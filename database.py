"""Database setup for FreshKart. Uses SQLite or PostgreSQL. Never drops or resets data."""
import argparse
import mimetypes
import os
import re
import sqlite3
import sys

from flask import g
from werkzeug.security import generate_password_hash

try:
    from psycopg import IntegrityError as PostgresIntegrityError
except ImportError:
    PostgresIntegrityError = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "freshkart.db")
MIN_ADMIN_PASSWORD = 10
IntegrityError = (
    (sqlite3.IntegrityError, PostgresIntegrityError)
    if PostgresIntegrityError is not None
    else sqlite3.IntegrityError
)

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
CREATE TABLE IF NOT EXISTS cart_items (
    customer_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (customer_id, product_id)
);
CREATE TABLE IF NOT EXISTS product_images (
    image_name TEXT PRIMARY KEY,
    content BLOB NOT NULL,
    content_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TEXT
);
"""

POSTGRES_SCHEMA = (
    SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    .replace("farmer_id INTEGER", "farmer_id BIGINT")
    .replace("customer_id INTEGER", "customer_id BIGINT")
    .replace("order_id INTEGER", "order_id BIGINT")
    .replace("product_id INTEGER", "product_id BIGINT")
    .replace("user_id INTEGER", "user_id BIGINT")
    .replace("content BLOB", "content BYTEA")
)


class HybridRow(dict):
    """Provide both named and positional column access for PostgreSQL rows."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _hybrid_row_factory(cursor):
    columns = [column.name for column in cursor.description]
    return lambda values: HybridRow(zip(columns, values))


class DatabaseConnection:
    def __init__(self, connection, is_postgres=False):
        self.connection = connection
        self.is_postgres = is_postgres

    def execute(self, sql, params=()):
        if self.is_postgres:
            if sql.strip().upper() == "BEGIN IMMEDIATE":
                # PostgreSQL starts a transaction on the request's first query.
                return self.connection.cursor()
            sql = re.sub(r"\?", "%s", sql)
        return self.connection.execute(sql, params)

    def executescript(self, script):
        if not self.is_postgres:
            return self.connection.executescript(script)
        cursor = self.connection.cursor()
        for statement in script.split(";"):
            if statement.strip():
                cursor.execute(statement)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def connect():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        if PostgresIntegrityError is None:
            raise RuntimeError("DATABASE_URL is set, but psycopg is not installed.")
        import psycopg

        conn = psycopg.connect(database_url, row_factory=_hybrid_row_factory)
        return DatabaseConnection(conn, is_postgres=True)
    if os.environ.get("RENDER"):
        raise RuntimeError(
            "DATABASE_URL must point to PostgreSQL on Render; its local filesystem is not durable."
        )

    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return DatabaseConnection(conn)


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


