
import os
import uuid
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import (
    Flask,
    jsonify,
    request,
    session,
    redirect,
    render_template,
    url_for
)

from werkzeug.security import check_password_hash

from database import (
    init_db,
    get_db,
    create_user,
    get_user_by_username
)


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "FRESHKART_SECRET_KEY",
    "development-secret-change-this"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def query_db(query, args=(), one=False):
    connection = get_db()

    try:
        cursor = connection.execute(query, args)

        if one:
            return cursor.fetchone()

        return cursor.fetchall()

    finally:
        connection.close()


def execute_db(query, args=()):
    connection = get_db()

    try:
        cursor = connection.execute(query, args)

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


def money_to_paise(value):
    try:
        value = float(value)

        if value < 0:
            raise ValueError

        return round(value * 100)

    except (TypeError, ValueError):
        raise ValueError("Invalid price")


def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return query_db(
        """
        SELECT id, username, full_name, role, phone, email, address
        FROM users
        WHERE id = ?
          AND is_active = 1
        """,
        (user_id,),
        one=True
    )


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

def login_required(role=None):
    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            user = current_user()

            if not user:
                return jsonify({
                    "success": False,
                    "message": "Please login first"
                }), 401

            if role and user["role"] != role:
                return jsonify({
                    "success": False,
                    "message": "Access denied"
                }), 403

            return function(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "success": True,
        "message": "FreshKart API is running"
    })


@app.route("/api/register", methods=["POST"])
def register():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    full_name = str(data.get("full_name", "")).strip()

    role = str(data.get("role", "customer")).strip()

    phone = str(data.get("phone", "")).strip()
    email = str(data.get("email", "")).strip()
    address = str(data.get("address", "")).strip()

    if not username or not password or not full_name:
        return jsonify({
            "success": False,
            "message": "Username, password and full name are required"
        }), 400

    if len(username) < 3:
        return jsonify({
            "success": False,
            "message": "Username must contain at least 3 characters"
        }), 400

    if len(password) < 8:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 8 characters"
        }), 400

    if role not in ("customer", "farmer"):
        return jsonify({
            "success": False,
            "message": "Invalid registration role"
        }), 400

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

        return jsonify({
            "success": True,
            "message": "Account created successfully",
            "user_id": user_id
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "message": "Username already exists"
        }), 409


@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({
            "success": False,
            "message": "Username and password are required"
        }), 400

    user = get_user_by_username(username)

    if not user or not check_password_hash(
        user["password_hash"],
        password
    ):
        return jsonify({
            "success": False,
            "message": "Invalid username or password"
        }), 401

    session.clear()

    session["user_id"] = user["id"]

    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"]
        }
    })


@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    })


@app.route("/api/me")
@login_required()
def me():

    user = current_user()

    return jsonify({
        "success": True,
        "user": dict(user)
    })


# --------------------------------------------------
# PRODUCTS
# --------------------------------------------------

@app.route("/api/products")
def products():

    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = """
        SELECT
            p.id,
            p.name,
            p.category,
            p.price_paise,
            p.stock_quantity,
            p.unit,
            p.description,
            p.image_url,
            p.farmer_id,
            u.full_name AS farmer_name
        FROM products p
        LEFT JOIN users u
            ON p.farmer_id = u.id
        WHERE p.is_available = 1
          AND p.stock_quantity > 0
    """

    params = []

    if search:
        sql += " AND p.name LIKE ?"
        params.append("%" + search + "%")

    if category:
        sql += " AND p.category = ?"
        params.append(category)

    sql += " ORDER BY p.name"

    result = query_db(sql, params)

    return jsonify({
        "success": True,
        "products": [dict(row) for row in result]
    })


@app.route("/api/products/<int:product_id>")
def product_detail(product_id):

    product = query_db(
        """
        SELECT
            p.*,
            u.full_name AS farmer_name
        FROM products p
        LEFT JOIN users u
            ON p.farmer_id = u.id
        WHERE p.id = ?
        """,
        (product_id,),
        one=True
    )

    if not product:
        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    return jsonify({
        "success": True,
        "product": dict(product)
    })


# --------------------------------------------------
# FARMER PRODUCTS
# --------------------------------------------------

@app.route("/api/farmer/products", methods=["GET"])
@login_required("farmer")
def farmer_products():

    user = current_user()

    result = query_db(
        """
        SELECT *
        FROM products
        WHERE farmer_id = ?
        ORDER BY created_at DESC
        """,
        (user["id"],)
    )

    return jsonify({
        "success": True,
        "products": [dict(row) for row in result]
    })


