"""REST API — Content management: sources, media uploads, and posts."""
from flask import request, jsonify, session
from flask_login import login_required, current_user

from . import api_v1_bp
from ...models.source import SourceType, SourceStatus
from ...models.post import PostStatus
from ...models.media_asset import MediaSourceType
from ...services import content_service, media_service, permission_service
from ...extensions import limiter


def _get_active_tenant_id() -> tuple[str | None, str | None]:
    """Retrieve active tenant ID from session or X-Tenant-ID header, verifying membership."""
    tenant_id = session.get("active_tenant_id") or request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, "No active workspace selected. Set active workspace or pass X-Tenant-ID header."

    membership = permission_service.get_membership(current_user.id, tenant_id)
    if not membership:
        return None, "Access denied to the specified workspace."
    return tenant_id, None


# ── Sources ──────────────────────────────────────────────────────────────────

@api_v1_bp.route("/sources", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_submit_source():
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.create"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    source_type_str = data.get("source_type", "manual")
    try:
        source_type = SourceType(source_type_str)
    except ValueError:
        return jsonify({"error": "validation_error", "message": f"Invalid source_type: {source_type_str}"}), 400

    source, error = content_service.submit_source(
        tenant_id=tenant_id,
        user_id=current_user.id,
        source_type=source_type,
        source_url=data.get("source_url"),
        raw_text=data.get("raw_text"),
        headline=data.get("headline"),
        notes=data.get("notes"),
        tone_instruction=data.get("tone_instruction"),
    )
    if error:
        return jsonify({"error": "submission_failed", "message": error}), 422

    return jsonify({
        "id": source.id,
        "source_type": source.source_type.value,
        "source_url": source.source_url,
        "headline": source.headline,
        "status": source.status.value,
        "created_at": source.created_at.isoformat(),
    }), 201


# ── Media ────────────────────────────────────────────────────────────────────

@api_v1_bp.route("/media/uploads", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_upload_media():
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "media.upload"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    if "file" not in request.files:
        return jsonify({"error": "validation_error", "message": "File part is required."}), 400

    file_storage = request.files["file"]
    notes = request.form.get("notes")
    labels = [l.strip() for l in request.form.get("labels", "").split(",") if l.strip()]

    asset, error = media_service.save_media_file(
        file_storage=file_storage,
        tenant_id=tenant_id,
        user_id=current_user.id,
        source_type=MediaSourceType.UPLOADED,
        labels=labels,
        notes=notes,
    )
    if error:
        return jsonify({"error": "upload_failed", "message": error}), 422

    return jsonify({
        "id": asset.id,
        "original_filename": asset.original_filename,
        "storage_url": asset.storage_url,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "width": asset.width,
        "height": asset.height,
        "created_at": asset.created_at.isoformat(),
    }), 201


@api_v1_bp.route("/media", methods=["GET"])
@login_required
def api_list_media():
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    search = request.args.get("search")
    label = request.args.get("label")
    page = request.args.get("page", 1, type=int)

    assets, total = media_service.get_tenant_media(tenant_id, label=label, search=search, page=page)
    return jsonify({
        "total": total,
        "page": page,
        "media": [
            {
                "id": a.id,
                "original_filename": a.original_filename,
                "storage_url": a.storage_url,
                "mime_type": a.mime_type,
                "size_bytes": a.size_bytes,
                "width": a.width,
                "height": a.height,
                "source_type": a.source_type.value,
                "labels": a.labels_json,
                "notes": a.notes,
                "created_at": a.created_at.isoformat(),
            }
            for a in assets
        ]
    }), 200


@api_v1_bp.route("/media/<asset_id>", methods=["DELETE"])
@login_required
def api_delete_media(asset_id: str):
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "media.delete"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    success, error = media_service.delete_media_asset(asset_id, tenant_id)
    if not success:
        return jsonify({"error": "delete_failed", "message": error}), 404
    return jsonify({"message": "Media asset deleted successfully"}), 200


# ── Posts ────────────────────────────────────────────────────────────────────

@api_v1_bp.route("/posts", methods=["GET"])
@login_required
def api_list_posts():
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    status_str = request.args.get("status")
    status = None
    if status_str:
        try:
            status = PostStatus(status_str)
        except ValueError:
            pass

    search = request.args.get("search")
    page = request.args.get("page", 1, type=int)

    posts, total = content_service.list_tenant_posts(tenant_id, status=status, search=search, page=page)
    return jsonify({
        "total": total,
        "page": page,
        "posts": [
            {
                "id": p.id,
                "caption": p.caption,
                "hashtags": p.hashtags_json,
                "status": p.status.value,
                "content_version": p.content_version,
                "media_count": len(p.media_links),
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in posts
        ]
    }), 200


@api_v1_bp.route("/posts", methods=["POST"])
@login_required
def api_create_post():
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.create"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    post, error = content_service.create_draft_post(
        tenant_id=tenant_id,
        user_id=current_user.id,
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags", []),
        source_id=data.get("source_id"),
        media_asset_ids=data.get("media_asset_ids", []),
        first_comment=data.get("first_comment"),
        first_comment_enabled=data.get("first_comment_enabled", False),
        social_account_ids=data.get("social_account_ids", []),
    )
    if error:
        return jsonify({"error": "creation_failed", "message": error}), 422

    return jsonify({
        "id": post.id,
        "caption": post.caption,
        "status": post.status.value,
        "content_version": post.content_version,
        "created_at": post.created_at.isoformat(),
    }), 201


@api_v1_bp.route("/posts/<post_id>", methods=["GET"])
@login_required
def api_get_post(post_id: str):
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    post = content_service.get_tenant_post(post_id, tenant_id)
    if not post:
        return jsonify({"error": "not_found", "message": "Post not found"}), 404

    return jsonify({
        "id": post.id,
        "caption": post.caption,
        "hashtags": post.hashtags_json,
        "first_comment": post.first_comment,
        "first_comment_enabled": post.first_comment_enabled,
        "status": post.status.value,
        "content_version": post.content_version,
        "media": [
            {
                "id": ml.media_asset.id,
                "url": ml.media_asset.storage_url,
                "filename": ml.media_asset.original_filename,
                "position": ml.position,
            }
            for ml in post.media_links if ml.media_asset
        ],
        "targets": [
            {
                "id": t.id,
                "platform": t.platform.value,
                "status": t.status.value,
                "display_name": t.social_account.display_name if t.social_account else None,
            }
            for t in post.targets
        ],
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
    }), 200


@api_v1_bp.route("/posts/<post_id>", methods=["PATCH"])
@login_required
def api_update_post(post_id: str):
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.edit"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    post, error = content_service.update_post_content(
        post_id=post_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        caption=data.get("caption", ""),
        hashtags=data.get("hashtags"),
        media_asset_ids=data.get("media_asset_ids"),
        first_comment=data.get("first_comment"),
        first_comment_enabled=data.get("first_comment_enabled", False),
        social_account_ids=data.get("social_account_ids"),
    )
    if error:
        return jsonify({"error": "update_failed", "message": error}), 422

    return jsonify({
        "id": post.id,
        "caption": post.caption,
        "status": post.status.value,
        "content_version": post.content_version,
        "updated_at": post.updated_at.isoformat(),
    }), 200


@api_v1_bp.route("/posts/<post_id>/approve", methods=["POST"])
@login_required
def api_approve_post(post_id: str):
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.approve"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    approval, error = content_service.approve_post_version(
        post_id=post_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_version_number=data.get("version_number"),
    )
    if error:
        return jsonify({"error": "approval_failed", "message": error}), 422

    return jsonify({
        "approval_id": approval.id,
        "post_id": post_id,
        "post_version_id": approval.post_version_id,
        "approved_by": current_user.name,
        "approved_at": approval.approved_at.isoformat(),
    }), 200

