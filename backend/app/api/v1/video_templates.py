"""REST API — Video Text Overlay Template Endpoints."""
import logging
from flask import request, jsonify, session
from flask_login import login_required, current_user

from . import api_v1_bp
from ...models.video_template import VideoTemplate
from ...extensions import db, limiter
from ...services import permission_service
from ...services.video_text_renderer import SYSTEM_PRESET_TEMPLATES

logger = logging.getLogger(__name__)


def _get_active_tenant_id() -> tuple[str | None, str | None]:
    """Retrieve active tenant ID from session or X-Tenant-ID header, verifying membership."""
    tenant_id = session.get("active_tenant_id") or request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, "No active workspace selected. Set active workspace or pass X-Tenant-ID header."

    membership = permission_service.get_membership(current_user.id, tenant_id)
    if not membership:
        return None, "Access denied to the specified workspace."
    return tenant_id, None


@api_v1_bp.route("/video/templates", methods=["GET"])
@login_required
def api_list_video_templates():
    """List system preset templates plus user saved templates for the active workspace."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    # Fetch custom user templates from database
    user_templates: list[VideoTemplate] = []
    try:
        user_templates = (
            VideoTemplate.query.filter_by(tenant_id=tenant_id)
            .order_by(VideoTemplate.created_at.desc())
            .all()
        )
    except Exception as e:
        logger.warning(f"Error querying video templates from DB: {e}")

    # Combine system presets + user templates
    templates = list(SYSTEM_PRESET_TEMPLATES)
    for ut in user_templates:
        templates.append(ut.to_dict())

    return jsonify({"templates": templates})


@api_v1_bp.route("/video/templates", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_create_video_template():
    """Save a new custom text overlay styling template."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "validation_error", "message": "Template name is required."}), 400

    config = data.get("config") or {}
    if not isinstance(config, dict) or len(config) == 0:
        return jsonify({"error": "validation_error", "message": "Template configuration is required."}), 400

    template = VideoTemplate(
        tenant_id=tenant_id,
        created_by=current_user.id,
        name=name,
        description=data.get("description"),
        is_preset=False,
        config_json=config,
        thumbnail_url=data.get("thumbnail_url"),
    )

    db.session.add(template)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving video template: {e}")
        return jsonify({"error": "db_error", "message": "Failed to save template."}), 500

    return jsonify({"success": True, "template": template.to_dict()}), 201


@api_v1_bp.route("/video/templates/<template_id>", methods=["GET"])
@login_required
def api_get_video_template(template_id: str):
    """Retrieve details of a single template by ID."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    # Check system presets first
    for p in SYSTEM_PRESET_TEMPLATES:
        if p["id"] == template_id:
            return jsonify({"template": p})

    template = VideoTemplate.query.filter_by(id=template_id, tenant_id=tenant_id).first()
    if not template:
        return jsonify({"error": "not_found", "message": "Template not found."}), 404

    return jsonify({"template": template.to_dict()})


@api_v1_bp.route("/video/templates/<template_id>", methods=["PATCH"])
@login_required
def api_update_video_template(template_id: str):
    """Update a custom user template."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    # Check if attempting to modify a preset
    for p in SYSTEM_PRESET_TEMPLATES:
        if p["id"] == template_id:
            return jsonify({"error": "forbidden", "message": "System preset templates cannot be modified."}), 403

    template = VideoTemplate.query.filter_by(id=template_id, tenant_id=tenant_id).first()
    if not template:
        return jsonify({"error": "not_found", "message": "Template not found."}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = str(data["name"]).strip()
        if name:
            template.name = name
    if "description" in data:
        template.description = data["description"]
    if "config" in data and isinstance(data["config"], dict):
        template.config_json = data["config"]

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating video template: {e}")
        return jsonify({"error": "db_error", "message": "Failed to update template."}), 500

    return jsonify({"success": True, "template": template.to_dict()})


@api_v1_bp.route("/video/templates/<template_id>", methods=["DELETE"])
@login_required
def api_delete_video_template(template_id: str):
    """Delete a custom user template."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    # Check if attempting to delete a preset
    for p in SYSTEM_PRESET_TEMPLATES:
        if p["id"] == template_id:
            return jsonify({"error": "forbidden", "message": "System preset templates cannot be deleted."}), 403

    template = VideoTemplate.query.filter_by(id=template_id, tenant_id=tenant_id).first()
    if not template:
        return jsonify({"error": "not_found", "message": "Template not found."}), 404

    try:
        db.session.delete(template)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting video template: {e}")
        return jsonify({"error": "db_error", "message": "Failed to delete template."}), 500

    return jsonify({"success": True})
