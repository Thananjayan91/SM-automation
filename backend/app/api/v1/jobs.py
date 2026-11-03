"""REST API — AI Generation jobs and async pipeline execution."""
from flask import request, jsonify, session
from flask_login import login_required, current_user

from . import api_v1_bp
from ...extensions import db, limiter
from ...models.research import GenerationJob, JobStatus, JobStep
from ...models.source import Source, SourceType
from ...services import permission_service
from ...tasks import dispatch_generation_job


def _get_active_tenant_id() -> tuple[str | None, str | None]:
    """Retrieve active tenant ID from session or X-Tenant-ID header, verifying membership."""
    tenant_id = session.get("active_tenant_id") or request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, "No active workspace selected. Set active workspace or pass X-Tenant-ID header."

    membership = permission_service.get_membership(current_user.id, tenant_id)
    if not membership:
        return None, "Access denied to the specified workspace."
    return tenant_id, None


@api_v1_bp.route("/posts/generate", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def api_generate_post():
    """Trigger the end-to-end AI generation pipeline (research, caption, hashtags, banner)."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.create"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    data = request.get_json(silent=True) or {}
    source_id = data.get("source_id")
    topic = data.get("topic")
    post_id = data.get("post_id")

    # If topic is passed directly without an existing source, create a source record
    if topic and not source_id:
        source = Source(
            tenant_id=tenant_id,
            source_type=SourceType.MANUAL,
            headline=topic[:250],
            raw_text=topic,
        )
        db.session.add(source)
        db.session.flush()
        source_id = source.id

    job = GenerationJob(
        tenant_id=tenant_id,
        user_id=current_user.id,
        source_id=source_id,
        post_id=post_id,
        status=JobStatus.PENDING,
        current_step=JobStep.EXTRACTING,
        progress_pct=10,
    )
    db.session.add(job)
    db.session.commit()

    # Trigger async dispatch or inline execution
    dispatch_generation_job(job.id, async_mode=True)

    return jsonify(job.to_dict()), 202


@api_v1_bp.route("/jobs/<job_id>", methods=["GET"])
@login_required
def api_get_job_status(job_id: str):
    """Poll generation job status, progress percentage, and resulting post ID."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    job = db.session.get(GenerationJob, job_id)
    if not job or job.tenant_id != tenant_id:
        return jsonify({"error": "not_found", "message": "Generation job not found"}), 404

    return jsonify(job.to_dict()), 200


@api_v1_bp.route("/jobs/<job_id>/retry", methods=["POST"])
@login_required
def api_retry_job(job_id: str):
    """Retry a failed generation job."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.create"):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    job = db.session.get(GenerationJob, job_id)
    if not job or job.tenant_id != tenant_id:
        return jsonify({"error": "not_found", "message": "Generation job not found"}), 404

    if job.attempt_count >= job.max_attempts:
        return jsonify({"error": "max_retries_exceeded", "message": "Max retry attempts reached"}), 400

    job.attempt_count += 1
    job.status = JobStatus.PENDING
    job.error_message = None
    job.error_code = None
    job.progress_pct = 10
    db.session.commit()

    dispatch_generation_job(job.id, async_mode=True)
    return jsonify(job.to_dict()), 202


@api_v1_bp.route("/cron/publish-scheduled", methods=["POST", "GET"])
@limiter.limit("60 per hour")
def api_cron_publish_scheduled():
    """Endpoint for scheduled cron triggers (e.g. Render Cron, cron-job.org).

    Protected via X-Cron-Secret header matching CRON_SECRET or PLATFORM_ADMIN_SECRET.
    """
    import os
    from ...tasks.publishing import publish_due_scheduled_posts
    secret = request.headers.get("X-Cron-Secret") or request.args.get("secret")
    expected = os.environ.get("CRON_SECRET") or os.environ.get("PLATFORM_ADMIN_SECRET")

    if expected and secret != expected:
        return jsonify({"error": "unauthorized", "message": "Invalid cron secret"}), 401

    results = publish_due_scheduled_posts()
    return jsonify({
        "status": "success",
        "processed_count": len(results),
        "results": results,
    }), 200

