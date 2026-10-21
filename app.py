import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from database import get_db, init_app as init_database_app, init_db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "freshkart.sqlite3"),
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_database_app(app)
    with app.app_context():
        init_db()

    @app.get("/")
    def homepage():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "FreshKart"})

    @app.get("/api/products")
    def product_list():
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        conditions = ["is_available = 1", "stock_quantity > 0"]
        parameters = []

        if query:
            conditions.append("instr(lower(name), lower(?)) > 0")
            parameters.append(query)
        if category and category.casefold() != "all":
            conditions.append("category = ? COLLATE NOCASE")
            parameters.append(category)

        rows = get_db().execute(
            "SELECT id, name, category, price_paise, stock_quantity, unit, "
            "description, image_url, created_at "
            "FROM products WHERE " + " AND ".join(conditions) +
            " ORDER BY id DESC",
            parameters,
        ).fetchall()

        return jsonify({"products": [dict(row) for row in rows], "count": len(rows)})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)