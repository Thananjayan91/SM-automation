"""Vercel Serverless WSGI Entry Point."""
import os
import sys

# Ensure backend directory is on sys.path so 'app' and 'config' are importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Force production config on Vercel unless explicitly overridden
os.environ.setdefault("FLASK_ENV", "production")

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_ENV", "production"))
