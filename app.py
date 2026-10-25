
import os
import sqlite3
from functools import wraps
from datetime import datetime, date
from flask import (
    Flask,
    request,
    jsonify,
    session,
    render_template,
    redirect
)
from werkzeug.security import check_password_hash
from database import get_db, init_db, create_user


# ==================================================
# APPLICATION
# ==================================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    app.secret_key = "development-only-change-this-secret"

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ==================================================
# HELPERS
# ==================================================

def response(message, success=True, **data):

    result = {
        "success": success,
        "message": message
    }

    result.update(data)

    return jsonify(result)


def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()

    try:

        user = db.execute(
            """
            SELECT id, username, full_name, phone, email,
                   role, address, is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        return user

    finally:
        db.close()


def login_required(role=None):

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            user = get_current_user()

            if not user:

                return response(
                    "Please login first",
                    False
                ), 401

            if not user["is_active"]:

                session.clear()

                return response(
                    "Account is inactive",
                    False
                ), 403

            if role and user["role"] != role:

                return response(
                    "Access denied",
                    False
                ), 403

            return func(*args, **kwargs)

        return wrapper

    return decorator


def user_json(user):

    if not user:
        return None

    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "phone": user["phone"],
        "email": user["email"],
        "role": user["role"],
        "address": user["address"],
        "is_active": user["is_active"]
    }


def product_json(product):

    return {
        "id": product["id"],
        "farmer_id": product["farmer_id"],
        "name": product["name"],
        "category": product["category"],
        "price": product["price_paise"] / 100,
        "price_paise": product["price_paise"],
        "stock_quantity": product["stock_quantity"],
        "unit": product["unit"],
        "description": product["description"],
        "image_url": product["image_url"],
        "is_available": product["is_available"]
    }


# ==================================================
# HOME AND DASHBOARD PAGES
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")


@app.route("/login")
def login_page():

    return render_template("login.html")


@app.route("/customer")
@login_required("customer")
def customer_page():

    return render_template("customer.html")


@app.route("/farmer")
@login_required("farmer")
def farmer_page():

    return render_template("farmer.html")


@app.route("/admin")
@login_required("admin")
def admin_page():

    return render_template("admin.html")


# ==================================================
# HEALTH
# ==================================================

@app.route("/api/health")
def health():

    return response(
        "FreshKart backend is healthy",
        True,
        service="FreshKart"
    )


# ==================================================
# REGISTRATION
# CUSTOMER AND FARMER ACCOUNTS CREATED BY ADMIN ONLY
# ==================================================

@app.route("/api/register", methods=["POST"])
def register():

    return response(
        "Registration disabled. Contact FreshKart admin.",
        False
    ), 403


# ==================================================
# LOGIN
# ==================================================

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = str(
        data.get("username", "")
    ).strip()

    password = str(
        data.get("password", "")
    )

    if not username or not password:

        return response(
            "Username and password are required",
            False
        ), 400

    db = get_db()

    try:

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

    finally:
        db.close()

    if not user:

        return response(
            "Invalid username or password",
            False
        ), 401

    if not user["is_active"]:

        return response(
            "Your account is inactive",
            False
        ), 403

    try:

        password_valid = check_password_hash(
            user["password_hash"],
            password
        )

    except (ValueError, TypeError):

        password_valid = False

    if not password_valid:

        return response(
            "Invalid username or password",
            False
        ), 401

    session.clear()

    session["user_id"] = user["id"]
    session["role"] = user["role"]

    redirects = {
        "customer": "/customer",
        "farmer": "/farmer",
        "admin": "/admin"
    }

    return response(
        "Login successful",
        True,
        user=user_json(user),
        redirect=redirects.get(user["role"], "/")
    )


# ==================================================
# CURRENT USER
# ==================================================

@app.route("/api/me")
@login_required()
def me():

    user = get_current_user()

    return response(
        "User loaded",
        True,
        user=user_json(user)
    )


# ==================================================
# LOGOUT
# ==================================================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return response(
        "Logged out successfully",
        True
    )


# ==================================================
# PUBLIC PRODUCTS
# ==================================================

@app.route("/api/products", methods=["GET"])
def products():

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT *
            FROM products
            WHERE is_available = 1
              AND stock_quantity > 0
            ORDER BY created_at DESC
            """
        ).fetchall()

        result = [
            product_json(product)
            for product in rows
        ]

    finally:
        db.close()

    return response(
        "Products loaded",
        True,
        products=result
    )


