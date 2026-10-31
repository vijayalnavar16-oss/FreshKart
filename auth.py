"""Shared login helpers: find the signed-in user and protect routes by role."""
from functools import wraps

from flask import abort, redirect, session, url_for

from database import get_db


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return get_db().execute(
        "SELECT id, username, role, full_name, phone_number FROM users WHERE id = ? AND is_active = 1",
        (uid,),
    ).fetchone()


def login_required(*roles):
    """Send anonymous users to login. Return 403 for roles not allowed on a route."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login"))
            if roles and user["role"] not in roles:
                abort(403)
            return view(user, *args, **kwargs)
        return wrapper
    return decorator