def init_db(create_admin=True):
    """Create tables if missing and create the first admin if none exists."""
    conn = connect()
    conn.executescript(POSTGRES_SCHEMA if conn.is_postgres else SCHEMA)
    if conn.is_postgres:
        user_columns = {
            row["name"] for row in conn.execute(
                """SELECT column_name AS name FROM information_schema.columns
                   WHERE table_schema = current_schema() AND table_name = 'users'"""
            )
        }
        order_columns = {
            row["name"] for row in conn.execute(
                """SELECT column_name AS name FROM information_schema.columns
                   WHERE table_schema = current_schema() AND table_name = 'orders'"""
            )
        }
    else:
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
    if "phone_number" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_number
           ON users(phone_number) WHERE phone_number IS NOT NULL"""
    )
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
    if create_admin:
        username, password = _admin_credentials()
        has_admin = conn.execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone()
        if username and not has_admin:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, 'admin', 'Administrator')",
                (username, generate_password_hash(password)),
            )
    conn.commit()
    conn.close()
    if create_admin and os.environ.get("RESET_ADMIN_CREDENTIALS_ON_STARTUP") == "1":
        reset_admin_password()
        print("Admin credentials reset from environment.")


def migrate_sqlite_to_postgres(source_path, uploads_dir=None):
    """Copy a SQLite production database into an empty PostgreSQL database."""
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("Set DATABASE_URL to the PostgreSQL destination before migrating.")
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"SQLite source database does not exist: {source_path}")

    init_db(create_admin=False)
    target = connect()
    if not target.is_postgres:
        target.close()
        raise RuntimeError("The migration destination must be PostgreSQL.")

    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    try:
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite source database failed its integrity check: {integrity}")
        source_tables = {
            row["name"] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required_tables = {"users", "products", "orders", "order_items", "app_settings"}
        missing_tables = required_tables - source_tables
        if missing_tables:
            raise RuntimeError(
                f"SQLite source is missing required tables: {', '.join(sorted(missing_tables))}"
            )
    except Exception:
        source.close()
        target.close()
        raise
    upload_root = uploads_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "static", "uploads"
    )
    tables = ("users", "products", "orders", "order_items", "app_settings")
    copied = {}
    try:
        for table in (*tables, "cart_items", "product_images", "notifications"):
            count = target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count:
                raise RuntimeError(
                    f"PostgreSQL table '{table}' is not empty; refusing to risk overwriting data."
                )

        for table in tables:
            if table not in source_tables:
                continue
            source_columns = [row["name"] for row in source.execute(f"PRAGMA table_info({table})")]
            target_columns = [
                column.name for column in target.execute(f"SELECT * FROM {table} LIMIT 0").description
            ]
            unsupported = set(source_columns) - set(target_columns)
            if unsupported:
                raise RuntimeError(
                    f"SQLite table '{table}' has unsupported columns: {', '.join(sorted(unsupported))}"
                )
            columns = [column for column in source_columns if column in target_columns]
            placeholders = ", ".join("?" for _ in columns)
            quoted_columns = ", ".join(columns)
            rows = source.execute(f"SELECT {quoted_columns} FROM {table}").fetchall()
            for row in rows:
                target.execute(
                    f"INSERT INTO {table} ({quoted_columns}) VALUES ({placeholders})",
                    tuple(row[column] for column in columns),
                )
            copied[table] = len(rows)

        if "products" in source_tables:
            images = source.execute("SELECT image FROM products WHERE image != ''").fetchall()
            for row in images:
                image_name = row["image"]
                if os.path.basename(image_name) != image_name:
                    raise RuntimeError(f"Unexpected product image path in database: {image_name}")
                image_path = os.path.join(upload_root, image_name)
                if not os.path.isfile(image_path):
                    raise FileNotFoundError(
                        f"Image '{image_name}' is missing from {upload_root}; "
                        "copy all product images before retrying."
                    )
                with open(image_path, "rb") as image_file:
                    content = image_file.read()
                content_type = mimetypes.guess_type(image_name)[0] or "application/octet-stream"
                target.execute(
                    """INSERT INTO product_images (image_name, content, content_type)
                       VALUES (?, ?, ?)""",
                    (image_name, content, content_type),
                )
                copied["product_images"] = copied.get("product_images", 0) + 1

        for table in ("users", "products", "orders", "notifications"):
            target.execute(
                f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                         COALESCE((SELECT MAX(id) FROM {table}), 1),
                         EXISTS (SELECT 1 FROM {table}))"""
            )
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()
    for table, count in copied.items():
        print(f"Migrated {count} {table} rows.")


def reset_admin_password():
    """Change the admin password from ADMIN_USERNAME / ADMIN_PASSWORD. Keeps all other data."""
    username, password = _admin_credentials()
    if not username:
        raise SystemExit("Set ADMIN_USERNAME and ADMIN_PASSWORD first.")
    conn = connect()
    conn.executescript(POSTGRES_SCHEMA if conn.is_postgres else SCHEMA)
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
    parser = argparse.ArgumentParser(description="FreshKart database maintenance")
    parser.add_argument("--reset-admin", action="store_true")
    parser.add_argument("--migrate-sqlite", metavar="PATH")
    parser.add_argument("--uploads-dir", metavar="PATH")
    args = parser.parse_args()
    if args.migrate_sqlite:
        migrate_sqlite_to_postgres(args.migrate_sqlite, args.uploads_dir)
    elif args.reset_admin:
        reset_admin_password()
        print("Admin password updated. Other data was not changed.")
    else:
        init_db()
        print("Database ready.")
