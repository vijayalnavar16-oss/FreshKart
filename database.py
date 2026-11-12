"""FreshKart database layer: PostgreSQL on Render/Supabase, SQLite for local tests."""
import os
import re
import sqlite3
import sys
from flask import g
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "freshkart.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
MIN_ADMIN_PASSWORD = 10
USE_POSTGRES = bool(DATABASE_URL)
if os.environ.get("RENDER") and not USE_POSTGRES:
    raise RuntimeError("DATABASE_URL is required on Render. Configure the Supabase PostgreSQL connection string.")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','farmer','customer')),
 full_name TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', phone_number TEXT UNIQUE, is_active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, farmer_id INTEGER NOT NULL REFERENCES users(id),
 name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL CHECK(price >= 0), unit TEXT NOT NULL,
 stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0), description TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
 deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL REFERENCES users(id),
 total REAL NOT NULL, delivery_charge REAL NOT NULL, address TEXT NOT NULL, delivery_date TEXT NOT NULL,
 payment_method TEXT NOT NULL CHECK(payment_method IN ('COD','UPI')), status TEXT NOT NULL DEFAULT 'Pending',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, customer_phone TEXT NOT NULL DEFAULT '', cashfree_order_id TEXT,
 cashfree_session_id TEXT, payment_status TEXT NOT NULL DEFAULT 'pending', stock_released INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders(id),
 product_id INTEGER NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL CHECK(quantity > 0), price REAL NOT NULL);
CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_number ON users(phone_number) WHERE phone_number IS NOT NULL;
"""

POSTGRES_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS freshkart;
SET search_path TO freshkart, public;
CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','farmer','customer')),
 full_name TEXT NOT NULL, address TEXT NOT NULL DEFAULT '', phone_number TEXT UNIQUE,
 is_active SMALLINT NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)));
CREATE TABLE IF NOT EXISTS products (id BIGSERIAL PRIMARY KEY, farmer_id BIGINT NOT NULL REFERENCES users(id),
 name TEXT NOT NULL, category TEXT NOT NULL, price DOUBLE PRECISION NOT NULL CHECK(price >= 0), unit TEXT NOT NULL,
 stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0), description TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
 deleted SMALLINT NOT NULL DEFAULT 0 CHECK(deleted IN (0,1)));
CREATE TABLE IF NOT EXISTS orders (id BIGSERIAL PRIMARY KEY, customer_id BIGINT NOT NULL REFERENCES users(id),
 total DOUBLE PRECISION NOT NULL, delivery_charge DOUBLE PRECISION NOT NULL, address TEXT NOT NULL,
 delivery_date TEXT NOT NULL, payment_method TEXT NOT NULL CHECK(payment_method IN ('COD','UPI')),
 status TEXT NOT NULL DEFAULT 'Pending', created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 customer_phone TEXT NOT NULL DEFAULT '', cashfree_order_id TEXT, cashfree_session_id TEXT,
 payment_status TEXT NOT NULL DEFAULT 'pending', stock_released SMALLINT NOT NULL DEFAULT 0 CHECK(stock_released IN (0,1)));
CREATE TABLE IF NOT EXISTS order_items (id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL REFERENCES orders(id),
 product_id BIGINT NOT NULL REFERENCES products(id), quantity INTEGER NOT NULL CHECK(quantity > 0), price DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_number ON users(phone_number) WHERE phone_number IS NOT NULL;
"""

class PgCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._lastrowid = None
    @property
    def rowcount(self):
        return self._cursor.rowcount
    @property
    def lastrowid(self):
        if self._lastrowid is None:
            row = self._cursor.fetchone()
            self._lastrowid = row["id"] if row else None
        return self._lastrowid
    def fetchone(self):
        return self._cursor.fetchone()
    def fetchall(self):
        return self._cursor.fetchall()

class PgConnection:
    def __init__(self, raw):
        self.raw = raw
    def execute(self, sql, params=()):
        from psycopg2.extras import DictCursor
        sql = sql.replace("BEGIN IMMEDIATE", "BEGIN")
        sql = re.sub(r"\?", "%s", sql)
        add_returning = bool(re.match(r"\s*INSERT\s+INTO\s+(users|products|orders|order_items)\b", sql, re.I)) and "RETURNING" not in sql.upper()
        if add_returning:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        cur = self.raw.cursor(cursor_factory=DictCursor)
        cur.execute(sql, params)
        return PgCursor(cur)
    def executescript(self, script):
        cur = self.raw.cursor()
        for statement in script.split(";"):
            if statement.strip():
                cur.execute(statement)
        cur.close()
    def commit(self):
        self.raw.commit()
    def rollback(self):
        self.raw.rollback()
    def close(self):
        self.raw.close()

if USE_POSTGRES:
    import psycopg2
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError

def connect():
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import DictCursor
        raw = psycopg2.connect(DATABASE_URL, sslmode="require", cursor_factory=DictCursor, connect_timeout=15, options="-c search_path=freshkart,public")
        return PgConnection(raw)
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db

def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def _admin_credentials():
    username = (os.environ.get("FRESHKART_ADMIN_USERNAME") or os.environ.get("ADMIN_USERNAME", "")).strip()
    password = os.environ.get("FRESHKART_ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        return None, None
    if len(password) < MIN_ADMIN_PASSWORD:
        raise SystemExit(f"FRESHKART_ADMIN_PASSWORD must be at least {MIN_ADMIN_PASSWORD} characters.")
    return username, password

def init_db():
    conn = connect()
    if USE_POSTGRES:
        conn.executescript(POSTGRES_SCHEMA)
    else:
        conn.executescript(SQLITE_SCHEMA)
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "phone_number" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
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
    username, password = _admin_credentials()
    if username:
        row = conn.execute("SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO users (username,password_hash,role,full_name) VALUES (?,?,'admin','Administrator')",
                         (username, generate_password_hash(password)))
        elif row["role"] != "admin":
            conn.close()
            raise SystemExit("FRESHKART_ADMIN_USERNAME belongs to a non-admin account.")
        else:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (generate_password_hash(password), row["id"]))
    conn.commit()
    conn.close()

def reset_admin_password():
    username, password = _admin_credentials()
    if not username:
        raise SystemExit("Set FRESHKART_ADMIN_USERNAME and FRESHKART_ADMIN_PASSWORD first.")
    conn = connect()
    row = conn.execute("SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO users (username,password_hash,role,full_name) VALUES (?,?,'admin','Administrator')",
                     (username, generate_password_hash(password)))
    elif row["role"] != "admin":
        conn.close()
        raise SystemExit("That username belongs to a non-admin account.")
    else:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), row["id"]))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    reset_admin_password() if "--reset-admin" in sys.argv else init_db()
    print("Database ready.")