@app.route("/api/farmer/products", methods=["POST"])
@login_required("farmer")
def farmer_add_product():

    user = current_user()

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()

    unit = str(data.get("unit", "kg")).strip()

    description = str(data.get("description", "")).strip()
    image_url = str(data.get("image_url", "")).strip()

    try:
        price_paise = money_to_paise(data.get("price_rupees"))

        stock_quantity = float(data.get("stock_quantity", 0))

        if stock_quantity < 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid price or stock quantity"
        }), 400

    if not name or not category:
        return jsonify({
            "success": False,
            "message": "Product name and category are required"
        }), 400

    product_id = execute_db(
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
            price_paise,
            stock_quantity,
            unit,
            description,
            image_url,
            1
        )
    )

    return jsonify({
        "success": True,
        "message": "Product added successfully",
        "product_id": product_id
    }), 201


@app.route("/api/farmer/products/<int:product_id>", methods=["PUT"])
@login_required("farmer")
def farmer_update_product(product_id):

    user = current_user()

    product = query_db(
        """
        SELECT *
        FROM products
        WHERE id = ?
          AND farmer_id = ?
        """,
        (product_id, user["id"]),
        one=True
    )

    if not product:
        return jsonify({
            "success": False,
            "message": "Product not found"
        }), 404

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", product["name"])).strip()

    category = str(
        data.get("category", product["category"])
    ).strip()

    try:
        price_paise = money_to_paise(
            data.get(
                "price_rupees",
                product["price_paise"] / 100
            )
        )

        stock_quantity = float(
            data.get(
                "stock_quantity",
                product["stock_quantity"]
            )
        )

        if stock_quantity < 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Invalid price or stock"
        }), 400

    execute_db(
        """
        UPDATE products
        SET name = ?,
            category = ?,
            price_paise = ?,
            stock_quantity = ?,
            description = ?,
            image_url = ?,
            is_available = ?
        WHERE id = ?
          AND farmer_id = ?
        """,
        (
            name,
            category,
            price_paise,
            stock_quantity,
            data.get("description", product["description"]),
            data.get("image_url", product["image_url"]),
            1 if stock_quantity > 0 else 0,
            product_id,
            user["id"]
        )
    )

    return jsonify({
        "success": True,
        "message": "Product updated successfully"
    })


@app.route("/api/farmer/products/<int:product_id>", methods=["DELETE"])
@login_required("farmer")
def farmer_delete_product(product_id):

    user = current_user()

    execute_db(
        """
        DELETE FROM products
        WHERE id = ?
          AND farmer_id = ?
        """,
        (product_id, user["id"])
    )

    return jsonify({
        "success": True,
        "message": "Product deleted"
    })


# --------------------------------------------------
# DELIVERY SCHEDULE
# --------------------------------------------------

def next_delivery_day():

    today = date.today()

    delivery_days = {
        2: "Wednesday",
        6: "Sunday"
    }

    for offset in range(1, 8):

        delivery_date = today + timedelta(days=offset)

        if delivery_date.weekday() in delivery_days:

            return {
                "date": delivery_date.isoformat(),
                "day": delivery_days[delivery_date.weekday()]
            }

    return None


@app.route("/api/delivery/next")
def next_delivery():

    delivery = next_delivery_day()

    return jsonify({
        "success": True,
        "delivery": delivery
    })


@app.route("/api/admin/delivery-schedule", methods=["GET"])
@login_required("admin")
def admin_delivery_schedule():

    result = query_db(
        """
        SELECT *
        FROM delivery_schedule
        ORDER BY delivery_date
        """
    )

    return jsonify({
        "success": True,
        "schedule": [dict(row) for row in result]
    })


