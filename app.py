from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import psycopg2
import psycopg2.extras
import os
from datetime import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = "stockr-secret-key"
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:AnubhavShivamVinmra@db.pbgkdkrfvdozazekrgnj.supabase.co:5432/postgres"
)

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE,
            name TEXT,
            category TEXT,
            quantity INTEGER,
            min_stock INTEGER,
            max_stock INTEGER DEFAULT 500,
            price REAL,
            status TEXT,
            supplier TEXT DEFAULT '',
            location TEXT DEFAULT '',
            last_updated TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            sup_id TEXT UNIQUE,
            name TEXT,
            contact TEXT,
            phone TEXT,
            email TEXT,
            city TEXT,
            rating INTEGER DEFAULT 3,
            items INTEGER DEFAULT 0,
            orders INTEGER DEFAULT 0,
            on_time INTEGER DEFAULT 90
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id SERIAL PRIMARY KEY,
            po_id TEXT UNIQUE,
            supplier TEXT,
            item TEXT,
            qty INTEGER,
            amount REAL,
            date TEXT,
            status TEXT
        )
    """)

    c.execute("SELECT COUNT(*) FROM inventory")
    if c.fetchone()["count"] == 0:
        items = [
            ("ELE001","Laptop","Electronics",50,10,500,50000,"in-stock","TechCorp Ltd","A-1-1"),
            ("ELE002","Mouse","Electronics",5,10,200,500,"low","TechCorp Ltd","A-1-2"),
            ("FUR001","Chair","Furniture",0,5,100,2000,"out","Vertex Supply Co","B-2-1"),
        ]
        for i in items:
            c.execute("""
                INSERT INTO inventory (sku,name,category,quantity,min_stock,max_stock,price,status,supplier,location,last_updated)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (*i, datetime.now().strftime("%Y-%m-%d")))

    c.execute("SELECT COUNT(*) FROM suppliers")
    if c.fetchone()["count"] == 0:
        sups = [
            ("SUP-001","TechCorp Ltd","Rajesh Kumar","+91-98100-12345","rajesh@techcorp.in","Bengaluru",5,38,124,97),
            ("SUP-002","Vertex Supply Co","Priya Sharma","+91-99200-56789","priya@vertexsupply.in","Mumbai",4,31,89,92),
            ("SUP-003","Global Parts Inc","Amit Patel","+91-97300-34567","amit@globalparts.in","Pune",4,29,76,89),
            ("SUP-004","NexGen Vendors","Sunita Rao","+91-96400-78901","sunita@nexgen.in","Hyderabad",3,24,54,84),
            ("SUP-005","Delta Logistics","Vikram Singh","+91-95500-23456","vikram@deltalog.in","Delhi",5,42,198,98),
            ("SUP-006","Prime Source","Ananya Das","+91-94600-67890","ananya@primesource.in","Chennai",4,46,112,94),
        ]
        for s in sups:
            c.execute("INSERT INTO suppliers (sup_id,name,contact,phone,email,city,rating,items,orders,on_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", s)

    c.execute("SELECT COUNT(*) FROM purchase_orders")
    if c.fetchone()["count"] == 0:
        pos = [
            ("PO-02400","TechCorp Ltd","Laptop",20,1000000,"2025-03-01","DELIVERED"),
            ("PO-02401","Vertex Supply Co","Chair",15,30000,"2025-03-10","IN TRANSIT"),
            ("PO-02402","Global Parts Inc","Mouse",100,50000,"2025-03-15","PROCESSING"),
            ("PO-02403","NexGen Vendors","Keyboard",50,75000,"2025-03-20","PENDING"),
            ("PO-02404","Delta Logistics","Monitor",10,200000,"2025-03-25","DELIVERED"),
        ]
        for p in pos:
            c.execute("INSERT INTO purchase_orders (po_id,supplier,item,qty,amount,date,status) VALUES (%s,%s,%s,%s,%s,%s,%s)", p)

    conn.commit()
    c.close()
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
    return "in-stock"