# ==================================================
# CUSTOMER ORDERS
# ==================================================

@app.route("/api/customer/orders", methods=["GET"])
@login_required("customer")
def customer_orders():

    user = get_current_user()

    db = get_db()

    try:

        orders = db.execute(
            """
            SELECT *
            FROM orders
            WHERE customer_id = ?
            ORDER BY created_at DESC
            """,
            (user["id"],)
        ).fetchall()

        result = []

        for order in orders:

            items = db.execute(
                """
                SELECT *
                FROM order_items
                WHERE order_id = ?
                """,
                (order["id"],)
            ).fetchall()

            result.append({

                "id": order["id"],

                "order_number": order["order_number"],

                "delivery_date": order["delivery_date"],

                "delivery_slot": order["delivery_slot"],

                "delivery_address": order["delivery_address"],

                "total": order["total_paise"] / 100,

                "total_paise": order["total_paise"],

                "status": order["status"],

                "payment_method": order["payment_method"],

                "payment_status": order["payment_status"],

                "items": [

                    {
                        "product_name": item["product_name"],
                        "quantity": item["quantity"],
                        "unit": item["unit"],
                        "price": item["price_paise"] / 100,
                        "subtotal": item["subtotal_paise"] / 100
                    }

                    for item in items

                ]

            })

    finally:
        db.close()

    return response(
        "Orders loaded",
        True,
        orders=result
    )


# ==================================================
# PLACE ORDER
# ==================================================

