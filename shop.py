"""Customer shopping, checkout, and direct UPI payment handling."""
import base64
import io
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import qrcode
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from auth import login_required
from database import get_db
from products import CATEGORIES

bp = Blueprint("shop", __name__)

IST = ZoneInfo("Asia/Kolkata")  # the store's local time, not the server's UTC clock
DELIVERY_DAYS = {2: "Wednesday", 6: "Sunday"}  # date.weekday(): Mon=0 ... Wed=2 ... Sun=6
DELIVERY_CHARGE = 30.0
PAYMENT_METHODS = {"COD": "Cash on Delivery", "UPI": "Pay directly by UPI"}
UPI_ID = os.environ.get("UPI_ID", "8296863406@ybl").strip()
PHONE_RE = re.compile(r"\+91[6-9][0-9]{9}")
MAX_QTY = 1000


class CheckoutError(Exception):
    pass


def delivery_dates():
    """Wednesdays and Sundays in the next 14 days, starting tomorrow."""
    today = datetime.now(IST).date()
    dates = []
    for offset in range(1, 15):
        d = today + timedelta(days=offset)
        if d.weekday() in DELIVERY_DAYS:
            dates.append((d.isoformat(), DELIVERY_DAYS[d.weekday()]))
    return dates


def _upi_payment_url(order_id, amount):
    if not UPI_ID:
        raise RuntimeError("Set UPI_ID to the store's personal UPI ID.")
    return urlencode({
        "pa": UPI_ID,
        "pn": "FreshKart",
        "am": f"{amount:.2f}",
        "cu": "INR",
        "tn": f"FreshKart order {order_id}",
        "tr": f"freshkart-{order_id}",
    })


def _upi_app_links(order_id, amount):
    params = _upi_payment_url(order_id, amount)
    return [
        {
            "name": "PhonePe",
            "class": "phonepe",
            "mark": "पे",
            "url": f"phonepe://pay?{params}",
        },
        {
            "name": "Paytm",
            "class": "paytm",
            "mark": "Paytm",
            "url": f"paytmmp://pay?{params}",
        },
        {
            "name": "Google Pay",
            "class": "google-pay",
            "mark": "G",
            "url": f"tez://upi/pay?{params}",
        },
        {
            "name": "Other UPI app",
            "class": "other-upi",
            "mark": "UPI",
            "url": f"upi://pay?{params}",
        },
    ]


def _upi_qr_data_url(payment_url):
    from qrcode.image.svg import SvgImage

    image = qrcode.make(payment_url, image_factory=SvgImage)
    output = io.BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def parse_qty(value, minimum=1):
    try:
        qty = int(value)
    except (TypeError, ValueError):
        return None
    return qty if minimum <= qty <= MAX_QTY else None


def get_cart():
    return dict(session.get("cart", {}))


def set_cart(cart):
    session["cart"] = {k: v for k, v in cart.items() if v > 0}


def get_delivery_charge(db):
    """FreshKart currently offers free delivery on every new order."""
    return 0.0


def load_cart_items(db, cart):
    """Return (items, subtotal) for live products only. Prices come from the database."""
    if not cart:
        return [], 0.0
    ids = [int(k) for k in cart]
    marks = ",".join("?" * len(ids))  # only '?' placeholders, values are bound safely
    rows = db.execute(
        f"""SELECT p.id, p.name, p.price, p.unit, p.stock, p.image, u.full_name AS farmer_name
            FROM products p JOIN users u ON u.id = p.farmer_id
            WHERE p.deleted = 0 AND u.is_active = 1 AND p.id IN ({marks})""",
        ids,
    ).fetchall()
    items, subtotal = [], 0.0
    for row in rows:
        qty = cart[str(row["id"])]
        items.append({"product": row, "qty": qty, "line": qty * row["price"]})
        subtotal += qty * row["price"]
    return items, subtotal


