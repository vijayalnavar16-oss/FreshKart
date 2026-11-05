"""Admin user management: create customer and farmer accounts, search, activate or deactivate."""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from auth import login_required
from database import IntegrityError, get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")
USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")
PHONE_RE = re.compile(r"\+91[6-9][0-9]{9}")
CREATABLE_ROLES = ("customer", "farmer")


@bp.route("/users", methods=["GET", "POST"])
@login_required("admin")
def users(admin):
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            create_account(db)
        elif action == "toggle":
            toggle_account(db, admin)
        elif action == "update_phone":
            update_customer_phone(db)
        elif action == "reset_customer_password":
            reset_customer_password(db)
        return redirect(url_for("admin.users"))

    q = request.args.get("q", "").strip()[:50]
    rows = db.execute(
        """SELECT id, username, role, full_name, phone_number, is_active FROM users
           WHERE role != 'admin' AND (username LIKE ? OR full_name LIKE ?)
           ORDER BY id DESC""",
        (f"%{q}%", f"%{q}%"),
    ).fetchall()
    return render_template("admin_users.html", users=rows, q=q)


@bp.route("/orders")
@login_required("admin")
def orders(admin):
    db = get_db()
    rows = db.execute(
        """SELECT o.id, o.total, o.address, o.delivery_date,
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
    return render_template("admin_orders.html", orders=rows, order_items=order_items)


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
    if cur.rowcount:
        customer = db.execute(
            "SELECT customer_id FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        db.execute(
            "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
            (customer["customer_id"], f"Order #{order_id} was confirmed."),
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
    customer = db.execute(
        "SELECT customer_id FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    db.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
        (customer["customer_id"], f"Order #{order_id} was cancelled."),
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
    phone_number = request.form.get("phone_number", "").strip()

    if not USERNAME_RE.fullmatch(username):
        flash("Username must be 3-30 letters, numbers or underscores.")
        return
    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return
    if role not in CREATABLE_ROLES or not full_name:
        flash("Choose a role and enter a full name.")
        return
    if role == "customer" and not phone_number:
        flash("Enter a mobile number for the customer account.")
        return
    if phone_number and not PHONE_RE.fullmatch(phone_number):
        flash("Enter an Indian mobile number in +91XXXXXXXXXX format.")
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
    except IntegrityError:
        flash("That username already exists.")
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
    phone_number = request.form.get("phone_number", "").strip()
    user = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'customer'", (user_id,)
    ).fetchone()
    if user is None:
        flash("Customer not found.")
        return
    if not PHONE_RE.fullmatch(phone_number):
        flash("Enter an Indian mobile number in +91XXXXXXXXXX format.")
        return
    try:
        db.execute(
            "UPDATE users SET phone_number = ? WHERE id = ?", (phone_number, user_id)
        )
        db.commit()
    except IntegrityError:
        flash("That mobile number is already assigned to another account.")
        return
    flash("Customer mobile number updated.")


def reset_customer_password(db):
    try:
        user_id = int(request.form.get("user_id", ""))
    except ValueError:
        flash("Invalid customer.")
        return
    password = request.form.get("password", "")
    customer = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'customer'", (user_id,)
    ).fetchone()
    if customer is None:
        flash("Customer not found.")
        return
    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(password), user_id),
    )
    db.commit()
    flash("Customer password updated.")
