"""WSGI entry point. Run with: gunicorn wsgi:application"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

application = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", 5000)))
    application.run(host=host, port=port, debug=True)