@bp.route("/shop")
@login_required("customer")
def listing(user):
    q = request.args.get("q", "").strip()[:60]
    cat = request.args.get("category", "")
    sql = ("SELECT p.id, p.name, p.category, p.price, p.unit, p.stock, p.image, "
           "u.full_name AS farmer_name FROM products p JOIN users u ON u.id = p.farmer_id "
           "WHERE p.deleted = 0 AND u.is_active = 1")
    params = []
    if q:
        sql += " AND p.name LIKE ?"
        params.append(f"%{q}%")
    if cat in CATEGORIES:
        sql += " AND p.category = ?"
        params.append(cat)
    rows = get_db().execute(sql + " ORDER BY p.name", params).fetchall()
    return render_template("shop.html", products=rows, q=q, cat=cat, categories=CATEGORIES)


@bp.route("/shop/<int:product_id>")
@login_required("customer")
def detail(user, product_id):
    row = get_db().execute(
        """SELECT p.*, u.full_name AS farmer_name, u.address AS farmer_address
           FROM products p JOIN users u ON u.id = p.farmer_id
           WHERE p.id = ? AND p.deleted = 0 AND u.is_active = 1""",
        (product_id,),
    ).fetchone()
    if row is None:
        abort(404)
    return render_template("product_detail.html", p=row)


@bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required("customer")
def add_to_cart(user, product_id):
    p = get_db().execute(
        "SELECT stock FROM products WHERE id = ? AND deleted = 0", (product_id,)).fetchone()
    if p is None:
        abort(404)
    qty = parse_qty(request.form.get("quantity"))
    if qty is None:
        flash("Enter a valid quantity.")
        return redirect(url_for("shop.detail", product_id=product_id))
    cart = get_cart()
    key = str(product_id)
    new_total = cart.get(key, 0) + qty
    if new_total > p["stock"]:
        flash(f"Only {p['stock']} available. You already have {cart.get(key, 0)} in your cart.")
        return redirect(url_for("shop.detail", product_id=product_id))
    cart[key] = new_total
    set_cart(cart)
    flash("Added to cart.")
    return redirect(url_for("shop.cart"))


@bp.route("/cart")
@login_required("customer")
def cart(user):
    db = get_db()
    items, subtotal = load_cart_items(db, get_cart())
    set_cart({str(i["product"]["id"]): i["qty"] for i in items})  # drop removed products
    address = db.execute("SELECT address FROM users WHERE id = ?", (user["id"],)).fetchone()["address"]
    charge = get_delivery_charge(db) if items else 0.0
    return render_template("cart.html", items=items, subtotal=subtotal, charge=charge,
                           total=subtotal + charge, dates=delivery_dates(),
                           methods=PAYMENT_METHODS, address=address)


@bp.route("/cart/update/<int:product_id>", methods=["POST"])
@login_required("customer")
def update_cart(user, product_id):
    cart = get_cart()
    key = str(product_id)
    if key not in cart:
        flash("That item is not in your cart.")
        return redirect(url_for("shop.cart"))
    qty = parse_qty(request.form.get("quantity"), minimum=0)
    if qty is None:
        flash("Enter a valid quantity.")
        return redirect(url_for("shop.cart"))
    if qty == 0:
        cart.pop(key)
    else:
        p = get_db().execute(
            "SELECT stock FROM products WHERE id = ? AND deleted = 0", (product_id,)).fetchone()
        if p is None:
            cart.pop(key)
        elif qty > p["stock"]:
            flash(f"Only {p['stock']} available.")
            return redirect(url_for("shop.cart"))
        else:
            cart[key] = qty
    set_cart(cart)
    flash("Cart updated.")
    return redirect(url_for("shop.cart"))


