"""REST API — Tenant/workspace management endpoints."""
from flask import request, jsonify
from flask_login import login_required, current_user

from . import api_v1_bp
from ...services import tenant_service, permission_service
from ...extensions import limiter, db


@api_v1_bp.route("/tenants", methods=["GET"])
@login_required
def api_list_tenants():
    tenants = tenant_service.get_user_tenants(current_user.id)
    return jsonify({
        "tenants": [
            {"id": t.id, "name": t.name, "slug": t.slug, "timezone": t.timezone}
            for t in tenants
        ]
    }), 200


@api_v1_bp.route("/tenants", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def api_create_tenant():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "validation_error", "message": "name is required"}), 400

    tenant, error = tenant_service.create_tenant(name=name, owner_user_id=current_user.id)
    if error:
        return jsonify({"error": "creation_failed", "message": error}), 422

    return jsonify({
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "timezone": tenant.timezone,
    }), 201


@api_v1_bp.route("/tenants/<tenant_id>", methods=["GET"])
@login_required
def api_get_tenant(tenant_id: str):
    membership = permission_service.get_membership(current_user.id, tenant_id)
    if not membership:
        return jsonify({"error": "not_found", "message": "Workspace not found"}), 404

    from ...models.tenant import Tenant
    tenant = db.session.get(Tenant, tenant_id)
    return jsonify({
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "timezone": tenant.timezone,
        "brand_name": tenant.brand_name,
        "your_role": membership.role.value,
    }), 200


@api_v1_bp.route("/tenants/<tenant_id>/members", methods=["GET"])
@login_required
def api_get_members(tenant_id: str):
    if not permission_service.has_permission(current_user.id, tenant_id, "members.view"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    members = tenant_service.get_tenant_members(tenant_id)
    return jsonify({
        "members": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "role": m.role.value,
                "joined_at": m.created_at.isoformat(),
            }
            for m in members
        ]
    }), 200


@api_v1_bp.route("/tenants/<tenant_id>/invitations", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def api_invite_member(tenant_id: str):
    if not permission_service.has_permission(current_user.id, tenant_id, "members.invite"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    role_str = data.get("role", "editor")

    from ...models.membership import MembershipRole
    try:
        role = MembershipRole(role_str)
        if role == MembershipRole.OWNER:
            return jsonify({"error": "validation_error", "message": "Cannot invite directly as owner"}), 400
    except ValueError:
        return jsonify({"error": "validation_error", "message": f"Invalid role: {role_str}"}), 400

    invitation, error = tenant_service.invite_member(
        tenant_id=tenant_id,
        email=email,
        role=role,
        invited_by_id=current_user.id,
    )
    if error:
        return jsonify({"error": "invitation_failed", "message": error}), 422

    return jsonify({
        "id": invitation.id,
        "email": invitation.email,
        "role": invitation.role.value,
        "expires_at": invitation.expires_at.isoformat(),
    }), 201