@app.route("/api/admin/delivery-schedule", methods=["POST"])
@login_required("admin")
def admin_create_delivery():

    data = request.get_json(silent=True) or {}

    delivery_date = str(data.get("delivery_date", "")).strip()

    try:
        parsed_date = date.fromisoformat(delivery_date)

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid delivery date"
        }), 400

    if parsed_date.weekday() not in (2, 6):
        return jsonify({
            "success": False,
            "message": "Delivery must be Wednesday or Sunday"
        }), 400

    day = "Wednesday" if parsed_date.weekday() == 2 else "Sunday"

    execute_db(
        """
        INSERT INTO delivery_schedule (
            delivery_day,
            delivery_date,
            start_time,
            end_time,
            is_active
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            day,
            delivery_date,
            data.get("start_time", "08:00"),
            data.get("end_time", "18:00"),
            1
        )
    )

    return jsonify({
        "success": True,
        "message": "Delivery schedule created"
    }), 201


# --------------------------------------------------
# CUSTOMER ORDERS
# --------------------------------------------------

@app.route("/api/customer/orders", methods=["GET"])
@login_required("customer")
def customer_orders():

    user = current_user()

    result = query_db(
        """
        SELECT *
        FROM orders
        WHERE customer_id = ?
        ORDER BY created_at DESC
        """,
        (user["id"],)
    )

    return jsonify({
        "success": True,
        "orders": [dict(row) for row in result]
    })


@app.route("/api/customer/orders", methods=["POST"])
@login_required("customer")
def customer_create_order():

    user = current_user()

    data = request.get_json(silent=True) or {}

    items = data.get("items", [])

    delivery_address = str(
        data.get("delivery_address", user["address"] or "")
    ).strip()

    delivery_date = str(
        data.get("delivery_date", "")
    ).strip()

    if not items:
        return jsonify({
            "success": False,
            "message": "Your cart is empty"
        }), 400

    if not delivery_address:
        return jsonify({
            "success": False,
            "message": "Delivery address is required"
        }), 400

    try:
        parsed_date = date.fromisoformat(delivery_date)

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid delivery date"
        }), 400

    if parsed_date.weekday() not in (2, 6):
        return jsonify({
            "success": False,
            "message": "Choose Wednesday or Sunday"
        }), 400

    order_number = "FK-" + uuid.uuid4().hex[:10].upper()

    connection = get_db()

    try:
        total_paise = 0

        validated_items = []

        for item in items:

            product_id = int(item.get("product_id"))

            quantity = float(item.get("quantity"))

            if quantity <= 0:
                raise ValueError("Invalid quantity")

            product = connection.execute(
                """
                SELECT *
                FROM products
                WHERE id = ?
                  AND is_available = 1
                  AND stock_quantity >= ?
                """,
                (product_id, quantity)
            ).fetchone()

            if not product:
                raise ValueError(
                    "Product unavailable or insufficient stock"
                )

            subtotal = round(
                product["price_paise"] * quantity
            )

            total_paise += subtotal

            validated_items.append(
                (product, quantity, subtotal)
            )

        delivery_charge_paise = 0

        cursor = connection.execute(
            """
            INSERT INTO orders (
                customer_id,
                order_number,
                delivery_date,
                delivery_slot,
                delivery_address,
                total_paise,
                delivery_charge_paise,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                order_number,
                delivery_date,
                "Wednesday" if parsed_date.weekday() == 2 else "Sunday",
                delivery_address,
                total_paise,
                delivery_charge_paise,
                "Placed"
            )
        )

        order_id = cursor.lastrowid

        for product, quantity, subtotal in validated_items:

            connection.execute(
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
                    quantity,
                    product["unit"],
                    product["price_paise"],
                    subtotal
                )
            )

            connection.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - ?,
                    is_available = CASE
                        WHEN stock_quantity - ? <= 0 THEN 0
                        ELSE 1
                    END
                WHERE id = ?
                """,
                (
                    quantity,
                    quantity,
                    product["id"]
                )
            )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Order placed successfully",
            "order_id": order_id,
            "order_number": order_number,
            "total_paise": total_paise
        }), 201

    except (ValueError, TypeError, sqlite3.Error) as error:

        connection.rollback()

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    finally:
        connection.close()


# --------------------------------------------------
# FARMER ORDERS
# --------------------------------------------------

@app.route("/api/farmer/orders")
@login_required("farmer")
def farmer_orders():

    user = current_user()

    result = query_db(
        """
        SELECT
            o.id,
            o.order_number,
            o.delivery_date,
            o.delivery_slot,
            o.status,
            o.created_at,
            oi.product_name,
            oi.quantity,
            oi.unit,
            oi.subtotal_paise,
            u.full_name AS customer_name
        FROM order_items oi
        JOIN orders o
            ON oi.order_id = o.id
        JOIN users u
            ON o.customer_id = u.id
        WHERE oi.farmer_id = ?
        ORDER BY o.created_at DESC
        """,
        (user["id"],)
    )

    return jsonify({
        "success": True,
        "orders": [dict(row) for row in result]
    })


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

@app.route("/api/admin/dashboard")
@login_required("admin")
def admin_dashboard():

    stats = query_db(
        """
        SELECT
            (SELECT COUNT(*)
             FROM users
             WHERE role = 'customer') AS customers,

            (SELECT COUNT(*)
             FROM users
             WHERE role = 'farmer') AS farmers,

            (SELECT COUNT(*)
             FROM products) AS products,

            (SELECT COUNT(*)
             FROM products
             WHERE is_available = 1
               AND stock_quantity > 0) AS available_products,

            (SELECT COUNT(*)
             FROM orders) AS orders,

            (SELECT COALESCE(SUM(total_paise), 0)
             FROM orders) AS revenue
        """,
        one=True
    )

    return jsonify({
        "success": True,
        "dashboard": dict(stats)
    })


# --------------------------------------------------
# ADMIN CUSTOMERS
# --------------------------------------------------

@app.route("/api/admin/customers")
@login_required("admin")
def admin_customers():

    result = query_db(
        """
        SELECT id, username, full_name, phone, email, address, is_active
        FROM users
        WHERE role = 'customer'
        ORDER BY created_at DESC
        """
    )

    return jsonify({
        "success": True,
        "customers": [dict(row) for row in result]
    })


# --------------------------------------------------
# ADMIN FARMERS
# --------------------------------------------------

@app.route("/api/admin/farmers")
@login_required("admin")
def admin_farmers():

    result = query_db(
        """
        SELECT id, username, full_name, phone, email, address, is_active
        FROM users
        WHERE role = 'farmer'
        ORDER BY created_at DESC
        """
    )

    return jsonify({
        "success": True,
        "farmers": [dict(row) for row in result]
    })


# --------------------------------------------------
# ADMIN ALL PRODUCTS
# --------------------------------------------------

@app.route("/api/admin/products")
@login_required("admin")
def admin_products():

    result = query_db(
        """
        SELECT
            p.*,
            u.full_name AS farmer_name
        FROM products p
        LEFT JOIN users u
            ON p.farmer_id = u.id
        ORDER BY p.created_at DESC
        """
    )

    return jsonify({
        "success": True,
        "products": [dict(row) for row in result]
    })


# --------------------------------------------------
# ADMIN ALL ORDERS
# --------------------------------------------------

@app.route("/api/admin/orders")
@login_required("admin")
def admin_orders():

    result = query_db(
        """
        SELECT
            o.*,
            u.full_name AS customer_name,
            u.phone AS customer_phone
        FROM orders o
        JOIN users u
            ON o.customer_id = u.id
        ORDER BY o.created_at DESC
        """
    )

    return jsonify({
        "success": True,
        "orders": [dict(row) for row in result]
    })


@app.route("/api/admin/orders/<int:order_id>", methods=["PUT"])
@login_required("admin")
def admin_update_order(order_id):

    data = request.get_json(silent=True) or {}

    status = str(data.get("status", "")).strip()

    allowed_statuses = (
        "Placed",
        "Preparing",
        "Out for Delivery",
        "Delivered",
        "Cancelled"
    )

    if status not in allowed_statuses:
        return jsonify({
            "success": False,
            "message": "Invalid order status"
        }), 400

    execute_db(
        """
        UPDATE orders
        SET status = ?
        WHERE id = ?
        """,
        (status, order_id)
    )

    return jsonify({
        "success": True,
        "message": "Order status updated"
    })


# --------------------------------------------------
# ADMIN USER ACTIVATION
# --------------------------------------------------

@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@login_required("admin")
def admin_update_user(user_id):

    data = request.get_json(silent=True) or {}

    is_active = 1 if data.get("is_active") else 0

    execute_db(
        """
        UPDATE users
        SET is_active = ?
        WHERE id = ?
          AND role IN ('customer', 'farmer')
        """,
        (is_active, user_id)
    )

    return jsonify({
        "success": True,
        "message": "User status updated"
    })


# --------------------------------------------------
# ERROR HANDLERS
# --------------------------------------------------

@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "message": "Resource not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):

    app.logger.exception("FreshKart server error")

    return jsonify({
        "success": False,
        "message": "Internal server error"
    }), 500


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

with app.app_context():
    init_db()


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
