"""Vercel Serverless WSGI Entry Point."""
import os
import sys
import traceback

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
for path in (BACKEND_DIR, ROOT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("FLASK_ENV", "production")


def _build_app():
    try:
        from app import create_app
        return create_app(os.environ.get("FLASK_ENV", "production"))
    except Exception as exc:
        traceback.print_exc()
        from flask import Flask, jsonify
        err_app = Flask(__name__)
        err_msg = f"{type(exc).__name__}: {exc}"

        @err_app.route("/", defaults={"path": ""})
        @err_app.route("/<path:path>")
        def _startup_error(path):
            return jsonify({
                "error": "startup_failed",
                "message": err_msg,
                "backend_exists": os.path.isdir(BACKEND_DIR),
            }), 500

        return err_app


app = _build_app()