@app.route("/api/customer/orders", methods=["POST"])
@login_required("customer")
def place_order():

    user = get_current_user()

    data = request.get_json(silent=True) or {}

    items = data.get("items", [])

    delivery_date = str(
        data.get("delivery_date", "")
    ).strip()

    delivery_address = str(
        data.get(
            "delivery_address",
            user["address"] or ""
        )
    ).strip()

    payment_method = str(
        data.get("payment_method", "COD")
    ).strip().upper()

    if not isinstance(items, list) or not items:

        return response(
            "Cart is empty",
            False
        ), 400

    if not delivery_address:

        return response(
            "Delivery address is required",
            False
        ), 400

    if payment_method not in ("COD", "UPI"):

        return response(
            "Invalid payment method",
            False
        ), 400

    try:

        requested_date = date.fromisoformat(
            delivery_date
        )

    except ValueError:

        return response(
            "Invalid delivery date",
            False
        ), 400

    if requested_date <= date.today():

        return response(
            "Choose a future delivery date",
            False
        ), 400

    delivery_day = requested_date.strftime("%A")

    if delivery_day not in ("Wednesday", "Sunday"):

        return response(
            "Delivery available only on Wednesday and Sunday",
            False
        ), 400

    db = get_db()

    try:

        total_paise = 0

        order_items = []

        for item in items:

            product_id = item.get("product_id")

            try:

                quantity = float(
                    item.get("quantity", 0)
                )

            except (ValueError, TypeError):

                return response(
                    "Invalid quantity",
                    False
                ), 400

            if quantity <= 0:

                return response(
                    "Quantity must be greater than zero",
                    False
                ), 400

            product = db.execute(
                """
                SELECT *
                FROM products
                WHERE id = ?
                  AND is_available = 1
                  AND stock_quantity > 0
                """,
                (product_id,)
            ).fetchone()

            if not product:

                return response(
                    "Product unavailable",
                    False
                ), 400

            if quantity > product["stock_quantity"]:

                return response(
                    "Insufficient stock for "
                    + product["name"],
                    False
                ), 400

            subtotal = int(
                round(
                    product["price_paise"] * quantity
                )
            )

            total_paise += subtotal

            order_items.append({

                "product": product,

                "quantity": quantity,

                "subtotal": subtotal

            })

        order_number = (
            "FK"
            + datetime.now().strftime("%Y%m%d%H%M%S")
            + str(user["id"])
        )

        cursor = db.execute(
            """
            INSERT INTO orders (
                customer_id,
                order_number,
                delivery_date,
                delivery_slot,
                delivery_address,
                total_paise,
                delivery_charge_paise,
                status,
                payment_method,
                payment_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                order_number,
                delivery_date,
                delivery_day,
                delivery_address,
                total_paise,
                0,
                "Placed",
                payment_method,
                "Pending"
            )
        )

        order_id = cursor.lastrowid

        for item in order_items:

            product = item["product"]

            db.execute(
                """
                INSERT INTO order_items (
                    order_id,
                    product_id,
                    farmer_id,
                    product_name,
                    quantity,
                    unit,
                    price_paise,
                    subtotal_paise
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    product["id"],
                    product["farmer_id"],
                    product["name"],
                    item["quantity"],
                    product["unit"],
                    product["price_paise"],
                    item["subtotal"]
                )
            )

            db.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE id = ?
                """,
                (
                    item["quantity"],
                    product["id"]
                )
            )

        db.commit()

        return response(
            "Order placed successfully",
            True,
            order_id=order_id,
            order_number=order_number,
            total=total_paise / 100
        ), 201

    except Exception:

        db.rollback()

        app.logger.exception(
            "Order placement error"
        )

        return response(
            "Unable to place order",
            False
        ), 500

    finally:

        db.close()


# ==================================================
# FARMER PRODUCTS
# ==================================================

@app.route("/api/farmer/products", methods=["GET"])
@login_required("farmer")
def farmer_products():

    user = get_current_user()

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT *
            FROM products
            WHERE farmer_id = ?
            ORDER BY created_at DESC
            """,
            (user["id"],)
        ).fetchall()

        result = [
            product_json(product)
            for product in rows
        ]

    finally:
        db.close()

    return response(
        "Farmer products loaded",
        True,
        products=result
    )


# ==================================================
# ADD FARMER PRODUCT
# ==================================================

