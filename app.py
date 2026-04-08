from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import random
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ✅ deployment-safe DB path
DB_PATH = os.environ.get("DB_PATH", "/tmp/stockr.db")


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
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            min_stock INTEGER NOT NULL DEFAULT 10,
            max_stock INTEGER NOT NULL DEFAULT 500,
            price REAL NOT NULL DEFAULT 0,
            value REAL GENERATED ALWAYS AS (quantity * price) STORED,
            supplier TEXT,
            location TEXT,
            status TEXT NOT NULL DEFAULT 'in-stock',
            last_updated TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sup_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            contact TEXT,
            phone TEXT,
            email TEXT,
            city TEXT,
            rating INTEGER DEFAULT 3,
            items INTEGER DEFAULT 0,
            orders INTEGER DEFAULT 0,
            on_time INTEGER DEFAULT 90
        );

        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id TEXT NOT NULL UNIQUE,
            supplier TEXT,
            item TEXT,
            qty INTEGER,
            amount REAL,
            date TEXT,
            status TEXT
        );
    """)
    conn.commit()

    if c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        seed_data(conn)

    conn.close()


def compute_status(qty, min_stock):
    if qty == 0:
        return "out"
    elif qty <= min_stock * 0.3:
        return "critical"
    elif qty <= min_stock:
        return "low"
    elif qty > 400:
        return "overstock"
    else:
        return "in-stock"


# 🔥 UPDATED SEED DATA (200–500 realistic items)
def seed_data(conn):
    c = conn.cursor()

    PRODUCTS = [
        "Laptop","Smartphone","Office Chair","Desk","Monitor","Keyboard","Mouse",
        "Printer","Router","Tablet","Headphones","Speaker","Webcam","Hard Drive",
        "SSD","USB Drive","Power Bank","Projector","Scanner","Camera","TV",
        "AC Unit","Fan","Refrigerator","Microwave","Coffee Machine",
        "Water Dispenser","Whiteboard","Bookshelf","Sofa"
    ]

    CATEGORIES = ["Electronics", "Furniture", "Appliances", "Office"]
    SUPPLIERS = ["TechCorp Ltd","Vertex Supply","Global Parts","NexGen","Delta Logistics"]
    LOCATIONS = ["A","B","C","D","E","F"]

    total_items = random.randint(200, 500)

    for i in range(total_items):
        name = random.choice(PRODUCTS)
        qty = random.randint(0, 500)
        min_stock = random.randint(10, 80)
        max_stock = random.randint(300, 600)
        price = random.randint(500, 80000)

        status = compute_status(qty, min_stock)

        c.execute("""
            INSERT OR IGNORE INTO inventory
            (sku, name, category, quantity, min_stock, max_stock, price, supplier, location, status, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            f"SKU{i+1:04}",
            f"{name} {random.randint(1, 100)}",
            random.choice(CATEGORIES),
            qty,
            min_stock,
            max_stock,
            price,
            random.choice(SUPPLIERS),
            f"{random.choice(LOCATIONS)}-{random.randint(1,12)}",
            status,
            datetime.now().strftime("%Y-%m-%d")
        ))

    conn.commit()


@app.route("/")
def home():
    return jsonify({
        "message": "STOCKR API running",
        "health": "/api/health"
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    conn = get_db()
    rows = conn.execute("SELECT * FROM inventory ORDER BY id").fetchall()
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
        INSERT INTO inventory
        (sku,name,category,quantity,min_stock,max_stock,price,supplier,location,status,last_updated)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data["sku"], data["name"], data["category"],
        qty, min_s, int(data.get("max_stock", 500)),
        float(data["price"]),
        data.get("supplier", ""), data.get("location", ""),
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


init_db()


# ✅ Render-compatible run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
