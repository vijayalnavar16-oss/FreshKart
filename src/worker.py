"""Cloudflare Python Worker entry point for FreshKart."""
import os
os.environ["FRESHKART_CLOUDFLARE"] = "1"

from workers import wsgi
from app import app

Default = wsgi.entrypoint(app)