@app.route("/api/farmer/products", methods=["POST"])
@login_required("farmer")
def add_farmer_product():

    user = get_current_user()

    data = request.get_json(silent=True) or {}

    name = str(
        data.get("name", "")
    ).strip()

    category = str(
        data.get("category", "Vegetables")
    ).strip()

    description = str(
        data.get("description", "")
    ).strip()

    unit = str(
        data.get("unit", "kg")
    ).strip()

    image_url = str(
        data.get("image_url", "")
    ).strip()

    try:

        price = float(
            data.get("price", 0)
        )

        stock = float(
            data.get("stock_quantity", 0)
        )

    except (ValueError, TypeError):

        return response(
            "Invalid price or stock",
            False
        ), 400

    if not name or price < 0 or stock < 0:

        return response(
            "Enter valid product details",
            False
        ), 400

    db = get_db()

    try:

        cursor = db.execute(
            """
            INSERT INTO products (
                farmer_id,
                name,
                category,
                price_paise,
                stock_quantity,
                unit,
                description,
                image_url,
                is_available
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                name,
                category,
                int(round(price * 100)),
                stock,
                unit,
                description,
                image_url,
                1
            )
        )

        db.commit()

        product_id = cursor.lastrowid

    finally:
        db.close()

    return response(
        "Product added successfully",
        True,
        product_id=product_id
    ), 201


# ==================================================
# UPDATE FARMER PRODUCT
# ==================================================

@app.route(
    "/api/farmer/products/<int:product_id>",
    methods=["PUT"]
)
@login_required("farmer")
def update_farmer_product(product_id):

    user = get_current_user()

    data = request.get_json(silent=True) or {}

    db = get_db()

    try:

        product = db.execute(
            """
            SELECT *
            FROM products
            WHERE id = ?
              AND farmer_id = ?
            """,
            (
                product_id,
                user["id"]
            )
        ).fetchone()

        if not product:

            return response(
                "Product not found",
                False
            ), 404

        name = str(
            data.get("name", product["name"])
        ).strip()

        category = str(
            data.get(
                "category",
                product["category"]
            )
        ).strip()

        description = str(
            data.get(
                "description",
                product["description"] or ""
            )
        ).strip()

        unit = str(
            data.get("unit", product["unit"])
        ).strip()

        image_url = str(
            data.get(
                "image_url",
                product["image_url"] or ""
            )
        ).strip()

        try:

            price = float(
                data.get(
                    "price",
                    product["price_paise"] / 100
                )
            )

            stock = float(
                data.get(
                    "stock_quantity",
                product["stock_quantity"]
                )
            )

        except (ValueError, TypeError):

            return response(
                "Invalid price or stock",
                False
            ), 400

        if not name or price < 0 or stock < 0:

            return response(
                "Invalid product details",
                False
            ), 400

        db.execute(
            """
            UPDATE products
            SET name = ?,
                category = ?,
                price_paise = ?,
                stock_quantity = ?,
                unit = ?,
                description = ?,
                image_url = ?
            WHERE id = ?
              AND farmer_id = ?
            """,
            (
                name,
                category,
                int(round(price * 100)),
                stock,
                unit,
                description,
                image_url,
                product_id,
                user["id"]
            )
        )

        db.commit()

    finally:
        db.close()

    return response(
        "Product updated successfully",
        True
    )


# ==================================================
# DELETE FARMER PRODUCT
# ==================================================

@app.route(
    "/api/farmer/products/<int:product_id>",
    methods=["DELETE"]
)
@login_required("farmer")
def delete_farmer_product(product_id):

    user = get_current_user()

    db = get_db()

    try:

        cursor = db.execute(
            """
            DELETE FROM products
            WHERE id = ?
              AND farmer_id = ?
            """,
            (
                product_id,
                user["id"]
            )
        )

        db.commit()

        deleted = cursor.rowcount

    finally:
        db.close()

    if not deleted:

        return response(
            "Product not found",
            False
        ), 404

    return response(
        "Product deleted successfully",
        True
    )


# ==================================================
# FARMER ORDERS
# ==================================================

@app.route("/api/farmer/orders", methods=["GET"])
@login_required("farmer")
def farmer_orders():

    user = get_current_user()

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT DISTINCT
                o.id,
                o.order_number,
                o.delivery_date,
                o.delivery_slot,
                o.delivery_address,
                o.status,
                o.payment_method,
                o.payment_status,
                u.full_name AS customer_name,
                u.phone AS customer_phone
            FROM orders o
            JOIN order_items oi
                ON oi.order_id = o.id
            JOIN users u
                ON u.id = o.customer_id
            WHERE oi.farmer_id = ?
            ORDER BY o.created_at DESC
            """,
            (user["id"],)
        ).fetchall()

        result = []

        for order in rows:

            items = db.execute(
                """
                SELECT *
                FROM order_items
                WHERE order_id = ?
                  AND farmer_id = ?
                """,
                (
                    order["id"],
                    user["id"]
                )
            ).fetchall()

            result.append({

                "id": order["id"],

                "order_number": order["order_number"],

                "customer_name": order["customer_name"],

                "customer_phone": order["customer_phone"],

                "delivery_date": order["delivery_date"],

                "delivery_slot": order["delivery_slot"],

                "delivery_address": order["delivery_address"],

                "status": order["status"],

                "payment_method": order["payment_method"],

                "payment_status": order["payment_status"],

                "items": [

                    {
                        "product_name": item["product_name"],
                        "quantity": item["quantity"],
                        "unit": item["unit"],
                        "subtotal": item["subtotal_paise"] / 100
                    }

                    for item in items

                ]

            })

    finally:
        db.close()

    return response(
        "Farmer orders loaded",
        True,
        orders=result
    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/api/admin/dashboard", methods=["GET"])
@login_required("admin")
def admin_dashboard():

    db = get_db()

    try:

        customers = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role = 'customer'
            """
        ).fetchone()[0]

        farmers = db.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role = 'farmer'
            """
        ).fetchone()[0]

        products = db.execute(
            """
            SELECT COUNT(*)
            FROM products
            """
        ).fetchone()[0]

        orders = db.execute(
            """
            SELECT COUNT(*)
            FROM orders
            """
        ).fetchone()[0]

        revenue = db.execute(
            """
            SELECT COALESCE(SUM(total_paise), 0)
            FROM orders
            WHERE status != 'Cancelled'
            """
        ).fetchone()[0]

    finally:
        db.close()

    return response(
        "Dashboard loaded",
        True,
        dashboard={
            "customers": customers,
            "farmers": farmers,
            "products": products,
            "orders": orders,
            "revenue": revenue / 100
        }
    )


