"""Flask application factory."""
import os
import structlog
from flask import Flask
from dotenv import load_dotenv

from .extensions import db, migrate, login_manager, csrf, limiter
from config import config_map

load_dotenv()

logger = structlog.get_logger(__name__)


def create_app(config_name: str = "default") -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'production', 'testing'.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load configuration
    cfg = config_map.get(config_name, config_map["default"])
    app.config.from_object(cfg)

    # Initialise extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Configure login manager
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        from .models.user import User
        return db.session.get(User, user_id)

    @app.template_filter("number_format")
    def number_format_filter(value):
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return str(value)

    # Register root landing redirect
    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("web.dashboard"))
        return redirect(url_for("auth.login"))

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Enable proxy headers support behind load balancers (e.g. Render, Nginx)
    if config_name == "production" or os.environ.get("FLASK_ENV") == "production":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    logger.info("app_created", config=config_name)
    return app


def _register_blueprints(app: Flask) -> None:
    """Register all application blueprints."""
    from .auth.routes import auth_bp
    from .tenants.routes import tenants_bp
    from .web.routes import web_bp
    from .api.v1 import api_v1_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tenants_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_v1_bp)


def _register_error_handlers(app: Flask) -> None:
    """Register HTTP error handlers."""
    from flask import render_template, jsonify, request

    @app.errorhandler(400)
    def bad_request(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "bad_request", "message": str(e)}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized", "message": "Authentication required"}), 401
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "forbidden", "message": "Access denied"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found", "message": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "rate_limited", "message": "Too many requests"}), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify({"error": "internal_error", "message": "Internal server error"}), 500
        return render_template("errors/500.html"), 500
