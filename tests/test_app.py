import tempfile
import unittest
from pathlib import Path

from app import create_app
from database import get_db


class FreshKartCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": str(Path(self.temp_dir.name) / "freshkart-test.sqlite3"),
        })
        self.client = self.app.test_client()

    def add_product(self, name, category="Vegetables", price_paise=3250,
                    stock_quantity=5, unit="500 g", is_available=1):
        with self.app.app_context():
            cursor = get_db().execute(
                "INSERT INTO products "
                "(name, category, price_paise, stock_quantity, unit, is_available) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, category, price_paise, stock_quantity, unit, is_available),
            )
            get_db().commit()
            return cursor.lastrowid

    def test_homepage_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FreshKart", response.data)
        self.assertIn(b"No items available right now. Please check back later.", response.data)

    def test_health_check(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_fresh_database_has_no_products(self):
        response = self.client.get("/api/products")
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data, {"products": [], "count": 0})

    def test_admin_entered_product_is_returned_by_search_and_category(self):
        product_id = self.add_product("Red Tomatoes")
        search = self.client.get("/api/products?q=TOMATO").get_json()
        category = self.client.get("/api/products?category=vegetables").get_json()

        self.assertEqual(search["count"], 1)
        self.assertEqual(search["products"][0]["id"], product_id)
        self.assertEqual(category["count"], 1)
        self.assertEqual(category["products"][0]["name"], "Red Tomatoes")

    def test_unavailable_and_out_of_stock_products_are_hidden(self):
        self.add_product("Available Apples", category="Fruits")
        self.add_product("Hidden Pears", category="Fruits", is_available=0)
        self.add_product("Sold Out Plums", category="Fruits", stock_quantity=0)
        response = self.client.get("/api/products?category=Fruits")
        data = response.get_json()

        self.assertEqual(data["count"], 1)
        self.assertEqual(data["products"][0]["name"], "Available Apples")


if __name__ == "__main__":
    unittest.main()