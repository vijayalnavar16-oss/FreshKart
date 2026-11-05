"""Stage 2 tests: accounts, roles, vegetables, photos. Run: python -m unittest discover -s tests -v"""
import io
import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test2.db"))
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "AdminPass123!")
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
from app import app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PASSWORD = "Pass12345"


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def product_fields(**overrides):
    data = {"name": "Tomato", "category": "Other", "unit": "kg",
            "price": "40", "stock": "25", "description": "Fresh"}
    data.update(overrides)
    return data


class Stage2Tests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.db = database.connect()
        self.admin = app.test_client()
        login(self.admin, "admin", os.environ["ADMIN_PASSWORD"])
        tag = uuid.uuid4().hex[:8]
        self.farmer_name = f"farmer_{tag}"
        self.other_name = f"other_{tag}"
        self.customer_name = f"cust_{tag}"
        self.create_account("farmer", self.farmer_name)
        self.create_account("farmer", self.other_name)
        self.create_account("customer", self.customer_name)

    def tearDown(self):
        self.db.close()

    def create_account(self, role, username, password=PASSWORD):
        return self.admin.post("/admin/users", data={
            "action": "create", "username": username, "full_name": username,
            "password": password, "role": role, "address": "",
            "phone_number": f"+916{uuid.uuid4().int % 1_000_000_000:09d}" if role == "customer" else "",
        })

    def user_id(self, username):
        return self.db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]

    def client_for(self, username):
        client = app.test_client()
        login(client, username, PASSWORD)
        return client

    def product_count(self):
        return self.db.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    def test_admin_creates_accounts(self):
        self.assertEqual(self.db.execute(
            "SELECT role FROM users WHERE username = ?", (self.farmer_name,)).fetchone()["role"], "farmer")
        self.assertEqual(self.db.execute(
            "SELECT role FROM users WHERE username = ?", (self.customer_name,)).fetchone()["role"], "customer")

    def test_customer_account_requires_mobile_number(self):
        username = f"no_phone_{uuid.uuid4().hex[:8]}"
        self.admin.post("/admin/users", data={
            "action": "create", "username": username, "full_name": "No Phone",
            "password": PASSWORD, "role": "customer", "address": "",
        })
        self.assertIsNone(self.db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone())

    def test_admin_can_update_customer_mobile_number(self):
        customer_id = self.user_id(self.customer_name)
        self.admin.post("/admin/users", data={
            "action": "update_phone", "user_id": str(customer_id),
            "phone_number": "+916123456789",
        })
        phone_number = self.db.execute(
            "SELECT phone_number FROM users WHERE id = ?", (customer_id,)
        ).fetchone()["phone_number"]
        self.assertEqual(phone_number, "+916123456789")

    def test_admin_can_reset_customer_password(self):
        customer_id = self.user_id(self.customer_name)
        new_password = "FreshPass987!"
        self.admin.post("/admin/users", data={
            "action": "reset_customer_password",
            "user_id": str(customer_id),
            "password": new_password,
        })
        self.assertEqual(login(app.test_client(), self.customer_name, new_password).status_code, 302)
        self.assertEqual(login(app.test_client(), self.customer_name, PASSWORD).status_code, 200)
        password_hash = self.db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (customer_id,)
        ).fetchone()["password_hash"]
        self.assertNotEqual(password_hash, new_password)

    def test_customer_password_reset_rejects_short_password_and_non_customers(self):
        customer_id = self.user_id(self.customer_name)
        original_hash = self.db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (customer_id,)
        ).fetchone()["password_hash"]
        self.admin.post("/admin/users", data={
            "action": "reset_customer_password",
            "user_id": str(customer_id),
            "password": "short",
        })
        customer_hash = self.db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (customer_id,)
        ).fetchone()["password_hash"]
        self.assertEqual(customer_hash, original_hash)
        self.admin.post("/admin/users", data={
            "action": "reset_customer_password",
            "user_id": str(self.user_id(self.farmer_name)),
            "password": "FreshPass987!",
        })
        self.assertEqual(login(app.test_client(), self.farmer_name, PASSWORD).status_code, 302)

    def test_init_db_migrates_legacy_orders_before_phone_backfill(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = os.path.join(directory, "legacy.db")
            conn = sqlite3.connect(legacy_path)
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    total REAL NOT NULL,
                    delivery_charge REAL NOT NULL,
                    address TEXT NOT NULL,
                    delivery_date TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    customer_phone TEXT NOT NULL DEFAULT ''
                );
                INSERT INTO users
                    (id, username, password_hash, role, full_name)
                    VALUES (1, 'legacy_customer', 'hash', 'customer', 'Legacy Customer');
                INSERT INTO orders
                    (id, customer_id, total, delivery_charge, address, delivery_date,
                     payment_method, customer_phone)
                    VALUES (1, 1, 10, 0, 'Address', '2030-01-02', 'COD', '9876543210');
            """)
            conn.close()

            with patch.object(database, "DB_PATH", legacy_path):
                database.init_db()
                migrated = database.connect()
                columns = {
                    row["name"] for row in migrated.execute("PRAGMA table_info(orders)")
                }
                phone = migrated.execute(
                    "SELECT phone_number FROM users WHERE username = 'legacy_customer'"
                ).fetchone()["phone_number"]
                migrated.close()

        self.assertIn("payment_status", columns)
        self.assertEqual(phone, "+919876543210")

    def test_render_refuses_ephemeral_sqlite(self):
        with patch.dict(os.environ, {"RENDER": "true"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                database.connect()

    def test_sqlite_import_requires_postgresql_destination(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                database.migrate_sqlite_to_postgres("unused.db")

    def test_duplicate_and_weak_accounts_rejected(self):
        self.create_account("customer", self.customer_name)
        count = self.db.execute("SELECT COUNT(*) FROM users WHERE username = ?", (self.customer_name,)).fetchone()[0]
        self.assertEqual(count, 1)
        weak_name = f"weak_{uuid.uuid4().hex[:8]}"
        self.create_account("customer", weak_name, password="short")
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM users WHERE username = ?", (weak_name,)).fetchone()[0], 0)

    def test_customer_cannot_open_management_pages(self):
        client = self.client_for(self.customer_name)
        self.assertEqual(client.get("/admin/users").status_code, 403)
        self.assertEqual(client.get("/products/").status_code, 403)
        self.assertEqual(client.get("/products/new").status_code, 403)

    def test_anonymous_user_is_sent_to_login(self):
        r = app.test_client().get("/products/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_farmer_adds_vegetable_with_photo(self):
        client = self.client_for(self.farmer_name)
        before = self.product_count()
        data = product_fields()
        data["image"] = (io.BytesIO(PNG), "tomato.png")
        client.post("/products/new", data=data, content_type="multipart/form-data")
        self.assertEqual(self.product_count(), before + 1)
        row = self.db.execute("SELECT * FROM products ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(row["farmer_id"], self.user_id(self.farmer_name))
        self.assertTrue(row["image"].endswith(".png"))
        stored_image = self.db.execute(
            "SELECT content, content_type FROM product_images WHERE image_name = ?",
            (row["image"],),
        ).fetchone()
        self.assertEqual(stored_image["content"], PNG)
        self.assertEqual(stored_image["content_type"], "image/png")
        response = client.get(f"/products/image/{row['image']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, PNG)

    def test_fake_image_is_rejected(self):
        client = self.client_for(self.farmer_name)
        before = self.product_count()
        data = product_fields()
        data["image"] = (io.BytesIO(b"this is not a picture"), "evil.png")
        client.post("/products/new", data=data, content_type="multipart/form-data")
        self.assertEqual(self.product_count(), before)

    def test_invalid_price_is_rejected(self):
        client = self.client_for(self.farmer_name)
        before = self.product_count()
        client.post("/products/new", data=product_fields(price="-5"))
        self.assertEqual(self.product_count(), before)

    def test_admin_assigns_product_to_farmer(self):
        self.admin.post("/products/new", data=product_fields(farmer_id=str(self.user_id(self.other_name))))
        row = self.db.execute("SELECT farmer_id FROM products ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(row["farmer_id"], self.user_id(self.other_name))

    def test_farmer_cannot_edit_another_farmers_product(self):
        self.admin.post("/products/new", data=product_fields(farmer_id=str(self.user_id(self.other_name))))
        pid = self.db.execute("SELECT id FROM products ORDER BY id DESC LIMIT 1").fetchone()["id"]
        client = self.client_for(self.farmer_name)
        self.assertEqual(client.get(f"/products/{pid}/edit").status_code, 403)
        self.assertEqual(client.post(f"/products/{pid}/delete").status_code, 403)

    def test_remove_is_soft_delete(self):
        client = self.client_for(self.farmer_name)
        client.post("/products/new", data=product_fields(name="Brinjal"))
        pid = self.db.execute("SELECT id FROM products ORDER BY id DESC LIMIT 1").fetchone()["id"]
        client.post(f"/products/{pid}/delete")
        row = self.db.execute("SELECT deleted FROM products WHERE id = ?", (pid,)).fetchone()
        self.assertEqual(row["deleted"], 1)  # row kept so past orders stay valid

    def test_deactivated_farmer_cannot_login(self):
        self.admin.post("/admin/users", data={"action": "toggle", "user_id": str(self.user_id(self.farmer_name))})
        self.assertEqual(login(app.test_client(), self.farmer_name, PASSWORD).status_code, 200)

    def test_dashboards_load_for_each_role(self):
        self.assertIn(b"Farmers", self.admin.get("/home").data)
        self.assertEqual(self.client_for(self.farmer_name).get("/home").status_code, 200)


if __name__ == "__main__":
    unittest.main()