# ==================================================
# ADMIN CUSTOMERS
# ==================================================

@app.route("/api/admin/customers", methods=["GET"])
@login_required("admin")
def admin_customers():

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT id, username, full_name,
                   phone, email, role, address,
                   is_active, created_at
            FROM users
            WHERE role = 'customer'
            ORDER BY created_at DESC
            """
        ).fetchall()

        result = [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()

    return response(
        "Customers loaded",
        True,
        customers=result
    )


# ==================================================
# ADMIN FARMERS
# ==================================================

@app.route("/api/admin/farmers", methods=["GET"])
@login_required("admin")
def admin_farmers():

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT id, username, full_name,
                   phone, email, role, address,
                   is_active, created_at
            FROM users
            WHERE role = 'farmer'
            ORDER BY created_at DESC
            """
        ).fetchall()

        result = [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()

    return response(
        "Farmers loaded",
        True,
        farmers=result
    )


# ==================================================
# ADMIN CREATE CUSTOMER OR FARMER
# ==================================================

@app.route("/api/admin/users", methods=["POST"])
@login_required("admin")
def admin_create_user():

    data = request.get_json(silent=True) or {}

    username = str(
        data.get("username", "")
    ).strip()

    password = str(
        data.get("password", "")
    )

    full_name = str(
        data.get("full_name", "")
    ).strip()

    role = str(
        data.get("role", "customer")
    ).strip().lower()

    phone = str(
        data.get("phone", "")
    ).strip()

    email = str(
        data.get("email", "")
    ).strip()

    address = str(
        data.get("address", "")
    ).strip()

    if not username or not password or not full_name:

        return response(
            "Username, password and full name required",
            False
        ), 400

    if len(password) < 8:

        return response(
            "Password must contain at least 8 characters",
            False
        ), 400

    if role not in ("customer", "farmer"):

        return response(
            "Only customer and farmer accounts can be created",
            False
        ), 400

    try:

        user_id = create_user(
            username=username,
            password=password,
            full_name=full_name,
            role=role,
            phone=phone,
            email=email,
            address=address
        )

        return response(
            "User created successfully",
            True,
            user_id=user_id
        ), 201

    except sqlite3.IntegrityError:

        return response(
            "Username already exists",
            False
        ), 409

    except Exception:

        app.logger.exception(
            "Admin user creation error"
        )

        return response(
            "Unable to create user",
            False
        ), 500


# ==================================================
# ADMIN USER STATUS
# ==================================================

@app.route(
    "/api/admin/users/<int:user_id>/status",
    methods=["PUT"]
)
@login_required("admin")
def admin_user_status(user_id):

    data = request.get_json(silent=True) or {}

    active = data.get("is_active")

    if active not in (True, False, 0, 1):

        return response(
            "is_active must be true or false",
            False
        ), 400

    db = get_db()

    try:

        cursor = db.execute(
            """
            UPDATE users
            SET is_active = ?
            WHERE id = ?
              AND role IN ('customer', 'farmer')
            """,
            (
                int(active),
                user_id
            )
        )

        db.commit()

        updated = cursor.rowcount

    finally:
        db.close()

    if not updated:

        return response(
            "User not found",
            False
        ), 404

    return response(
        "User status updated",
        True
    )


# ==================================================
# ADMIN PRODUCTS
# ==================================================

@app.route("/api/admin/products", methods=["GET"])
@login_required("admin")
def admin_products():

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT p.*, u.full_name AS farmer_name
            FROM products p
            LEFT JOIN users u
                ON u.id = p.farmer_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()

        result = []

        for row in rows:

            item = product_json(row)

            item["farmer_name"] = row["farmer_name"]

            result.append(item)

    finally:
        db.close()

    return response(
        "Products loaded",
        True,
        products=result
    )


# ==================================================
# ADMIN ORDERS
# ==================================================

@app.route("/api/admin/orders", methods=["GET"])
@login_required("admin")
def admin_orders():

    db = get_db()

    try:

        rows = db.execute(
            """
            SELECT o.*, 
                   u.full_name AS customer_name,
                   u.phone AS customer_phone
            FROM orders o
            JOIN users u
                ON u.id = o.customer_id
            ORDER BY o.created_at DESC
            """
        ).fetchall()

        result = [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()

    return response(
        "Orders loaded",
        True,
        orders=result
    )


# ==================================================
# ADMIN UPDATE ORDER STATUS
# ==================================================

@app.route(
    "/api/admin/orders/<int:order_id>/status",
    methods=["PUT"]
)
@login_required("admin")
def admin_order_status(order_id):

    data = request.get_json(silent=True) or {}

    status = str(
        data.get("status", "")
    ).strip()

    allowed = (
        "Placed",
        "Confirmed",
        "Preparing",
        "Out for Delivery",
        "Delivered",
        "Cancelled"
    )

    if status not in allowed:

        return response(
            "Invalid order status",
            False
        ), 400

    db = get_db()

    try:

        cursor = db.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                order_id
            )
        )

        db.commit()

        updated = cursor.rowcount

    finally:
        db.close()

    if not updated:

        return response(
            "Order not found",
            False
        ), 404

    return response(
        "Order status updated",
        True
    )


