"""Admin user management: create customer and farmer accounts, search, activate or deactivate."""
import re
import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from auth import login_required
from database import get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")
USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")
CREATABLE_ROLES = ("customer", "farmer")


def clean_phone(value):
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        return None
    return "+91" + digits


@bp.route("/users", methods=["GET", "POST"])
@login_required("admin")
def users(admin):
    db = get_db()
    role = request.args.get("role", "customer")
    if role not in CREATABLE_ROLES:
        role = "customer"
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            create_account(db)
        elif action == "toggle":
            toggle_account(db, admin)
        elif action == "update_phone":
            update_customer_phone(db)
        return redirect(url_for("admin.users", role=request.form.get("role", role)))

    q = request.args.get("q", "").strip()[:50]
    rows = db.execute(
        """SELECT id, username, role, full_name, phone_number, is_active FROM users
           WHERE role = ? AND (username LIKE ? OR full_name LIKE ?)
           ORDER BY id DESC""",
        (role, f"%{q}%", f"%{q}%"),
    ).fetchall()
    counts = {
        "customer": db.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0],
        "farmer": db.execute("SELECT COUNT(*) FROM users WHERE role='farmer'").fetchone()[0],
    }
    return render_template("admin_users.html", users=rows, q=q, active_role=role, counts=counts)


@bp.route("/orders", methods=["GET", "POST"])
@login_required("admin")
def orders(admin):
    db = get_db()
    if request.method == "POST":
        if request.form.get("action") == "set_free_delivery":
            free_delivery = request.form.get("free_delivery")
            if free_delivery not in ("0", "1"):
                flash("Invalid delivery setting.")
            else:
                db.execute(
                    """INSERT INTO app_settings (key, value) VALUES ('free_delivery', ?)
                       ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                    (free_delivery,),
                )
                db.commit()
                flash("Free delivery enabled for new orders." if free_delivery == "1"
                      else "Delivery charge restored for new orders.")
        return redirect(url_for("admin.orders"))

    setting = db.execute(
        "SELECT value FROM app_settings WHERE key = 'free_delivery'"
    ).fetchone()
    free_delivery = setting is not None and setting["value"] == "1"
    rows = db.execute(
        """SELECT o.id, o.total, o.delivery_charge, o.address, o.delivery_date,
                  o.payment_method, o.payment_status, o.status, o.stock_released, o.created_at,
                  u.username, u.full_name
           FROM orders o JOIN users u ON u.id = o.customer_id
           ORDER BY o.id DESC"""
    ).fetchall()
    order_items = {row["id"]: [] for row in rows}
    if order_items:
        marks = ",".join("?" for _ in order_items)
        items = db.execute(
            f"""SELECT oi.order_id, p.name, oi.quantity, oi.price
                FROM order_items oi JOIN products p ON p.id = oi.product_id
                WHERE oi.order_id IN ({marks})
                ORDER BY oi.order_id DESC, oi.id""",
            tuple(order_items),
        ).fetchall()
        for item in items:
            order_items[item["order_id"]].append(item)
    return render_template("admin_orders.html", orders=rows, order_items=order_items,
                           free_delivery=free_delivery)


@bp.route("/orders/<int:order_id>/verify-upi", methods=["POST"])
@login_required("admin")
def verify_upi_payment(admin, order_id):
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    cur = db.execute(
        """UPDATE orders SET payment_status = 'paid', status = 'Confirmed'
           WHERE id = ? AND payment_method = 'UPI'
             AND payment_status IN ('pending', 'verification_requested')
             AND status = 'Pending' AND stock_released = 0""",
        (order_id,),
    )
    db.commit()
    flash("UPI payment verified and order confirmed." if cur.rowcount
          else "Order cannot be confirmed; check its current payment and order status.")
    return redirect(url_for("admin.orders"))


@bp.route("/orders/<int:order_id>/cancel-upi", methods=["POST"])
@login_required("admin")
def cancel_unpaid_upi_order(admin, order_id):
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    order = db.execute(
        """SELECT payment_status, status, stock_released FROM orders
           WHERE id = ? AND payment_method = 'UPI'""",
        (order_id,),
    ).fetchone()
    if (order is None or order["payment_status"] not in ("pending", "verification_requested")
            or order["status"] != "Pending" or order["stock_released"]):
        db.rollback()
        flash("Order cannot be cancelled; check its current payment and order status.")
        return redirect(url_for("admin.orders"))
    items = db.execute(
        "SELECT product_id, quantity FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()
    for item in items:
        db.execute(
            "UPDATE products SET stock = stock + ? WHERE id = ?",
            (item["quantity"], item["product_id"]),
        )
    db.execute(
        """UPDATE orders SET payment_status = 'cancelled', status = 'Cancelled',
           stock_released = 1 WHERE id = ?""",
        (order_id,),
    )
    db.commit()
    flash("Unpaid UPI order cancelled and reserved stock released.")
    return redirect(url_for("admin.orders"))


def create_account(db):
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "")
    full_name = request.form.get("full_name", "").strip()[:80]
    address = request.form.get("address", "").strip()[:300]
    raw_phone = request.form.get("phone_number", "").strip()

    if not USERNAME_RE.fullmatch(username):
        flash("Username must be 3-30 letters, numbers or underscores.")
        return
    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return
    if role not in CREATABLE_ROLES or not full_name:
        flash("Choose a role and enter a full name.")
        return
    phone_number = clean_phone(raw_phone) if raw_phone else None
    if role == "customer" and not phone_number:
        flash("Enter a valid 10-digit Indian mobile number.")
        return
    if raw_phone and not phone_number:
        flash("Enter a valid 10-digit Indian mobile number.")
        return
    password_hash = generate_password_hash(password)
    try:
        db.execute(
            """INSERT INTO users
               (username, password_hash, role, full_name, address, phone_number)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, password_hash, role, full_name, address, phone_number or None),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("That username or mobile number already exists.")
        return
    flash(f"Created {role} account '{username}'.")


def toggle_account(db, admin):
    try:
        uid = int(request.form.get("user_id", ""))
    except ValueError:
        flash("Invalid user.")
        return
    if uid == admin["id"]:
        flash("You cannot deactivate your own account.")
        return
    cur = db.execute(
        "UPDATE users SET is_active = 1 - is_active WHERE id = ? AND role != 'admin'", (uid,))
    db.commit()
    flash("Account updated." if cur.rowcount else "User not found.")


def update_customer_phone(db):
    try:
        user_id = int(request.form.get("user_id", ""))
    except ValueError:
        flash("Invalid customer.")
        return
    phone_number = clean_phone(request.form.get("phone_number", ""))
    user = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'customer'", (user_id,)
    ).fetchone()
    if user is None:
        flash("Customer not found.")
        return
    if not phone_number:
        flash("Enter a valid 10-digit Indian mobile number.")
        return
    try:
        db.execute(
            "UPDATE users SET phone_number = ? WHERE id = ?", (phone_number, user_id)
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("That mobile number is already assigned to another account.")
        return
    flash("Customer mobile number updated.")