@bp.route("/checkout", methods=["POST"])
@login_required("customer")
def checkout(user):
    address = request.form.get("address", "").strip()
    phone = user["phone_number"] or ""
    delivery = request.form.get("delivery_date", "")
    payment = request.form.get("payment", "")
    cart = get_cart()

    if not 5 <= len(address) <= 300:
        flash("Enter a delivery address (5 to 300 characters).")
        return redirect(url_for("shop.cart"))
    if not PHONE_RE.fullmatch(phone):
        flash("Ask the store administrator to add a valid mobile number to your account before checkout.")
        return redirect(url_for("shop.cart"))
    if delivery not in {d for d, _ in delivery_dates()}:
        flash("Deliveries are only on Wednesday and Sunday. Choose a listed date.")
        return redirect(url_for("shop.cart"))
    if payment not in PAYMENT_METHODS:
        flash("Choose a payment method.")
        return redirect(url_for("shop.cart"))
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("shop.cart"))

    db = get_db()

    try:
        db.execute("BEGIN IMMEDIATE")  # lock the database while stock is checked and reduced
        delivery_charge = get_delivery_charge(db)
        items, subtotal = load_cart_items(db, cart)
        if len(items) != len(cart):
            raise CheckoutError("Some items in your cart are no longer available.")
        total = subtotal + delivery_charge
        for item in items:
            cur = db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (item["qty"], item["product"]["id"], item["qty"]),
            )
            if cur.rowcount != 1:
                raise CheckoutError(f"Not enough stock for {item['product']['name']}.")
        cur = db.execute(
            """INSERT INTO orders
               (customer_id, total, delivery_charge, address, delivery_date, payment_method,
                customer_phone, payment_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], total, delivery_charge, address, delivery, payment, phone,
             "pending" if payment == "UPI" else "cash_on_delivery"),
        )
        order_id = cur.lastrowid
        for item in items:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (order_id, item["product"]["id"], item["qty"], item["product"]["price"]),
            )
        db.commit()
    except CheckoutError as err:
        db.rollback()
        flash(str(err))
        return redirect(url_for("shop.cart"))
    except Exception:
        db.rollback()
        raise

    session.pop("cart", None)
    if payment == "UPI":
        return redirect(url_for("shop.upi_checkout", order_id=order_id))
    return redirect(url_for("shop.customer_order", order_id=order_id))


@bp.route("/orders/<int:order_id>/payment")
@login_required("customer")
def upi_checkout(user, order_id):
    order = get_db().execute(
        """SELECT id, status, payment_status, total FROM orders
           WHERE id = ? AND customer_id = ? AND payment_method = 'UPI'""",
        (order_id, user["id"]),
    ).fetchone()
    if order is None:
        abort(404)
    if order["payment_status"] == "paid":
        return redirect(url_for("shop.customer_order", order_id=order_id))
    if order["payment_status"] != "pending":
        return redirect(url_for("shop.customer_order", order_id=order_id))
    payment_params = _upi_payment_url(order_id, order["total"])
    payment_url = f"upi://pay?{payment_params}"
    return render_template(
        "upi_payment.html",
        order=order,
        upi_id=UPI_ID,
        payment_url=payment_url,
        payment_apps=_upi_app_links(order_id, order["total"]),
        qr_data_url=_upi_qr_data_url(payment_url),
    )


@bp.route("/orders/<int:order_id>/payment-submitted", methods=["POST"])
@login_required("customer")
def upi_payment_submitted(user, order_id):
    db = get_db()
    cur = db.execute(
        """UPDATE orders SET payment_status = 'verification_requested'
           WHERE id = ? AND customer_id = ? AND payment_method = 'UPI'
             AND payment_status = 'pending' AND status = 'Pending'""",
        (order_id, user["id"]),
    )
    db.commit()
    if cur.rowcount:
        flash("Payment reported. Your order will be confirmed after the store verifies the UPI payment.")
    return redirect(url_for("shop.customer_order", order_id=order_id))


@bp.route("/my-orders")
@login_required("customer")
def customer_orders(user):
    orders = get_db().execute(
        """SELECT id, total, delivery_date, status, payment_method, payment_status, created_at
           FROM orders WHERE customer_id = ? ORDER BY id DESC""",
        (user["id"],),
    ).fetchall()
    return render_template("customer_orders.html", orders=orders)


@bp.route("/orders/<int:order_id>")
@login_required("customer")
def customer_order(user, order_id):
    db = get_db()
    order = db.execute(
        """SELECT id, total, delivery_charge, delivery_date, address, customer_phone,
                  payment_method, payment_status, status, created_at
           FROM orders WHERE id = ? AND customer_id = ?""",
        (order_id, user["id"]),
    ).fetchone()
    if order is None:
        abort(404)
    items = db.execute(
        """SELECT p.name, oi.quantity, oi.price
           FROM order_items oi JOIN products p ON p.id = oi.product_id
           WHERE oi.order_id = ? ORDER BY oi.id""",
        (order_id,),
    ).fetchall()
    return render_template("customer_order.html", order=order, items=items)
