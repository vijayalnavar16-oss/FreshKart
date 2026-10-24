
import os
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "instance"
DATABASE_PATH = DATABASE_DIR / "freshkart.db"


def get_db():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection


def init_db():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = get_db()

    try:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,

            full_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,

            role TEXT NOT NULL
                CHECK(role IN ('customer', 'farmer', 'admin')),

            address TEXT,

            is_active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            farmer_id INTEGER,

            name TEXT NOT NULL,
            category TEXT NOT NULL,

            price_paise INTEGER NOT NULL
                CHECK(price_paise >= 0),

            stock_quantity REAL NOT NULL DEFAULT 0
                CHECK(stock_quantity >= 0),

            unit TEXT NOT NULL DEFAULT 'kg',

            description TEXT,

            image_url TEXT,

            is_available INTEGER NOT NULL DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(farmer_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        );


        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            customer_id INTEGER NOT NULL,

            order_number TEXT NOT NULL UNIQUE,

            delivery_date TEXT NOT NULL,

            delivery_slot TEXT NOT NULL
                CHECK(delivery_slot IN ('Wednesday', 'Sunday')),

            delivery_address TEXT NOT NULL,

            total_paise INTEGER NOT NULL DEFAULT 0,

            delivery_charge_paise INTEGER NOT NULL DEFAULT 0,

            status TEXT NOT NULL DEFAULT 'Placed',

            payment_method TEXT DEFAULT 'Cash on Delivery',

            payment_status TEXT DEFAULT 'Pending',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(customer_id)
                REFERENCES users(id)
                ON DELETE RESTRICT
        );


        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id INTEGER NOT NULL,

            product_id INTEGER,

            farmer_id INTEGER,

            product_name TEXT NOT NULL,

            quantity REAL NOT NULL
                CHECK(quantity > 0),

            unit TEXT NOT NULL,

            price_paise INTEGER NOT NULL,

            subtotal_paise INTEGER NOT NULL,

            FOREIGN KEY(order_id)
                REFERENCES orders(id)
                ON DELETE CASCADE,

            FOREIGN KEY(product_id)
                REFERENCES products(id)
                ON DELETE SET NULL,

            FOREIGN KEY(farmer_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        );


        CREATE TABLE IF NOT EXISTS delivery_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            delivery_day TEXT NOT NULL
                CHECK(delivery_day IN ('Wednesday', 'Sunday')),

            delivery_date TEXT NOT NULL UNIQUE,

            start_time TEXT DEFAULT '08:00',

            end_time TEXT DEFAULT '18:00',

            is_active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            title TEXT NOT NULL,

            message TEXT NOT NULL,

            is_read INTEGER NOT NULL DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        );


        CREATE INDEX IF NOT EXISTS idx_products_farmer
        ON products(farmer_id);


        CREATE INDEX IF NOT EXISTS idx_products_category
        ON products(category);


        CREATE INDEX IF NOT EXISTS idx_orders_customer
        ON orders(customer_id);


        CREATE INDEX IF NOT EXISTS idx_orders_delivery
        ON orders(delivery_date);


        CREATE INDEX IF NOT EXISTS idx_order_items_order
        ON order_items(order_id);


        CREATE INDEX IF NOT EXISTS idx_notifications_user
        ON notifications(user_id);
        """)

        create_default_admin(connection)

        connection.commit()

    finally:
        connection.close()


def create_default_admin(connection):
    username = os.environ.get(
        "FRESHKART_ADMIN_USERNAME",
        "admin"
    )

    password = os.environ.get(
        "FRESHKART_ADMIN_PASSWORD",
        "ChangeMe123!"
    )

    existing_admin = connection.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
          AND role = 'admin'
        """,
        (username,)
    ).fetchone()

    if existing_admin:
        return

    password_hash = generate_password_hash(password)

    connection.execute(
        """
        INSERT INTO users (
            username,
            password_hash,
            full_name,
            role,
            is_active
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            username,
            password_hash,
            "FreshKart Administrator",
            "admin",
            1
        )
    )


def get_user_by_username(username):
    connection = get_db()

    try:
        return connection.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
              AND is_active = 1
            """,
            (username,)
        ).fetchone()

    finally:
        connection.close()


def create_user(
    username,
    password,
    full_name,
    role,
    phone=None,
    email=None,
    address=None
):
    if role not in ("customer", "farmer"):
        raise ValueError(
            "Only customer and farmer registration is allowed."
        )

    password_hash = generate_password_hash(password)

    connection = get_db()

    try:
        cursor = connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                phone,
                email,
                role,
                address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                full_name,
                phone,
                email,
                role,
                address
            )
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print("FreshKart database initialized successfully.")
