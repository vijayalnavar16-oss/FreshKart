"""FreshKart – Raitha Market. Stages 1-2: login, dashboards, vegetable and user management."""
import os
import re
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from admin import bp as admin_bp
from auth import current_user, login_required
from database import close_db, get_db, init_db
from i18n import LANGS, t
from products import bp as products_bp
from shop import bp as shop_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),
    MAX_CONTENT_LENGTH=3 * 1024 * 1024,  # products.py enforces the 2 MB photo limit
)
app.jinja_env.globals["t"] = t
app.teardown_appcontext(close_db)
app.register_blueprint(admin_bp)
app.register_blueprint(products_bp)
app.register_blueprint(shop_bp)
init_db()
USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")


@app.context_processor
def inject_globals():
    return {"user": current_user(), "lang": session.get("lang", "kn"), "LANGS": LANGS,
            "cart_count": sum(session.get("cart", {}).values())}


def scalar(sql, params=()):
    return get_db().execute(sql, params).fetchone()[0]


@app.route("/")
def index():
    return redirect(url_for("home") if current_user() else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()[:30]
        password = request.form.get("password", "")
        row = get_db().execute(
            "SELECT id, password_hash FROM users WHERE username = ? AND is_active = 1",
            (username,),
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            lang = session.get("lang", "kn")
            session.clear()  # prevents session fixation
            session["lang"] = lang
            session["user_id"] = row["id"]
            return redirect(url_for("home"))
        flash(t("bad_login"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    lang = session.get("lang", "kn")
    session.clear()
    session["lang"] = lang
    return redirect(url_for("login"))


@app.route("/home")
@login_required()
def home(user):
    # Customers should land directly on the live vegetable catalogue.
    # Admin and farmer dashboards remain unchanged.
    if user["role"] == "customer":
        return redirect(url_for("shop.listing"))

    stats = {}
    recent_orders = []
    if user["role"] == "admin":
        stats = {
            "customers": scalar("SELECT COUNT(*) FROM users WHERE role = 'customer'"),
            "farmers": scalar("SELECT COUNT(*) FROM users WHERE role = 'farmer'"),
            "vegetables": scalar("SELECT COUNT(*) FROM products WHERE deleted = 0"),
            "orders": scalar("SELECT COUNT(*) FROM orders"),
            "sales": scalar("SELECT COALESCE(SUM(total), 0) FROM orders"),
        }
        recent_orders = get_db().execute(
            """SELECT o.id, o.total, o.delivery_date, o.status, o.created_at,
                      u.full_name AS customer_name,
                      (SELECT string_agg(p.name || ' × ' || oi.quantity::text, ', ')
                       FROM order_items oi JOIN products p ON p.id = oi.product_id
                       WHERE oi.order_id = o.id) AS item_summary
               FROM orders o JOIN users u ON u.id = o.customer_id
               ORDER BY o.id DESC LIMIT 5"""
        ).fetchall()
    elif user["role"] == "farmer":
        stats = {
            "vegetables": scalar(
                "SELECT COUNT(*) FROM products WHERE deleted = 0 AND farmer_id = ?", (user["id"],)),
            "low_stock": scalar(
                "SELECT COUNT(*) FROM products WHERE deleted = 0 AND farmer_id = ? AND stock <= 5",
                (user["id"],)),
        }
    return render_template("home.html", stats=stats, recent_orders=recent_orders)


@app.route("/lang/<code>")
def set_lang(code):
    if code in LANGS:
        session["lang"] = code
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)
