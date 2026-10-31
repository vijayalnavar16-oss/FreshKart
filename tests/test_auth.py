"""Run with: python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

TMP = tempfile.mkdtemp()
os.environ.update(
    DATABASE_PATH=os.path.join(TMP, "test.db"),
    ADMIN_USERNAME="admin",
    ADMIN_PASSWORD="AdminPass123!",
    SECRET_KEY="test-secret",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402
import database  # noqa: E402
from app import app  # noqa: E402


class AuthTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.db = database.connect()
        self.db.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, full_name, is_active) VALUES (?, ?, 'customer', 'Test Customer', 1)",
            ("cust1", generate_password_hash("Cust12345")),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, full_name, is_active) VALUES (?, ?, 'customer', 'Inactive', 0)",
            ("cust2", generate_password_hash("Cust12345")),
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def login(self, username, password):
        return self.client.post("/login", data={"username": username, "password": password})

    def test_admin_can_login_and_reach_home(self):
        self.assertEqual(self.login("admin", "AdminPass123!").status_code, 302)
        self.assertEqual(self.client.get("/home").status_code, 200)

    def test_customer_can_login(self):
        self.db.execute(
            "UPDATE users SET phone_number = ? WHERE username = 'cust1'",
            ("+919876543212",),
        )
        self.db.commit()
        self.assertEqual(self.login("cust1", "Cust12345").status_code, 302)
        self.assertEqual(self.client.get("/home").status_code, 200)

    def test_wrong_password_is_rejected(self):
        r = self.login("admin", "wrong-password")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/home").status_code, 302)

    def test_inactive_user_cannot_login(self):
        self.login("cust2", "Cust12345")
        self.assertEqual(self.client.get("/home").status_code, 302)

    def test_protected_page_redirects_anonymous_users(self):
        r = self.client.get("/home")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_logout_ends_session(self):
        self.login("cust1", "Cust12345")
        self.client.post("/logout")
        self.assertEqual(self.client.get("/home").status_code, 302)

    def test_logout_form_requests_confirmation(self):
        self.login("cust1", "Cust12345")
        self.client.get("/lang/en")
        response = self.client.get("/home")
        self.assertIn(b'data-confirm="', response.data)
        self.assertIn(b"Are you sure you want to log out?", response.data)

    def test_customer_registration_and_phone_auth_routes_are_removed(self):
        self.assertEqual(self.client.get("/register").status_code, 404)
        self.assertEqual(
            self.client.post("/auth/phone-login", json={}).status_code, 404
        )
        self.assertEqual(self.client.get("/account/phone").status_code, 404)

    def test_passwords_are_hashed(self):
        row = self.db.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()
        self.assertNotIn("AdminPass123!", row["password_hash"])

    def test_admin_password_reset_keeps_other_data(self):
        os.environ["ADMIN_PASSWORD"] = "NewAdminPass456!"
        database.reset_admin_password()
        self.assertEqual(self.login("admin", "NewAdminPass456!").status_code, 302)
        os.environ["ADMIN_PASSWORD"] = "AdminPass123!"
        database.reset_admin_password()  # restore the original password for other tests
        count = self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertGreaterEqual(count, 3)


if __name__ == "__main__":
    unittest.main()
