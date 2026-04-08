from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ✅ Use writable path for cloud
DB_PATH = "/tmp/stockr.db"

# ── DB SETUP ─────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT,
            category TEXT,
            quantity INTEGER,
            min_stock INTEGER,
            price REAL,
            status TEXT,
            last_updated TEXT
        )
    """)

    # seed minimal data if empty
    if c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        items = [
            ("ELE001", "Laptop", "Electronics", 50, 10, 50000, "in-stock"),
            ("ELE002", "Mouse", "Electronics", 5, 10, 500, "low"),
            ("FUR001", "Chair", "Furniture", 0, 5, 2000, "out"),
        ]
        for i in items:
            c.execute("""
                INSERT INTO inventory (sku,name,category,quantity,min_stock,price,status,last_updated)
                VALUES (?,?,?,?,?,?,?,?)
            """, (*i, datetime.now().strftime("%Y-%m-%d")))

    conn.commit()
    conn.close()

def compute_status(qty, min_stock):
    if qty == 0:
        return "out"
    elif qty <= min_stock:
        return "low"
    else:
        return "in-stock"

# ── ROUTES ─────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inventory").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/inventory", methods=["POST"])
def add_item():
    data = request.json

    qty = int(data["quantity"])
    min_s = int(data["min_stock"])
    status = compute_status(qty, min_s)

    conn = get_db()
    conn.execute("""
        INSERT INTO inventory (sku,name,category,quantity,min_stock,price,status,last_updated)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        data["sku"],
        data["name"],
        data["category"],
        qty,
        min_s,
        float(data["price"]),
        status,
        datetime.now().strftime("%Y-%m-%d")
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Item added"})

@app.route("/api/inventory/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM inventory WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Deleted"})

# ── START ─────────────────────────
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)