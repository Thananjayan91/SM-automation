"""REST API — Authentication endpoints for mobile/API clients."""
from flask import request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user

from . import api_v1_bp
from ...services import auth_service, tenant_service
from ...extensions import limiter


@api_v1_bp.route("/auth/register", methods=["POST"])
@limiter.limit("10 per minute")
def api_register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    name = data.get("name", "").strip()

    if not email or not password or not name:
        return jsonify({"error": "validation_error", "message": "email, password, and name are required"}), 400

    user, error = auth_service.register_user(email=email, password=password, name=name)
    if error:
        return jsonify({"error": "registration_failed", "message": error}), 409

    return jsonify({
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at.isoformat(),
    }), 201


@api_v1_bp.route("/auth/login", methods=["POST"])
@limiter.limit("20 per minute")
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    password = data.get("password", "")

    user = auth_service.authenticate_user(email, password)
    if not user:
        return jsonify({"error": "invalid_credentials", "message": "Invalid email or password"}), 401

    login_user(user)
    auth_service.create_web_session(user)
    tenants = tenant_service.get_user_tenants(user.id)

    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        },
        "tenants": [{"id": t.id, "name": t.name, "slug": t.slug} for t in tenants],
    }), 200


@api_v1_bp.route("/auth/logout", methods=["POST"])
@login_required
def api_logout():
    auth_service.logout_user_session(current_user)
    logout_user()
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@api_v1_bp.route("/auth/forgot-password", methods=["POST"])
@limiter.limit("5 per minute")
def api_forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    auth_service.generate_password_reset_token(email)
    return jsonify({"message": "If an account exists for this email, a reset link has been sent."}), 200


@api_v1_bp.route("/me", methods=["GET"])
@login_required
def api_me():
    tenants = tenant_service.get_user_tenants(current_user.id)
    return jsonify({
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_platform_admin": current_user.is_platform_admin,
        },
        "tenants": [{"id": t.id, "name": t.name, "slug": t.slug} for t in tenants],
    }), 200
