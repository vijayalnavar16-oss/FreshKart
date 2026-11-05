"""FreshKart – Raitha Market. Stages 1-2: login, dashboards, vegetable and user management."""
import os
import re
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from admin import bp as admin_bp
from auth import current_user, login_required
from database import close_db, get_db, init_db
from i18n import LANGS, category_label, t
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
app.jinja_env.globals["category_label"] = category_label
app.teardown_appcontext(close_db)
app.register_blueprint(admin_bp)
app.register_blueprint(products_bp)
app.register_blueprint(shop_bp)
init_db()
USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,30}")


@app.context_processor
def inject_globals():
    user = current_user()
    cart_count = 0
    notification_count = 0
    if user:
        db = get_db()
        if user["role"] == "customer":
            cart_count = scalar(
                "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE customer_id = ?",
                (user["id"],),
            )
        notification_count = scalar(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
            (user["id"],),
        )
    return {
        "user": user,
        "lang": session.get("lang", "kn"),
        "LANGS": LANGS,
        "cart_count": cart_count,
        "notification_count": notification_count,
    }


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


@app.route("/notifications")
@login_required()
def notifications(user):
    rows = get_db().execute(
        """SELECT id, message, created_at, read_at FROM notifications
           WHERE user_id = ? ORDER BY id DESC LIMIT 100""",
        (user["id"],),
    ).fetchall()
    return render_template("notifications.html", notifications=rows)


@app.route("/notifications/read", methods=["POST"])
@login_required()
def mark_notifications_read(user):
    db = get_db()
    db.execute(
        "UPDATE notifications SET read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND read_at IS NULL",
        (user["id"],),
    )
    db.commit()
    return redirect(url_for("notifications"))


def ask_groq(question, products):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("The shopping assistant is not configured. Set GROQ_API_KEY in Render.")

    base_url = os.environ.get(
        "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"
    ).strip().rstrip("/")
    parsed_url = urlsplit(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise RuntimeError("GROQ_API_BASE_URL must be a valid HTTPS URL.")

    catalog = [
        {
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "unit": product["unit"],
            "stock": product["stock"],
        }
        for product in products
    ]
    payload = json.dumps({
        "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are FreshKart's shopping assistant. Answer clearly and briefly. "
                    "Only recommend products in the supplied catalog. Do not invent prices, "
                    "stock, delivery promises, or product details. If the catalog lacks a "
                    "requested item, say so. Prices are in Indian rupees."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Current product catalog (JSON): {json.dumps(catalog, ensure_ascii=False)}\n\n"
                    f"Customer question: {question}"
                ),
            },
        ],
        "temperature": 0.3,
        "max_tokens": 400,
    }).encode("utf-8")
    api_request = Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(api_request, timeout=20) as response:
            response_body = response.read(1_000_001)
    except HTTPError as error:
        raise RuntimeError(
            f"Groq request failed with HTTP {error.code}. Check the Groq key, model, and account limits."
        ) from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not reach Groq. Check the service network and try again.") from None

    if len(response_body) > 1_000_000:
        raise RuntimeError("Groq returned an unexpectedly large response.")
    try:
        result = json.loads(response_body)
        answer = result["choices"][0]["message"]["content"].strip()
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
        raise RuntimeError("Groq returned an invalid response. Please try again.") from None
    if not answer:
        raise RuntimeError("Groq returned an empty answer. Please try again.")
    return answer


@app.route("/home")
@login_required()
def home(user):
    return render_template(
        "home.html", **dashboard_data(user), assistant_answer=None
    )


def dashboard_data(user):
    stats = {}
    recent_orders = []
    products = []
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
                      (SELECT group_concat(p.name || ' × ' || oi.quantity, ', ')
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
    elif user["role"] == "customer":
        products = get_db().execute(
            """SELECT p.id, p.name, p.category, p.price, p.unit, p.stock, p.image,
                      u.full_name AS farmer_name
               FROM products p JOIN users u ON u.id = p.farmer_id
               WHERE p.deleted = 0 AND u.is_active = 1
               ORDER BY p.name"""
        ).fetchall()
    return {"stats": stats, "recent_orders": recent_orders, "products": products}


@app.route("/assistant", methods=["POST"])
@login_required("customer")
def shopping_assistant(user):
    question = request.form.get("question", "").strip()
    if not question or len(question) > 500:
        flash("Enter a question up to 500 characters.")
        return redirect(url_for("home"))

    products = get_db().execute(
        """SELECT p.name, p.category, p.price, p.unit, p.stock
           FROM products p JOIN users u ON u.id = p.farmer_id
           WHERE p.deleted = 0 AND p.stock > 0 AND u.is_active = 1
           ORDER BY p.name LIMIT 100"""
    ).fetchall()
    try:
        answer = ask_groq(question, products)
    except RuntimeError as error:
        flash(str(error))
        return redirect(url_for("home"))
    return render_template(
        "home.html", **dashboard_data(user), assistant_answer=answer
    )


@app.route("/lang/<code>")
def set_lang(code):
    if code in LANGS:
        session["lang"] = code
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)
