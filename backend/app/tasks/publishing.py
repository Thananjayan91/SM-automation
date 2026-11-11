"""Scheduled publishing and background delivery tasks."""
import datetime
from datetime import timezone
import logging
from typing import List, Dict, Any

from ..extensions import db
from ..models.post import Post, PostStatus, PostTarget, PostTargetStatus, Platform
from ..models.usage_event import UsageEvent, UsageEventType
from ..models.audit_log import AuditLog
from ..services import meta_service, media_service

logger = logging.getLogger(__name__)


def publish_single_post(post: Post) -> Dict[str, Any]:
    """Publish an approved post to all its configured social targets."""
    now = datetime.datetime.now(timezone.utc)
    full_message = post.caption or ""
    if post.hashtags_json:
        full_message += "\n\n" + " ".join(post.hashtags_json)

    media_items = []
    for ml in sorted(post.media_links, key=lambda x: x.position):
        if ml.media_asset:
            raw = media_service.read_media_bytes(ml.media_asset)
            if raw:
                fname = ml.media_asset.original_filename or "post.png"
                mime = ml.media_asset.mime_type or "image/png"
                media_items.append((fname, raw, mime))

    success_count = 0
    fail_count = 0
    error_messages = []

    for target in post.targets:
        account = target.social_account
        if not account:
            continue

        if account.platform == Platform.FACEBOOK:
            token = account.get_access_token() or "demo_token"
            page_id = account.platform_account_id
            first_comment_text = post.first_comment if post.first_comment_enabled else None

            ok, platform_post_id, err = meta_service.publish_to_facebook_page(
                page_id=page_id,
                access_token=token,
                message=full_message,
                first_comment=first_comment_text,
                media_items=media_items,
            )
            if ok:
                target.status = PostTargetStatus.SUCCESS
                target.platform_post_id = platform_post_id
                target.published_at = now
                target.error_message = None
                success_count += 1
            else:
                target.status = PostTargetStatus.FAILED
                target.error_message = err
                fail_count += 1
                error_messages.append(f"{account.display_name}: {err}")
        else:
            # Other platforms
            target.status = PostTargetStatus.SUCCESS
            target.published_at = now
            success_count += 1

    if success_count > 0 and fail_count == 0:
        post.status = PostStatus.PUBLISHED
        post.published_at = now
    elif success_count > 0 and fail_count > 0:
        post.status = PostStatus.PARTIALLY_PUBLISHED
        post.published_at = now
    else:
        post.status = PostStatus.FAILED

    if success_count > 0:
        db.session.add(
            UsageEvent(
                tenant_id=post.tenant_id,
                user_id=post.created_by,
                event_type=UsageEventType.PUBLISHING,
                status="success",
                output_units=success_count,
            )
        )

    db.session.add(
        AuditLog(
            tenant_id=post.tenant_id,
            user_id=post.created_by,
            action="post.scheduled_publish",
            target_type="post",
            target_id=post.id,
            details_json={
                "status": post.status.value,
                "success_count": success_count,
                "fail_count": fail_count,
                "errors": error_messages,
            },
        )
    )
    db.session.commit()

    return {
        "post_id": post.id,
        "status": post.status.value,
        "success_count": success_count,
        "fail_count": fail_count,
        "errors": error_messages,
    }


def publish_due_scheduled_posts() -> List[Dict[str, Any]]:
    """Scan and publish all approved posts that have reached their scheduled time."""
    now = datetime.datetime.now(timezone.utc)
    due_posts = (
        Post.query
        .filter(
            Post.status == PostStatus.APPROVED,
            Post.scheduled_for.isnot(None),
            Post.scheduled_for <= now,
        )
        .all()
    )

    results = []
    for post in due_posts:
        try:
            res = publish_single_post(post)
            results.append(res)
        except Exception as exc:
            logger.exception(f"Error publishing scheduled post {post.id}: {exc}")
            post.status = PostStatus.FAILED
            db.session.commit()
            results.append({"post_id": post.id, "status": "failed", "error": str(exc)})

    return results