# ==================================================
# FARMER UPDATE ORDER STATUS
# ==================================================

@app.route(
    "/api/farmer/orders/<int:order_id>/status",
    methods=["PUT"]
)
@login_required("farmer")
def farmer_order_status(order_id):

    user = get_current_user()

    data = request.get_json(silent=True) or {}

    status = str(
        data.get("status", "")
    ).strip()

    allowed = (
        "Confirmed",
        "Preparing",
        "Out for Delivery",
        "Delivered"
    )

    if status not in allowed:

        return response(
            "Invalid order status",
            False
        ), 400

    db = get_db()

    try:

        order = db.execute(
            """
            SELECT o.id
            FROM orders o
            JOIN order_items oi
                ON oi.order_id = o.id
            WHERE o.id = ?
              AND oi.farmer_id = ?
            """,
            (
                order_id,
                user["id"]
            )
        ).fetchone()

        if not order:

            return response(
                "Order not found",
                False
            ), 404

        db.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                order_id
            )
        )

        db.commit()

    finally:
        db.close()

    return response(
        "Order status updated",
        True
    )


# ==================================================
# ERROR HANDLERS
# ==================================================

@app.errorhandler(404)
def not_found(error):

    return response(
        "Resource not found",
        False
    ), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return response(
        "Method not allowed",
        False
    ), 405


@app.errorhandler(500)
def internal_error(error):

    app.logger.exception(
        "Internal server error"
    )

    return response(
        "Internal server error",
        False
    ), 500


# ==================================================
# DATABASE INITIALIZATION
# ==================================================

init_db()


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
