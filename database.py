"""Database setup for FreshKart. Uses SQLite. Never drops or resets data."""
import os
import sqlite3
import sys

from flask import g
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "freshkart.db")
MIN_ADMIN_PASSWORD = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'farmer', 'customer')),
    full_name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    phone_number TEXT UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    unit TEXT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    description TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES users(id),
    total REAL NOT NULL,
    delivery_charge REAL NOT NULL,
    address TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('COD', 'UPI')),
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    customer_phone TEXT NOT NULL DEFAULT '',
    cashfree_order_id TEXT,
    cashfree_session_id TEXT,
    payment_status TEXT NOT NULL DEFAULT 'pending',
    stock_released INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Per-request connection, closed automatically at the end of the request."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _admin_credentials():
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        return None, None
    if len(password) < MIN_ADMIN_PASSWORD:
        raise SystemExit(f"ADMIN_PASSWORD must be at least {MIN_ADMIN_PASSWORD} characters.")
    return username, password


def init_db():
    """Create tables if missing and create the first admin if none exists."""
    conn = connect()
    conn.executescript(SCHEMA)
    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "phone_number" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_number
           ON users(phone_number) WHERE phone_number IS NOT NULL"""
    )
    order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
    migrations = {
        "customer_phone": "ALTER TABLE orders ADD COLUMN customer_phone TEXT NOT NULL DEFAULT ''",
        "cashfree_order_id": "ALTER TABLE orders ADD COLUMN cashfree_order_id TEXT",
        "cashfree_session_id": "ALTER TABLE orders ADD COLUMN cashfree_session_id TEXT",
        "payment_status": "ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'pending'",
        "stock_released": "ALTER TABLE orders ADD COLUMN stock_released INTEGER NOT NULL DEFAULT 0",
    }
    for column, statement in migrations.items():
        if column not in order_columns:
            conn.execute(statement)
    legacy_customers = conn.execute(
        """SELECT u.id, (
               SELECT o.customer_phone FROM orders o
               WHERE o.customer_id = u.id AND o.customer_phone != ''
               ORDER BY o.id DESC LIMIT 1
           ) AS customer_phone
           FROM users u WHERE u.role = 'customer' AND u.phone_number IS NULL"""
    ).fetchall()
    for customer in legacy_customers:
        phone = customer["customer_phone"] or ""
        digits = "".join(character for character in phone if character.isdigit())
        if len(digits) == 10 and digits[0] in "6789":
            phone = f"+91{digits}"
        elif len(digits) == 12 and digits.startswith("91"):
            phone = f"+{digits}"
        else:
            continue
        if not conn.execute(
            "SELECT 1 FROM users WHERE phone_number = ?", (phone,)
        ).fetchone():
            conn.execute(
                "UPDATE users SET phone_number = ? WHERE id = ?",
                (phone, customer["id"]),
            )
    username, password = _admin_credentials()
    has_admin = conn.execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone()
    if username and not has_admin:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, 'admin', 'Administrator')",
            (username, generate_password_hash(password)),
        )
    conn.commit()
    conn.close()


def reset_admin_password():
    """Change the admin password from ADMIN_USERNAME / ADMIN_PASSWORD. Keeps all other data."""
    username, password = _admin_credentials()
    if not username:
        raise SystemExit("Set ADMIN_USERNAME and ADMIN_PASSWORD first.")
    conn = connect()
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, 'admin', 'Administrator')",
            (username, generate_password_hash(password)),
        )
    elif row["role"] != "admin":
        conn.close()
        raise SystemExit("That username belongs to a non-admin account. Choose a different ADMIN_USERNAME.")
    else:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (generate_password_hash(password), row["id"]))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    if "--reset-admin" in sys.argv:
        reset_admin_password()
        print("Admin password updated. Other data was not changed.")
    else:
        init_db()
        print("Database ready.")
