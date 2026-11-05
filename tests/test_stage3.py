"""Stage 3 tests: shopping, cart, delivery rules, checkout.
Run: python -m unittest discover -s tests -v"""
import os
import json
import sys
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "test3.db"))
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "AdminPass123!")
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
from app import app  # noqa: E402
from shop import delivery_dates  # noqa: E402

PASSWORD = "Pass12345"
MONDAY = "2000-01-03"  # a Monday, never a valid delivery day


class Stage3Tests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.db = database.connect()
        tag = uuid.uuid4().hex[:8]
        self.farmer = f"farm_{tag}"
        self.customer = f"cust_{tag}"

        admin = app.test_client()
        admin.post("/login", data={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]})
        admin.post("/admin/users", data={"action": "create", "username": self.farmer,
                   "full_name": "Ravi Farmer", "password": PASSWORD, "role": "farmer", "address": "Hosur"})
        admin.post("/admin/users", data={"action": "create", "username": self.customer,
                   "full_name": "Asha Customer", "password": PASSWORD, "role": "customer",
                   "address": "12 MG Road, Bengaluru",
                   "phone_number": "+916" + str(int(tag, 16) % 1_000_000_000).zfill(9)})
        self.admin = admin

        farmer_id = self.db.execute("SELECT id FROM users WHERE username = ?", (self.farmer,)).fetchone()["id"]
        self.tomato = self.add_product("Tomato", 40, 10, farmer_id)
        self.ghost = self.add_product("Ghost", 10, 5, farmer_id, deleted=1)

        self.client = app.test_client()
        customer_id = self.db.execute(
            "SELECT id FROM users WHERE username = ?", (self.customer,)
        ).fetchone()["id"]
        with self.client.session_transaction() as user_session:
            user_session["user_id"] = customer_id

    def tearDown(self):
        self.db.close()

    def add_product(self, name, price, stock, farmer_id, deleted=0):
        cur = self.db.execute(
            """INSERT INTO products (farmer_id, name, category, price, unit, stock, description, deleted)
               VALUES (?, ?, 'Other', ?, 'kg', ?, 'Fresh', ?)""",
            (farmer_id, name, price, stock, deleted))
        self.db.commit()
        return cur.lastrowid

    def stock_of(self, pid):
        return self.db.execute("SELECT stock FROM products WHERE id = ?", (pid,)).fetchone()["stock"]

    def customer_id(self):
        return self.db.execute("SELECT id FROM users WHERE username = ?", (self.customer,)).fetchone()["id"]

    def order_count(self):
        return self.db.execute("SELECT COUNT(*) FROM orders WHERE customer_id = ?",
                               (self.customer_id(),)).fetchone()[0]

    def checkout(self, date=None, address="12 MG Road, Bengaluru", payment="COD",
                 phone=None):
        date = date or delivery_dates()[0][0]
        data = {"address": address, "delivery_date": date, "payment": payment}
        if phone is not None:
            data["phone"] = phone
        return self.client.post("/checkout", data=data)

    def test_listing_shows_live_products_only(self):
        body = self.client.get("/shop").data
        self.assertIn(b"Tomato", body)
        self.assertNotIn(b"Ghost", body)

    def test_kannada_marketplace_search_uses_database_products(self):
        home = self.client.get("/home").data
        self.assertIn("ತಾಜಾ ತರಕಾರಿಗಳನ್ನು ಆರ್ಡರ್ ಮಾಡಿ".encode(), home)
        self.assertIn("ತರಕಾರಿಗಳನ್ನು ಹುಡುಕಿ".encode(), home)
        self.assertIn(b"Tomato", home)

        results = self.client.get("/shop?q=Tomato").data
        self.assertIn(b"Tomato", results)
        self.assertNotIn(b"Ghost", results)

    def test_detail_shows_farmer(self):
        r = self.client.get(f"/shop/{self.tomato}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Ravi Farmer", r.data)

    def test_customer_can_ask_groq_about_current_catalog(self):
        response_mock = MagicMock()
        response_mock.__enter__.return_value.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Tomato is available for ₹40 per kg."}}]
        }).encode()
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test-groq-secret",
            "GROQ_API_BASE_URL": "https://api.groq.com/openai/v1",
        }), patch("app.urlopen", return_value=response_mock) as urlopen:
            response = self.client.post(
                "/assistant", data={"question": "What is available under ₹50?"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tomato is available", response.data)
        self.assertNotIn(b"test-groq-secret", response.data)
        api_request = urlopen.call_args.args[0]
        self.assertEqual(
            api_request.full_url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(api_request.get_header("Authorization"), "Bearer test-groq-secret")
        payload = json.loads(api_request.data)
        self.assertIn("Tomato", payload["messages"][1]["content"])
        self.assertIn("What is available under", payload["messages"][1]["content"])

    def test_shopping_assistant_reports_missing_groq_key(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post(
                "/assistant", data={"question": "What vegetables are available?"}
            )
        self.assertEqual(response.status_code, 302)
        home = self.client.get("/home")
        self.assertIn(b"Set GROQ_API_KEY in Render", home.data)

    def test_shopping_assistant_is_customer_only(self):
        self.assertEqual(
            self.admin.post("/assistant", data={"question": "Hello"}).status_code,
            403,
        )

    def test_admin_cannot_use_shopping_pages(self):
        self.assertEqual(self.admin.get("/shop").status_code, 403)
        self.assertEqual(self.admin.get("/cart").status_code, 403)

    def test_cannot_add_more_than_stock(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "11"})
        self.assertNotIn(b"Tomato", self.client.get("/cart").data)

    def test_add_update_and_remove(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "3"})
        self.assertIn(b"Tomato", self.client.get("/cart").data)
        self.client.post(f"/cart/update/{self.tomato}", data={"quantity": "0"})
        self.assertIn("ನಿಮ್ಮ ಕಾರ್ಟ್ ಖಾಲಿಯಾಗಿದೆ.".encode(), self.client.get("/cart").data)

    def test_cart_is_stored_in_database_across_sessions(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "3"})
        self.client.post("/logout")

        another_session = app.test_client()
        another_session.post(
            "/login", data={"username": self.customer, "password": PASSWORD}
        )
        self.assertIn(b"Tomato", another_session.get("/cart").data)
        saved = self.db.execute(
            "SELECT quantity FROM cart_items WHERE customer_id = ? AND product_id = ?",
            (self.customer_id(), self.tomato),
        ).fetchone()
        self.assertEqual(saved["quantity"], 3)

    def test_checkout_rejects_non_delivery_day(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "2"})
        before = self.order_count()
        self.checkout(date=MONDAY)
        self.assertEqual(self.order_count(), before)
        self.assertEqual(self.stock_of(self.tomato), 10)

    def test_checkout_success_reduces_stock_and_clears_cart(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "2"})
        before = self.order_count()
        self.checkout()
        self.assertEqual(self.order_count(), before + 1)
        self.assertEqual(self.stock_of(self.tomato), 8)
        self.assertIn("ನಿಮ್ಮ ಕಾರ್ಟ್ ಖಾಲಿಯಾಗಿದೆ.".encode(), self.client.get("/cart").data)
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM cart_items WHERE customer_id = ?",
                (self.customer_id(),),
            ).fetchone()[0],
            0,
        )

    def test_order_and_admin_notifications_are_persisted(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        self.checkout()
        self.assertIn(b"Order #", self.client.get("/notifications").data)
        self.assertIn(b"New order #", self.admin.get("/notifications").data)
        self.client.post("/notifications/read")
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
                (self.customer_id(),),
            ).fetchone()[0],
            0,
        )

    def test_admin_can_view_order_customer_and_items(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "2"})
        self.checkout()
        response = self.admin.get("/admin/orders")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Asha Customer", response.data)
        self.assertIn(b"Tomato", response.data)
        self.assertIn(b"12 MG Road, Bengaluru", response.data)

    def test_admin_dashboard_shows_recent_order_customer(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        self.checkout()
        response = self.admin.get("/home")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recent orders", response.data)
        self.assertIn(b"Asha Customer", response.data)
        self.assertIn(b"Tomato", response.data)

    def test_orders_page_is_admin_only(self):
        self.assertEqual(self.client.get("/admin/orders").status_code, 403)
        self.assertEqual(app.test_client().get("/admin/orders").status_code, 302)

    def test_delivery_is_always_free_for_new_orders(self):
        self.db.execute(
            """INSERT INTO app_settings (key, value) VALUES ('free_delivery', '0')
               ON CONFLICT(key) DO UPDATE SET value = excluded.value"""
        )
        self.db.commit()
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "2"})
        cart = self.client.get("/cart")
        self.assertNotIn(b"Delivery charge", cart.data)
        self.checkout()
        order = self.db.execute(
            "SELECT id, delivery_charge, total FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
            (self.customer_id(),),
        ).fetchone()
        self.assertEqual(order["delivery_charge"], 0)
        self.assertEqual(order["total"], 80)
        admin_orders = self.admin.get("/admin/orders")
        self.assertNotIn(b"Delivery charge", admin_orders.data)
        self.assertNotIn(b"Restore", admin_orders.data)
        self.assertNotIn(b"Enable free delivery", admin_orders.data)

        customer_order = self.client.get(f"/orders/{order['id']}")
        self.assertNotIn(b"Delivery charge", customer_order.data)

    def test_checkout_fails_cleanly_when_stock_changed(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "5"})
        self.db.execute("UPDATE products SET stock = 2 WHERE id = ?", (self.tomato,))
        self.db.commit()
        before = self.order_count()
        self.checkout()
        self.assertEqual(self.order_count(), before)
        self.assertEqual(self.stock_of(self.tomato), 2)

    def test_checkout_needs_address(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        before = self.order_count()
        self.checkout(address="")
        self.assertEqual(self.order_count(), before)

    def test_upi_order_is_pending_not_paid(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        response = self.checkout(payment="UPI")
        row = self.db.execute(
            """SELECT id, status, payment_method, payment_status, customer_phone
               FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1""",
            (self.customer_id(),)).fetchone()
        self.assertEqual(row["status"], "Pending")
        self.assertEqual(row["payment_method"], "UPI")
        self.assertEqual(row["payment_status"], "pending")
        self.assertTrue(row["customer_phone"].startswith("+91"))
        self.assertIn(f"/orders/{row['id']}/payment", response.headers["Location"])
        payment = self.client.get(response.headers["Location"])
        self.assertEqual(payment.status_code, 200)
        self.assertIn(b"DIRECT UPI PAYMENT", payment.data)
        self.assertIn(b"8296863406@ybl", payment.data)
        self.assertIn(b"upi://pay?", payment.data)
        self.assertIn(b"phonepe://pay?", payment.data)
        self.assertIn(b"paytmmp://pay?", payment.data)
        self.assertIn(b"tez://upi/pay?", payment.data)
        self.assertIn(b"PhonePe", payment.data)
        self.assertIn(b"Paytm", payment.data)
        self.assertIn(b"Google Pay", payment.data)
        self.assertIn(b"data:image/svg+xml;base64", payment.data)
        self.assertIn(b"I have completed payment", payment.data)

    def test_customer_cannot_open_another_customers_upi_payment(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        self.checkout(payment="UPI")
        order_id = self.db.execute(
            "SELECT id FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
            (self.customer_id(),),
        ).fetchone()["id"]
        other = app.test_client()
        other_name = f"other_{uuid.uuid4().hex[:8]}"
        self.admin.post("/admin/users", data={
            "action": "create", "username": other_name, "full_name": "Other Customer",
            "password": PASSWORD, "role": "customer", "address": "",
            "phone_number": "+916" + str(uuid.uuid4().int % 1_000_000_000).zfill(9),
        })
        other.post("/login", data={"username": other_name, "password": PASSWORD})
        self.assertEqual(other.get(f"/orders/{order_id}/payment").status_code, 404)
        self.assertEqual(other.get(f"/orders/{order_id}").status_code, 404)

    def test_admin_verifies_upi_payment_and_receipt_shows_delivery_date(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        self.checkout(payment="UPI")
        order = self.db.execute(
            "SELECT id, total, delivery_date FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
            (self.customer_id(),),
        ).fetchone()
        self.client.post(
            f"/orders/{order['id']}/payment-submitted",
            follow_redirects=True,
        )
        still_pending = self.db.execute(
            "SELECT payment_status, status FROM orders WHERE id = ?", (order["id"],)
        ).fetchone()
        self.assertEqual(still_pending["payment_status"], "verification_requested")
        self.assertEqual(still_pending["status"], "Pending")

        response = self.admin.post(
            f"/admin/orders/{order['id']}/verify-upi",
            follow_redirects=True,
        )
        self.assertIn(b"UPI payment verified", response.data)
        receipt = self.client.get(f"/orders/{order['id']}")
        self.assertIn("ಪಾವತಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ".encode(), receipt.data)
        self.assertIn("ದೃಢೀಕರಿಸಲಾಗಿದೆ".encode(), receipt.data)
        self.assertIn(order["delivery_date"].encode(), receipt.data)
        self.assertIn("ವಿತರಣಾ ಸಮಯ".encode(), receipt.data)
        self.assertIn("ಅಂಗಡಿಯಿಂದ ದೃಢೀಕರಿಸಲಾಗುತ್ತದೆ".encode(), receipt.data)
        saved = self.db.execute(
            "SELECT payment_status, status FROM orders WHERE id = ?", (order["id"],)
        ).fetchone()
        self.assertEqual(saved["payment_status"], "paid")
        self.assertEqual(saved["status"], "Confirmed")

    def test_unpaid_upi_order_can_be_cancelled_once_and_stock_returned(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "2"})
        self.checkout(payment="UPI")
        order = self.db.execute(
            "SELECT id FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
            (self.customer_id(),),
        ).fetchone()
        self.assertEqual(self.stock_of(self.tomato), 8)
        self.admin.post(f"/admin/orders/{order['id']}/cancel-upi")
        self.admin.post(f"/admin/orders/{order['id']}/cancel-upi")
        self.assertEqual(self.stock_of(self.tomato), 10)
        saved = self.db.execute(
            "SELECT payment_status, status, stock_released FROM orders WHERE id = ?",
            (order["id"],),
        ).fetchone()
        self.assertEqual(saved["payment_status"], "cancelled")
        self.assertEqual(saved["status"], "Cancelled")
        self.assertEqual(saved["stock_released"], 1)

    def test_checkout_uses_phone_saved_on_customer_account(self):
        cart_page = self.client.get("/cart")
        self.assertNotIn(b'name="phone"', cart_page.data)
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        response = self.checkout(payment="UPI")
        order = self.db.execute(
            "SELECT customer_phone FROM orders WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
            (self.customer_id(),),
        ).fetchone()
        customer_phone = self.db.execute(
            "SELECT phone_number FROM users WHERE id = ?", (self.customer_id(),)
        ).fetchone()["phone_number"]
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order["customer_phone"], customer_phone)

    def test_checkout_without_saved_phone_returns_to_cart(self):
        self.db.execute(
            "UPDATE users SET phone_number = NULL WHERE username = ?", (self.customer,)
        )
        self.db.commit()
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        response = self.client.post("/checkout", data={"address": "12 MG Road"})
        self.assertEqual(response.status_code, 302)
        cart = self.client.get("/cart")
        self.assertEqual(cart.status_code, 200)
        self.assertIn(b"Ask the store administrator", cart.data)

    def test_cod_order_receipt_shows_items_and_delivery_date(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "2"})
        response = self.checkout()
        receipt = self.client.get(response.headers["Location"])
        self.assertEqual(receipt.status_code, 200)
        self.assertIn("ಆರ್ಡರ್ ಮಾಡಿದ ವಸ್ತುಗಳು".encode(), receipt.data)
        self.assertIn(b"Tomato", receipt.data)
        self.assertIn("ವಿತರಣಾ ಸಮಯ".encode(), receipt.data)

    def test_removed_product_is_dropped_from_cart(self):
        self.client.post(f"/cart/add/{self.tomato}", data={"quantity": "1"})
        self.db.execute("UPDATE products SET deleted = 1 WHERE id = ?", (self.tomato,))
        self.db.commit()
        self.assertIn("ನಿಮ್ಮ ಕಾರ್ಟ್ ಖಾಲಿಯಾಗಿದೆ.".encode(), self.client.get("/cart").data)

    def test_adding_deleted_product_is_not_found(self):
        self.assertEqual(self.client.post(f"/cart/add/{self.ghost}", data={"quantity": "1"}).status_code, 404)

    def test_delivery_dates_are_only_wednesday_or_sunday(self):
        self.assertTrue(all(label in ("Wednesday", "Sunday") for _, label in delivery_dates()))


if __name__ == "__main__":
    unittest.main()
