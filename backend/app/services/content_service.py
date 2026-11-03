"""Content service — source submission, draft management, editing, and versioned approvals."""
import datetime
from datetime import timezone
from typing import Optional

from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models.source import Source, SourceType, SourceStatus
from ..models.post import (
    Post, PostVersion, PostMedia, PostTarget, Approval,
    PostStatus, Platform, PostTargetStatus
)
from ..models.media_asset import MediaAsset
from ..models.social_account import SocialAccount
from .security_service import validate_url_safe


def submit_source(
    tenant_id: str,
    user_id: str,
    source_type: SourceType,
    source_url: Optional[str] = None,
    raw_text: Optional[str] = None,
    headline: Optional[str] = None,
    notes: Optional[str] = None,
    tone_instruction: Optional[str] = None,
) -> tuple[Optional[Source], Optional[str]]:
    """Submit a new story/content source with security validation."""
    if source_type == SourceType.URL:
        if not source_url:
            return None, "Source URL is required for URL submissions."
        is_safe, error = validate_url_safe(source_url)
        if not is_safe:
            return None, f"URL validation failed: {error}"
    elif source_type == SourceType.MANUAL:
        if not raw_text and not headline:
            return None, "Please provide either a topic headline or text."

    source = Source(
        tenant_id=tenant_id,
        created_by=user_id,
        source_type=source_type,
        source_url=source_url,
        raw_text=raw_text,
        headline=headline,
        notes=notes,
        tone_instruction=tone_instruction,
        status=SourceStatus.READY,
    )
    db.session.add(source)
    db.session.commit()
    return source, None


def create_draft_post(
    tenant_id: str,
    user_id: str,
    caption: str = "",
    hashtags: Optional[list[str]] = None,
    source_id: Optional[str] = None,
    media_asset_ids: Optional[list[str]] = None,
    first_comment: Optional[str] = None,
    first_comment_enabled: bool = False,
    social_account_ids: Optional[list[str]] = None,
) -> tuple[Optional[Post], Optional[str]]:
    """Create a new post in DRAFT state with initial versioning."""
    if source_id:
        src = Source.query.filter_by(id=source_id, tenant_id=tenant_id).first()
        if not src:
            return None, "Referenced source not found in this workspace."

    post = Post(
        tenant_id=tenant_id,
        created_by=user_id,
        source_id=source_id,
        caption=caption,
        hashtags_json=hashtags or [],
        first_comment=first_comment,
        first_comment_enabled=first_comment_enabled,
        status=PostStatus.DRAFT,
        content_version=1,
    )
    db.session.add(post)
    db.session.flush()

    # Attach media assets if provided
    if media_asset_ids:
        _attach_media_to_post(post, media_asset_ids, tenant_id)

    # Attach targets if provided
    if social_account_ids:
        _set_post_targets(post, social_account_ids, tenant_id)

    # Create immutable version 1
    content_hash = post.compute_content_hash()
    version = PostVersion(
        tenant_id=tenant_id,
        post_id=post.id,
        version_number=1,
        caption=post.caption,
        hashtags_json=post.hashtags_json,
        first_comment=post.first_comment,
        content_hash=content_hash,
    )
    db.session.add(version)
    db.session.commit()

    return post, None


def update_post_content(
    post_id: str,
    tenant_id: str,
    user_id: str,
    caption: str,
    hashtags: Optional[list[str]] = None,
    media_asset_ids: Optional[list[str]] = None,
    first_comment: Optional[str] = None,
    first_comment_enabled: bool = False,
    social_account_ids: Optional[list[str]] = None,
) -> tuple[Optional[Post], Optional[str]]:
    """Update post content. Invalidates any prior approval and snapshots a new version."""
    post = get_tenant_post(post_id, tenant_id)
    if not post:
        return None, "Post not found."

    # If post was approved, editing invalidates approval
    if post.status == PostStatus.APPROVED:
        post.status = PostStatus.READY_FOR_REVIEW
        post.approved_by = None
        post.approved_at = None
        # Revoke open approvals
        for app in post.approvals:
            if app.revoked_at is None:
                app.revoked_at = datetime.datetime.now(timezone.utc)

    post.caption = caption
    post.hashtags_json = hashtags or []
    post.first_comment = first_comment
    post.first_comment_enabled = first_comment_enabled
    post.content_version += 1

    # Update media attachments
    if media_asset_ids is not None:
        PostMedia.query.filter_by(post_id=post.id).delete()
        _attach_media_to_post(post, media_asset_ids, tenant_id)

    # Update targets
    if social_account_ids is not None:
        PostTarget.query.filter_by(post_id=post.id).delete()
        _set_post_targets(post, social_account_ids, tenant_id)

    # Snapshot new immutable PostVersion
    content_hash = post.compute_content_hash()
    new_version = PostVersion(
        tenant_id=tenant_id,
        post_id=post.id,
        version_number=post.content_version,
        caption=post.caption,
        hashtags_json=post.hashtags_json,
        first_comment=post.first_comment,
        content_hash=content_hash,
    )
    db.session.add(new_version)
    db.session.commit()

    return post, None


