
import hmac
import os
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import (
    get_db,
    init_app as init_database_app,
    init_db,
)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        DATABASE=os.path.join(
            app.instance_path,
            "freshkart.sqlite3",
        ),
        SECRET_KEY=os.environ.get(
            "FRESHKART_SECRET_KEY",
            "",
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=True,
    )

    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    init_database_app(app)

    with app.app_context():
        init_db()

    # --------------------------------------------------
    # ADMIN AUTHENTICATION HELPERS
    # --------------------------------------------------

    def admin_credentials_configured():
        return bool(
            os.environ.get("FRESHKART_ADMIN_USERNAME")
            and os.environ.get("FRESHKART_ADMIN_PASSWORD")
            and app.config.get("SECRET_KEY")
        )

    def is_admin():
        return session.get("freshkart_admin") is True

    # --------------------------------------------------
    # HOMEPAGE
    # --------------------------------------------------

    @app.get("/")
    def homepage():
        return render_template("index.html")

    # --------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "FreshKart",
        })

    # --------------------------------------------------
    # PUBLIC PRODUCT LIST
    # --------------------------------------------------

    @app.get("/api/products")
    def product_list():
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()

        conditions = [
            "is_available = 1",
            "stock_quantity > 0",
        ]
        parameters = []

        if query:
            conditions.append(
                "instr(lower(name), lower(?)) > 0"
            )
            parameters.append(query)

        if category and category.casefold() != "all":
            conditions.append(
                "category = ? COLLATE NOCASE"
            )
            parameters.append(category)

        rows = get_db().execute(
            """
            SELECT
                id,
                name,
                category,
                price_paise,
                stock_quantity,
                unit,
                description,
                image_url,
                created_at
            FROM products
            WHERE
            """
            + " AND ".join(conditions)
            + " ORDER BY id DESC",
            parameters,
        ).fetchall()

        return jsonify({
            "products": [dict(row) for row in rows],
            "count": len(rows),
        })

    # --------------------------------------------------
    # ADMIN PAGE
    # --------------------------------------------------

    @app.get("/admin")
    def admin_page():
        if not is_admin():
            return redirect(url_for("admin_login"))

        return render_template("admin.html")

    # --------------------------------------------------
    # ADMIN LOGIN
    # --------------------------------------------------

    @app.route(
        "/admin/login",
        methods=["GET", "POST"],
    )
    def admin_login():
        if request.method == "POST":
            if not admin_credentials_configured():
                return render_template(
                    "admin.html",
                    login_mode=True,
                    error=(
                        "Admin access is not configured. "
                        "Set FRESHKART_ADMIN_USERNAME, "
                        "FRESHKART_ADMIN_PASSWORD, and "
                        "FRESHKART_SECRET_KEY in Render."
                    ),
                ), 503

            username = request.form.get(
                "username",
                "",
            )
            password = request.form.get(
                "password",
                "",
            )

            expected_username = os.environ[
                "FRESHKART_ADMIN_USERNAME"
            ]
            expected_password = os.environ[
                "FRESHKART_ADMIN_PASSWORD"
            ]

            username_ok = hmac.compare_digest(
                username,
                expected_username,
            )
            password_ok = hmac.compare_digest(
                password,
                expected_password,
            )

            if username_ok and password_ok:
                session.clear()
                session["freshkart_admin"] = True

                return redirect(url_for("admin_page"))

            return render_template(
                "admin.html",
                login_mode=True,
                error="Incorrect username or password.",
            ), 401

        if not admin_credentials_configured():
            return render_template(
                "admin.html",
                login_mode=True,
                error=(
                    "Admin access is not configured. "
                    "Set FRESHKART_ADMIN_USERNAME, "
                    "FRESHKART_ADMIN_PASSWORD, and "
                    "FRESHKART_SECRET_KEY in Render."
                ),
            ), 503

        if is_admin():
            return redirect(url_for("admin_page"))

        return render_template(
            "admin.html",
            login_mode=True,
        )

    # --------------------------------------------------
    # ADMIN LOGOUT
    # --------------------------------------------------

    @app.post("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    # --------------------------------------------------
    # ADMIN DASHBOARD STATISTICS API
    # --------------------------------------------------

    @app.get("/api/admin/dashboard")
    def admin_dashboard_data():
        if not is_admin():
            return jsonify({
                "error": "Admin login required",
            }), 401

        db = get_db()

        product_stats = db.execute(
            """
            SELECT
                COUNT(*) AS total_products,

                COALESCE(
                    SUM(
                        CASE
                            WHEN is_available = 1
                            AND stock_quantity > 0
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS available_products,

                COALESCE(
                    SUM(
                        CASE
                            WHEN stock_quantity = 0
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS out_of_stock,

                COALESCE(
                    SUM(stock_quantity),
                    0
                ) AS total_stock

            FROM products
            """
        ).fetchone()

        return jsonify({
            "ok": True,
            "products": {
                "total": product_stats["total_products"],
                "available": product_stats[
                    "available_products"
                ],
                "out_of_stock": product_stats[
                    "out_of_stock"
                ],
                "total_stock": product_stats[
                    "total_stock"
                ],
            },
        })

    # --------------------------------------------------
    # ADMIN PRODUCTS: LIST AND CREATE
    # --------------------------------------------------

    @app.route(
        "/api/admin/products",
        methods=["GET", "POST"],
    )
    def admin_products():
        if not is_admin():
            return jsonify({
                "error": "Admin login required",
            }), 401

        db = get_db()

        if request.method == "GET":
            rows = db.execute(
                """
                SELECT
                    id,
                    name,
                    category,
                    price_paise,
                    stock_quantity,
                    unit,
                    description,
                    image_url,
                    is_available
                FROM products
                ORDER BY id DESC
                """
            ).fetchall()

            return jsonify({
                "products": [
                    dict(row) for row in rows
                ],
            })

        data = request.get_json(silent=True) or {}

        try:
            name = str(
                data.get("name", "")
            ).strip()

            category = str(
                data.get("category", "")
            ).strip()

            unit = str(
                data.get("unit", "")
            ).strip()

            description = str(
                data.get("description", "")
            ).strip()

            image_url = str(
                data.get("image_url", "")
            ).strip()

            price_rupees = float(
                data.get("price_rupees", -1)
            )

            stock = int(
                data.get("stock_quantity", -1)
            )

            available = (
                1 if data.get("is_available", True)
                else 0
            )

            if not name or not category or not unit:
                raise ValueError(
                    "Name, category, and unit are required."
                )

            if (
                not __import__("math").isfinite(price_rupees)
                or price_rupees < 0
                or stock < 0
            ):
                raise ValueError(
                    "Price and stock must be valid "
                    "non-negative numbers."
                )

            price_paise = round(price_rupees * 100)

        except (TypeError, ValueError, OverflowError) as exc:
            return jsonify({
                "error": str(exc)
                or "Enter valid product details.",
            }), 400

        db.execute(
            """
            INSERT INTO products (
                name,
                category,
                price_paise,
                stock_quantity,
                unit,
                description,
                image_url,
                is_available
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                category,
                price_paise,
                stock,
                unit,
                description,
                image_url,
                available,
            ),
        )

        db.commit()

        return jsonify({
            "ok": True,
            "message": "Vegetable added successfully.",
        }), 201

    # --------------------------------------------------
    # ADMIN PRODUCTS: UPDATE AND DELETE
    # --------------------------------------------------

    @app.route(
        "/api/admin/products/<int:product_id>",
        methods=["PUT", "DELETE"],
    )
    def admin_product_detail(product_id):
        if not is_admin():
            return jsonify({
                "error": "Admin login required",
            }), 401

        db = get_db()

        existing = db.execute(
            "SELECT id FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        if existing is None:
            return jsonify({
                "error": "Product not found.",
            }), 404

        if request.method == "DELETE":
            db.execute(
                "DELETE FROM products WHERE id = ?",
                (product_id,),
            )
            db.commit()

            return jsonify({
                "ok": True,
                "message": "Product deleted.",
            })

        data = request.get_json(silent=True) or {}

        try:
            name = str(
                data.get("name", "")
            ).strip()

            category = str(
                data.get("category", "")
            ).strip()

            unit = str(
                data.get("unit", "")
            ).strip()

            description = str(
                data.get("description", "")
            ).strip()

            image_url = str(
                data.get("image_url", "")
            ).strip()

            price_rupees = float(
                data.get("price_rupees", -1)
            )

            stock = int(
                data.get("stock_quantity", -1)
            )

            available = (
                1 if data.get("is_available", True)
                else 0
            )

            if not name or not category or not unit:
                raise ValueError(
                    "Name, category, and unit are required."
                )

            if (
                not __import__("math").isfinite(price_rupees)
                or price_rupees < 0
                or stock < 0
            ):
                raise ValueError(
                    "Price and stock must be valid "
                    "non-negative numbers."
                )

            price_paise = round(price_rupees * 100)

        except (TypeError, ValueError, OverflowError) as exc:
            return jsonify({
                "error": str(exc)
                or "Enter valid product details.",
            }), 400

        db.execute(
            """
            UPDATE products
            SET
                name = ?,
                category = ?,
                price_paise = ?,
                stock_quantity = ?,
                unit = ?,
                description = ?,
                image_url = ?,
                is_available = ?
            WHERE id = ?
            """,
            (
                name,
                category,
                price_paise,
                stock,
                unit,
                description,
                image_url,
                available,
                product_id,
            ),
        )

        db.commit()

        return jsonify({
            "ok": True,
            "message": "Product updated.",
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
    )
