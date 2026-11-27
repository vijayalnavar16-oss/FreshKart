"""Cloudflare Python Worker entry point for the FreshKart Flask application.

The app remains in app.py so the same Flask routes and templates can be tested
locally before the Cloudflare cutover.
"""
from workers import wsgi
from app import app

Default = wsgi.entrypoint(app)
