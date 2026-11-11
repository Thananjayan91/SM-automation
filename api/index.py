"""Vercel Serverless WSGI Entry Point."""
import os
import sys
import traceback

# Ensure backend directory is on sys.path so 'app' and 'config' are importable
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
for path in (BACKEND_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

# Force production config on Vercel unless explicitly overridden
os.environ.setdefault("FLASK_ENV", "production")

try:
    from app import create_app  # noqa: E402
    app = create_app(os.environ.get("FLASK_ENV", "production"))
except Exception as startup_exc:
    traceback.print_exc()
    from flask import Flask, jsonify
    _err_msg = f"{type(startup_exc).__name__}: {startup_exc}"
    _err_trace = traceback.format_exc()
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _startup_error(path):
        return jsonify({
            "error": "startup_failed",
            "message": _err_msg,
            "sys_path": sys.path[:4],
            "backend_exists": os.path.isdir(BACKEND_DIR),
        }), 500
