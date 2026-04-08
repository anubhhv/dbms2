from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import random
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ✅ FIXED: use writable path for cloud
DB_PATH = os.environ.get("DB_PATH", "/tmp/stockr.db")

# ─── Database Helpers ─────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT,
            category TEXT,
            quantity INTEGER,
            min_stock INTEGER,
            max_stock INTEGER,
            price REAL,
            value REAL,
            supplier TEXT,
            location TEXT,
            status TEXT,
            last_updated TEXT
        );
    """)
    conn.commit()

    # seed if empty
    if c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        for i in range(10):
            qty = random.randint(0, 100)
            min_s = random.randint(5, 20)
            price = random.randint(100, 5000)

            c.execute("""
                INSERT INTO inventory (sku,name,category,quantity,min_stock,max_stock,price,value,supplier,location,status,last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                f"SKU{i+1:03}",
                f"Item {i+1}",
                "General",
                qty,
                min_s,
                100,
                price,
                qty * price,
                "SupplierX",
                f"A-{i}",
                "in-stock",
                datetime.now().strftime("%Y-%m-%d")
            ))

    conn.commit()
    conn.close()

def compute_status(qty, min_stock):
    if qty == 0:
        return "out"
    elif qty <= min_stock:
        return "low"
    else:
        return "in-stock"

# ─── ROOT ROUTE (NO MORE 404 DRAMA) ─────────────────

@app.route("/")
def home():
    return jsonify({
        "message": "STOCKR API running",
        "endpoints": [
            "/api/health",
            "/api/inventory"
        ]
    })

# ─── HEALTH ─────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

# ─── INVENTORY ─────────────────

@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/inventory", methods=["POST"])
def create_item():
    data = request.get_json()

    qty = int(data["quantity"])
    min_s = int(data["min_stock"])
    status = compute_status(qty, min_s)

    conn = get_db()
    conn.execute("""
        INSERT INTO inventory (sku,name,category,quantity,min_stock,max_stock,price,value,supplier,location,status,last_updated)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data["sku"],
        data["name"],
        data["category"],
        qty,
        min_s,
        int(data.get("max_stock", 100)),
        float(data["price"]),
        qty * float(data["price"]),
        data.get("supplier", ""),
        data.get("location", ""),
        status,
        datetime.now().strftime("%Y-%m-%d")
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Item created"})

@app.route("/api/inventory/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM inventory WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})

# ─── INIT DB ─────────────────

init_db()

# ─── START SERVER (CRUCIAL FIX) ─────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # ✅ FIXED FOR RENDER
    app.run(host="0.0.0.0", port=port)