def fetch_all(query, params=None):
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params or ())
    rows = [dict(r) for r in c.fetchall()]
    c.close()
    conn.close()
    return rows

def fetch_one(query, params=None):
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params or ())
    row = c.fetchone()
    c.close()
    conn.close()
    return dict(row) if row else None

def execute(query, params=None):
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params or ())
    conn.commit()
    c.close()
    conn.close()

def broadcast_inventory():
    socketio.emit("inventory_update", fetch_all("SELECT * FROM inventory ORDER BY id"))

def broadcast_suppliers():
    socketio.emit("suppliers_update", fetch_all("SELECT * FROM suppliers ORDER BY id"))

def broadcast_purchase_orders():
    socketio.emit("purchase_orders_update", fetch_all("SELECT * FROM purchase_orders ORDER BY id"))

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/api/inventory", methods=["GET"])
def get_inventory():
    return jsonify(fetch_all("SELECT * FROM inventory ORDER BY id"))

@app.route("/api/inventory", methods=["POST"])
def add_item():
    data = request.json
    qty = int(data.get("quantity", 0))
    min_s = int(data.get("min_stock", 10))
    status = compute_status(qty, min_s)
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            INSERT INTO inventory (sku,name,category,quantity,min_stock,max_stock,price,status,supplier,location,last_updated)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
        """, (
            data["sku"], data["name"], data["category"],
            qty, min_s, int(data.get("max_stock", 500)),
            float(data.get("price", 0)), status,
            data.get("supplier", ""), data.get("location", ""),
            datetime.now().strftime("%Y-%m-%d")
        ))
        row = dict(c.fetchone())
        conn.commit()
        c.close()
        conn.close()
        broadcast_inventory()
        return jsonify(row), 201
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "SKU already exists"}), 409

@app.route("/api/inventory/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    data = request.json
    qty = int(data.get("quantity", 0))
    min_s = int(data.get("min_stock", 10))
    status = compute_status(qty, min_s)
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE inventory SET sku=%s,name=%s,category=%s,quantity=%s,min_stock=%s,
        price=%s,status=%s,supplier=%s,location=%s,last_updated=%s WHERE id=%s RETURNING *
    """, (
        data["sku"], data["name"], data["category"],
        qty, min_s, float(data.get("price", 0)), status,
        data.get("supplier", ""), data.get("location", ""),
        datetime.now().strftime("%Y-%m-%d"), item_id
    ))
    row = dict(c.fetchone())
    conn.commit()
    c.close()
    conn.close()
    broadcast_inventory()
    return jsonify(row)

@app.route("/api/inventory/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    execute("DELETE FROM inventory WHERE id=%s", (item_id,))
    broadcast_inventory()
    return jsonify({"message": "Deleted"})

@app.route("/api/suppliers", methods=["GET"])
def get_suppliers():
    return jsonify(fetch_all("SELECT * FROM suppliers ORDER BY id"))

@app.route("/api/purchase_orders", methods=["GET"])
def get_purchase_orders():
    return jsonify(fetch_all("SELECT * FROM purchase_orders ORDER BY id"))

@socketio.on("connect")
def on_connect():
    emit("inventory_update", fetch_all("SELECT * FROM inventory ORDER BY id"))
    emit("suppliers_update", fetch_all("SELECT * FROM suppliers ORDER BY id"))
    emit("purchase_orders_update", fetch_all("SELECT * FROM purchase_orders ORDER BY id"))

@socketio.on("request_sync")
def on_request_sync():
    emit("inventory_update", fetch_all("SELECT * FROM inventory ORDER BY id"))
    emit("suppliers_update", fetch_all("SELECT * FROM suppliers ORDER BY id"))
    emit("purchase_orders_update", fetch_all("SELECT * FROM purchase_orders ORDER BY id"))

init_db()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