def approve_post_version(
    post_id: str,
    tenant_id: str,
    user_id: str,
    target_version_number: Optional[int] = None,
) -> tuple[Optional[Approval], Optional[str]]:
    """Approve a specific version of a post. Approval locks that exact content version."""
    post = get_tenant_post(post_id, tenant_id)
    if not post:
        return None, "Post not found."

    # Locate version to approve (default to current version)
    v_num = target_version_number or post.content_version
    version = PostVersion.query.filter_by(post_id=post.id, version_number=v_num).first()
    if not version:
        return None, f"Version {v_num} does not exist for this post."

    # Verify content hasn't changed since version was captured
    if version.version_number == post.content_version:
        current_hash = post.compute_content_hash()
        if current_hash != version.content_hash:
            return None, "Content has been altered since version was generated."

    approval = Approval(
        tenant_id=tenant_id,
        post_id=post.id,
        post_version_id=version.id,
        approved_by=user_id,
    )
    db.session.add(approval)

    post.status = PostStatus.APPROVED
    post.approved_by = user_id
    post.approved_at = datetime.datetime.now(timezone.utc)
    db.session.commit()

    return approval, None


def get_tenant_post(post_id: str, tenant_id: str) -> Optional[Post]:
    """Retrieve a post strictly scoped to the tenant, including media links and targets."""
    return (
        Post.query
        .options(
            joinedload(Post.media_links).joinedload(PostMedia.media_asset),
            joinedload(Post.targets).joinedload(PostTarget.social_account),
            joinedload(Post.versions),
        )
        .filter_by(id=post_id, tenant_id=tenant_id)
        .first()
    )


def list_tenant_posts(
    tenant_id: str,
    status: Optional[PostStatus] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Post], int]:
    """List posts for a workspace with status filtering and pagination."""
    query = (
        Post.query
        .options(
            joinedload(Post.media_links).joinedload(PostMedia.media_asset),
            joinedload(Post.targets),
        )
        .filter_by(tenant_id=tenant_id)
    )

    if status:
        query = query.filter_by(status=status)

    if search:
        query = query.filter(Post.caption.ilike(f"%{search.strip()}%"))

    query = query.order_by(Post.created_at.desc())
    total = query.count()
    posts = query.offset((page - 1) * per_page).limit(per_page).all()
    return posts, total


def _attach_media_to_post(post: Post, media_asset_ids: list[str], tenant_id: str) -> None:
    for idx, mid in enumerate(media_asset_ids):
        asset = MediaAsset.query.filter_by(id=mid, tenant_id=tenant_id).first()
        if asset:
            pm = PostMedia(
                tenant_id=tenant_id,
                post_id=post.id,
                media_asset_id=asset.id,
                position=idx,
            )
            db.session.add(pm)


def _set_post_targets(post: Post, social_account_ids: list[str], tenant_id: str) -> None:
    for sa_id in social_account_ids:
        acc = SocialAccount.query.filter_by(id=sa_id, tenant_id=tenant_id).first()
        if acc:
            pt = PostTarget(
                tenant_id=tenant_id,
                post_id=post.id,
                social_account_id=acc.id,
                platform=acc.platform,
                status=PostTargetStatus.PENDING,
            )
            db.session.add(pt)

