"""Vegetable management. Admins manage all products; farmers manage only their own."""
import math
import mimetypes
import os
import uuid

from flask import (
    Blueprint, Response, abort, current_app, flash, redirect, render_template,
    request, send_from_directory, url_for,
)

from auth import login_required
from database import get_db

bp = Blueprint("products", __name__, url_prefix="/products")

CATEGORIES = ["Leafy", "Root", "Gourd", "Onion & Garlic", "Other"]
MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_TYPES = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "webp": "webp"}


def upload_dir():
    path = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.root_path, "static", "uploads"
    )
    os.makedirs(path, exist_ok=True)
    return path


def has_upload():
    f = request.files.get("image")
    return f is not None and f.filename != ""


def save_image():
    """Check the real file signature (not just the name) and the size, then save with a random name."""
    f = request.files["image"]
    ext = os.path.splitext(f.filename)[1].lower().lstrip(".")
    kind = IMAGE_TYPES.get(ext)
    data = f.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Photo must be under 2 MB.")
    head = data[:12]
    valid = (
        (kind == "jpg" and head[:3] == b"\xff\xd8\xff")
        or (kind == "png" and head[:8] == b"\x89PNG\r\n\x1a\n")
        or (kind == "webp" and head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )
    if not valid:
        raise ValueError("Photo must be a real JPG, PNG or WebP image.")
    name = f"{uuid.uuid4().hex}.{kind}"
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return name, data, content_type


def remove_image(db, name):
    if name and os.path.basename(name) == name:
        db.execute("DELETE FROM product_images WHERE image_name = ?", (name,))
        path = os.path.join(upload_dir(), name)
        if os.path.isfile(path):
            os.remove(path)


@bp.route("/image/<image_name>")
def image(image_name):
    if os.path.basename(image_name) != image_name:
        abort(404)
    row = get_db().execute(
        "SELECT content, content_type FROM product_images WHERE image_name = ?",
        (image_name,),
    ).fetchone()
    if row is not None:
        return Response(
            row["content"],
            mimetype=row["content_type"],
            headers={"Cache-Control": "public, max-age=86400"},
        )
    path = os.path.join(upload_dir(), image_name)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(upload_dir(), image_name)


def read_form():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "")
    unit = request.form.get("unit", "").strip()
    description = request.form.get("description", "").strip()[:500]
    try:
        price = float(request.form.get("price", ""))
        stock = int(request.form.get("stock", ""))
    except ValueError:
        raise ValueError("Price and stock must be numbers.")
    if not 0 < len(name) <= 80:
        raise ValueError("Enter a name up to 80 characters.")
    if category not in CATEGORIES:
        raise ValueError("Choose a valid category.")
    if not 0 < len(unit) <= 20:
        raise ValueError("Enter a unit such as kg or bunch.")
    if not (math.isfinite(price) and 0 < price <= 100000):
        raise ValueError("Price must be more than 0 and at most 100000.")
    if not 0 <= stock <= 100000:
        raise ValueError("Stock must be between 0 and 100000.")
    return {"name": name, "category": category, "unit": unit,
            "description": description, "price": price, "stock": stock}


def chosen_farmer(db, user):
    """A farmer always owns their own products. An admin must pick an active farmer."""
    if user["role"] == "farmer":
        return user["id"]
    try:
        fid = int(request.form.get("farmer_id", ""))
    except ValueError:
        raise ValueError("Choose a farmer.")
    row = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'farmer' AND is_active = 1", (fid,)).fetchone()
    if row is None:
        raise ValueError("Choose an active farmer.")
    return fid


def farmers_for(db, user):
    if user["role"] != "admin":
        return []
    return db.execute(
        "SELECT id, full_name FROM users WHERE role = 'farmer' AND is_active = 1 ORDER BY full_name"
    ).fetchall()


def owned_product(db, user, product_id):
    p = db.execute("SELECT * FROM products WHERE id = ? AND deleted = 0", (product_id,)).fetchone()
    if p is None:
        abort(404)
    if user["role"] != "admin" and p["farmer_id"] != user["id"]:
        abort(403)
    return p


@bp.route("/")
@login_required("admin", "farmer")
def manage(user):
    db = get_db()
    sql = ("SELECT p.*, u.full_name AS farmer_name FROM products p "
           "JOIN users u ON u.id = p.farmer_id WHERE p.deleted = 0")
    if user["role"] == "admin":
        rows = db.execute(sql + " ORDER BY p.id DESC").fetchall()
    else:
        rows = db.execute(sql + " AND p.farmer_id = ? ORDER BY p.id DESC", (user["id"],)).fetchall()
    return render_template("manage_products.html", products=rows)


@bp.route("/new", methods=["GET", "POST"])
@login_required("admin", "farmer")
def new(user):
    db = get_db()
    if request.method == "POST":
        try:
            data = read_form()
            farmer_id = chosen_farmer(db, user)
            image_data = save_image() if has_upload() else None
            image = image_data[0] if image_data else ""
        except ValueError as err:
            flash(str(err))
            return render_template("product_form.html", product=None, form=request.form,
                                   categories=CATEGORIES, farmers=farmers_for(db, user))
        db.execute(
            """INSERT INTO products (farmer_id, name, category, price, unit, stock, description, image)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (farmer_id, data["name"], data["category"], data["price"], data["unit"],
             data["stock"], data["description"], image),
        )
        if image_data:
            db.execute(
                """INSERT INTO product_images (image_name, content, content_type)
                   VALUES (?, ?, ?)""",
                image_data,
            )
        db.commit()
        flash("Vegetable added.")
        return redirect(url_for("products.manage"))
    return render_template("product_form.html", product=None, form=None,
                           categories=CATEGORIES, farmers=farmers_for(db, user))


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required("admin", "farmer")
def edit(user, product_id):
    db = get_db()
    product = owned_product(db, user, product_id)
    if request.method == "POST":
        try:
            data = read_form()
            image_data = save_image() if has_upload() else None
            image = image_data[0] if image_data else None
        except ValueError as err:
            flash(str(err))
            return render_template("product_form.html", product=product, form=request.form,
                                   categories=CATEGORIES, farmers=[])
        db.execute(
            """UPDATE products SET name = ?, category = ?, price = ?, unit = ?, stock = ?,
               description = ?, image = ? WHERE id = ?""",
            (data["name"], data["category"], data["price"], data["unit"], data["stock"],
             data["description"], image or product["image"], product_id),
        )
        if image_data:
            db.execute(
                """INSERT INTO product_images (image_name, content, content_type)
                   VALUES (?, ?, ?)""",
                image_data,
            )
        db.commit()
        if image:
            remove_image(db, product["image"])
            db.commit()
        flash("Vegetable updated.")
        return redirect(url_for("products.manage"))
    return render_template("product_form.html", product=product, form=None,
                           categories=CATEGORIES, farmers=[])


@bp.route("/<int:product_id>/delete", methods=["POST"])
@login_required("admin", "farmer")
def delete(user, product_id):
    db = get_db()
    owned_product(db, user, product_id)
    # Soft delete: past orders still point at this product, so the row is kept.
    db.execute("UPDATE products SET deleted = 1 WHERE id = ?", (product_id,))
    db.commit()
    flash("Vegetable removed from the store. Past orders are kept.")
    return redirect(url_for("products.manage"))
