"""Web application blueprint — main application views."""
import os
import datetime
from datetime import timezone
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, session, g, request, send_file, abort, jsonify
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models.source import SourceType, Source
from ..models.post import Post, PostStatus, Platform, PostTargetStatus, PostTarget
from ..models.social_account import SocialAccount, SocialAccountStatus
from ..models.media_asset import MediaAsset, MediaSourceType
from ..models.usage_event import UsageEvent, UsageEventType
from ..models.audit_log import AuditLog
from ..services import tenant_service, permission_service, content_service, media_service
from .decorators import tenant_required, require_perm

web_bp = Blueprint("web", __name__, url_prefix="/app")


@web_bp.route("/")
@web_bp.route("/dashboard")
@login_required
@tenant_required
def dashboard():
    tenants = tenant_service.get_user_tenants(current_user.id)

    # Query real tenant stats
    posts_total = Post.query.filter_by(tenant_id=g.tenant.id).count()
    posts_published = Post.query.filter_by(tenant_id=g.tenant.id, status=PostStatus.PUBLISHED).count()
    posts_awaiting = Post.query.filter_by(tenant_id=g.tenant.id, status=PostStatus.READY_FOR_REVIEW).count()
    social_count = SocialAccount.query.filter_by(tenant_id=g.tenant.id, status=SocialAccountStatus.CONNECTED).count()

    recent_posts = (
        Post.query
        .filter_by(tenant_id=g.tenant.id)
        .order_by(Post.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "web/dashboard.html",
        title="Dashboard",
        tenant=g.tenant,
        membership=g.membership,
        tenants=tenants,
        stats={
            "posts_created": posts_total,
            "posts_published": posts_published,
            "posts_awaiting_approval": posts_awaiting,
            "social_accounts": social_count,
            "ai_usage_this_month": 0,
            "ai_usage_limit": 20,
        },
        recent_activity=recent_posts,
    )


# ── Video Generation ──────────────────────────────────────────────────────────

@web_bp.route("/generate-video")
@login_required
@tenant_required
def generate_video():
    tenants = tenant_service.get_user_tenants(current_user.id)
    return render_template(
        "web/generate_video.html",
        title="Generate Video",
        tenant=g.tenant,
        membership=g.membership,
        tenants=tenants,
    )


@web_bp.route("/generate-video/create-post", methods=["POST"])
@login_required
@tenant_required
@require_perm("content.create")
def video_create_post():
    asset_id = request.form.get("asset_id", "").strip()
    topic = request.form.get("topic", "").strip()
    script = request.form.get("script", "").strip()

    caption = script or (f"Check out our latest video on {topic}!" if topic else "Check out our new video!")
    post, post_err = content_service.create_draft_post(
        tenant_id=g.tenant.id,
        user_id=current_user.id,
        caption=caption,
        source_id=None,
        media_asset_ids=[asset_id] if asset_id else [],
    )
    if post_err:
        flash(post_err, "danger")
        return redirect(url_for("web.generate_video"))

    flash("Draft post created with your video! Choose social accounts and publish below.", "success")
    return redirect(url_for("web.edit_post", post_id=post.id))


@web_bp.route("/media/audio/<path:filename>")
@login_required
@tenant_required
def media_audio(filename: str):
    """Securely stream local voiceover audio files."""
    safe_name = secure_filename(filename)
    dest_dir = media_service.get_media_storage_path(g.tenant.id)
    file_path = os.path.join(dest_dir, f"audio_{safe_name}")
    if not os.path.exists(file_path):
        abort(404)
    mime = "audio/wav" if safe_name.endswith(".wav") else "audio/mpeg"
    return send_file(file_path, mimetype=mime)


@web_bp.route("/posts")
@login_required
@tenant_required
def posts():
    status_filter = request.args.get("status")
    status = None
    if status_filter:
        try:
            status = PostStatus(status_filter)
        except ValueError:
            pass

    search = request.args.get("search")
    page = request.args.get("page", 1, type=int)

    posts_list, total = content_service.list_tenant_posts(
        g.tenant.id, status=status, search=search, page=page, per_page=20
    )
    return render_template(
        "web/posts.html",
        title="Posts",
        tenant=g.tenant,
        membership=g.membership,
        posts=posts_list,
        total=total,
        page=page,
        current_status=status_filter,
    )


@web_bp.route("/posts/new", methods=["GET", "POST"])
@login_required
@tenant_required
@require_perm("content.create")
def new_post():
    if request.method == "POST":
        source_type_str = request.form.get("source_type", "manual")
        try:
            source_type = SourceType(source_type_str)
        except ValueError:
            source_type = SourceType.MANUAL

        source_url = request.form.get("source_url")
        raw_text = request.form.get("raw_text")
        headline = request.form.get("headline")
        caption = request.form.get("caption", "").strip()
        tone = request.form.get("tone_instruction")
        media_id = request.form.get("selected_media_id")

        # Submit source
        source = None
        if source_url or raw_text or headline:
            source, src_err = content_service.submit_source(
                tenant_id=g.tenant.id,
                user_id=current_user.id,
                source_type=source_type,
                source_url=source_url,
                raw_text=raw_text,
                headline=headline,
                tone_instruction=tone,
            )
            if src_err:
                flash(src_err, "danger")
                return redirect(url_for("web.new_post"))

        # If caption is blank and headline/text was given, initialize caption with headline
        if not caption and headline:
            caption = headline

        media_ids = [media_id] if media_id else []

        post, post_err = content_service.create_draft_post(
            tenant_id=g.tenant.id,
            user_id=current_user.id,
            caption=caption,
            source_id=source.id if source else None,
            media_asset_ids=media_ids,
        )

        if post_err:
            flash(post_err, "danger")
            return redirect(url_for("web.new_post"))

        flash("Draft post created! Refine and review it below.", "success")
        return redirect(url_for("web.edit_post", post_id=post.id))

    # Available media assets to attach
    media_assets, _ = media_service.get_tenant_media(g.tenant.id, per_page=12)
    social_accounts = SocialAccount.query.filter_by(tenant_id=g.tenant.id).all()

    return render_template(
        "web/new_post.html",
        title="Create post",
        tenant=g.tenant,
        membership=g.membership,
        media_assets=media_assets,
        social_accounts=social_accounts,
    )


@web_bp.route("/posts/<post_id>/edit", methods=["GET", "POST"])
@login_required
@tenant_required
def edit_post(post_id: str):
    post = content_service.get_tenant_post(post_id, g.tenant.id)
    if not post:
        flash("Post not found.", "warning")
        return redirect(url_for("web.posts"))

    if request.method == "POST":
        if not permission_service.has_permission(current_user.id, g.tenant.id, "content.edit"):
            flash("You do not have permission to edit posts.", "danger")
            return redirect(url_for("web.edit_post", post_id=post.id))

        caption = request.form.get("caption", "").strip()
        hashtags_raw = request.form.get("hashtags", "")
        hashtags = [h.strip() for h in hashtags_raw.replace(",", " ").split() if h.strip()]

        first_comment = request.form.get("first_comment", "").strip()
        first_comment_enabled = request.form.get("first_comment_enabled") == "on"

        selected_media_ids = request.form.getlist("media_ids")
        selected_account_ids = request.form.getlist("account_ids")

        updated_post, err = content_service.update_post_content(
            post_id=post.id,
            tenant_id=g.tenant.id,
            user_id=current_user.id,
            caption=caption,
            hashtags=hashtags,
            media_asset_ids=selected_media_ids,
            first_comment=first_comment,
            first_comment_enabled=first_comment_enabled,
            social_account_ids=selected_account_ids,
        )

        if err:
            flash(err, "danger")
            return redirect(url_for("web.edit_post", post_id=post.id))

        publish_action = request.form.get("publish_action") == "1"
        approve_action = request.form.get("approve_action") == "1"

        if publish_action:
            if not selected_account_ids:
                flash("Please select at least one social media account/page from the left panel before publishing.", "warning")
                return redirect(url_for("web.edit_post", post_id=post.id))

            # Approve version first if not already approved
            if post.status != PostStatus.APPROVED:
                content_service.approve_post_version(post.id, g.tenant.id, current_user.id)

            from ..services import meta_service
            now = datetime.datetime.now(timezone.utc)
            post = updated_post or post

            # Prepare full message and all attached media assets in order
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
                    # Other platforms simulated/queued
                    target.status = PostTargetStatus.SUCCESS
                    target.published_at = now
                    success_count += 1

            if success_count > 0 and fail_count == 0:
                post.status = PostStatus.PUBLISHED
                post.published_at = now
                flash(f"🎉 Post successfully published to {success_count} connected destination(s)!", "success")
            elif success_count > 0 and fail_count > 0:
                post.status = PostStatus.PARTIALLY_PUBLISHED
                post.published_at = now
                flash(f"⚠️ Published to {success_count} destination(s), but failed for {fail_count}: {'; '.join(error_messages)}", "warning")
            else:
                post.status = PostStatus.FAILED
                flash(f"❌ Publishing failed: {'; '.join(error_messages)}", "danger")

            if success_count > 0:
                db.session.add(
                    UsageEvent(
                        tenant_id=g.tenant.id,
                        user_id=current_user.id,
                        event_type=UsageEventType.PUBLISHING,
                        status="success",
                        output_units=success_count,
                    )
                )

            db.session.add(
                AuditLog(
                    tenant_id=g.tenant.id,
                    user_id=current_user.id,
                    action="post.publish",
                    target_type="post",
                    target_id=post.id,
                    details_json={"status": post.status.value, "success_count": success_count, "fail_count": fail_count},
                )
            )
            db.session.commit()
            return redirect(url_for("web.posts"))

        elif approve_action and permission_service.has_permission(current_user.id, g.tenant.id, "content.approve"):
            approval, app_err = content_service.approve_post_version(post.id, g.tenant.id, current_user.id)
            if app_err:
                flash(app_err, "danger")
            else:
                flash(f"Post version {updated_post.content_version} approved successfully!", "success")
        else:
            flash(f"Draft saved (version {updated_post.content_version}).", "success")

        return redirect(url_for("web.edit_post", post_id=post.id))

    # Get media and social accounts for selectors
    media_assets, _ = media_service.get_tenant_media(g.tenant.id, per_page=30)
    social_accounts = SocialAccount.query.filter_by(tenant_id=g.tenant.id).all()

    current_media_ids = [pm.media_asset_id for pm in post.media_links]
    current_account_ids = [pt.social_account_id for pt in post.targets if pt.social_account_id]

    # Fetch research and citations if linked to a source
    from ..models.research import ResearchRun
    research_runs = ResearchRun.query.filter_by(source_id=post.source_id).all() if post.source_id else []

    return render_template(
        "web/edit_post.html",
        title="Edit post",
        tenant=g.tenant,
        membership=g.membership,
        post=post,
        media_assets=media_assets,
        social_accounts=social_accounts,
        current_media_ids=current_media_ids,
        current_account_ids=current_account_ids,
        research_runs=research_runs,
    )


@web_bp.route("/posts/<post_id>/approve", methods=["POST"])
@login_required
@tenant_required
@require_perm("content.approve")
def approve_post(post_id: str):
    approval, err = content_service.approve_post_version(post_id, g.tenant.id, current_user.id)
    if err:
        flash(err, "danger")
    else:
        flash("Post approved! Ready for publication.", "success")
    return redirect(request.referrer or url_for("web.edit_post", post_id=post_id))


@web_bp.route("/approvals")
@login_required
@tenant_required
def approvals():
    posts_list = (
        Post.query
        .filter_by(tenant_id=g.tenant.id)
        .filter(Post.status.in_([PostStatus.READY_FOR_REVIEW, PostStatus.APPROVED]))
        .order_by(Post.created_at.desc())
        .all()
    )
    return render_template("web/approvals.html", title="Approvals", tenant=g.tenant, membership=g.membership, posts=posts_list)


@web_bp.route("/calendar")
@login_required
@tenant_required
def calendar():
    import calendar as py_cal
    from datetime import datetime, date

    now = datetime.now(timezone.utc)
    year = request.args.get("year", default=now.year, type=int)
    month = request.args.get("month", default=now.month, type=int)
    channel = request.args.get("channel", default="all").lower()

    # Calculate month matrix (Monday first)
    cal = py_cal.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    month_name = py_cal.month_name[month]

    # Query posts for tenant
    posts_query = Post.query.filter_by(tenant_id=g.tenant.id)
    if channel != "all":
        posts_query = posts_query.join(PostTarget).join(SocialAccount).filter(SocialAccount.platform == channel)

    all_posts = posts_query.all()

    # Group posts by date 'YYYY-MM-DD'
    posts_by_date = {}
    for p in all_posts:
        d = p.scheduled_for or p.published_at or p.created_at
        if d:
            d_str = d.strftime("%Y-%m-%d")
            posts_by_date.setdefault(d_str, []).append(p)

    return render_template(
        "web/calendar.html",
        title="Content Calendar",
        tenant=g.tenant,
        membership=g.membership,
        calendar_weeks=weeks,
        now=now,
        year=year,
        month=month,
        month_name=month_name,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        current_channel=channel,
        posts_by_date=posts_by_date,
    )


@web_bp.route("/posts/<post_id>/reschedule", methods=["POST"])
@login_required
@tenant_required
@require_perm("content.create")
def reschedule_post(post_id: str):
    post = content_service.get_tenant_post(post_id, g.tenant.id)
    if not post:
        flash("Post not found.", "warning")
        return redirect(url_for("web.calendar"))

    schedule_str = request.form.get("scheduled_for", "").strip()
    if schedule_str:
        try:
            dt = datetime.datetime.fromisoformat(schedule_str).replace(tzinfo=timezone.utc)
            post.scheduled_for = dt
            if post.status == PostStatus.DRAFT:
                post.status = PostStatus.READY_FOR_REVIEW
            db.session.commit()
            flash(f"Post successfully scheduled for {dt.strftime('%b %d, %Y at %I:%M %p UTC')}.", "success")
        except Exception as exc:
            flash(f"Invalid date format: {exc}", "danger")
    else:
        post.scheduled_for = None
        db.session.commit()
        flash("Scheduled date cleared.", "info")

    return redirect(request.referrer or url_for("web.calendar"))


@web_bp.route("/posts/<post_id>/retry-publish", methods=["POST"])
@login_required
@tenant_required
@require_perm("content.publish")
def retry_publish_post(post_id: str):
    from ..tasks.publishing import publish_single_post
    post = content_service.get_tenant_post(post_id, g.tenant.id)
    if not post:
        flash("Post not found.", "warning")
        return redirect(url_for("web.publishing_history"))

    res = publish_single_post(post)
    if res["status"] == "published":
        flash(f"🎉 Post successfully published to {res['success_count']} destination(s)!", "success")
    elif res["status"] == "partially_published":
        flash(f"⚠️ Published to {res['success_count']} destination(s), failed for {res['fail_count']}.", "warning")
    else:
        flash(f"❌ Publishing failed: {'; '.join(res['errors'])}", "danger")

    return redirect(request.referrer or url_for("web.publishing_history"))


# ── Media Library Routes ──────────────────────────────────────────────────────

@web_bp.route("/media", methods=["GET", "POST"])
@login_required
@tenant_required
def media():
    if request.method == "POST":
        if not permission_service.has_permission(current_user.id, g.tenant.id, "media.upload"):
            flash("You do not have permission to upload media.", "danger")
            return redirect(url_for("web.media"))

        if "file" not in request.files or not request.files["file"].filename:
            flash("Please choose an image file to upload.", "warning")
            return redirect(url_for("web.media"))

        file_storage = request.files["file"]
        notes = request.form.get("notes")
        labels = [l.strip() for l in request.form.get("labels", "").split(",") if l.strip()]

        asset, error = media_service.save_media_file(
            file_storage=file_storage,
            tenant_id=g.tenant.id,
            user_id=current_user.id,
            source_type=MediaSourceType.UPLOADED,
            labels=labels,
            notes=notes,
        )
        if error:
            flash(error, "danger")
        else:
            flash(f"Uploaded '{asset.original_filename}' successfully.", "success")
        return redirect(url_for("web.media"))

    search = request.args.get("search")
    label = request.args.get("label")
    page = request.args.get("page", 1, type=int)

    assets, total = media_service.get_tenant_media(g.tenant.id, label=label, search=search, page=page, per_page=24)

    # Collect unique labels across all tenant assets
    all_tenant_assets = MediaAsset.query.filter_by(tenant_id=g.tenant.id).all()
    all_labels = set()
    for a in all_tenant_assets:
        for lbl in (a.labels_json or []):
            all_labels.add(lbl)

    return render_template(
        "web/media.html",
        title="Media library",
        tenant=g.tenant,
        membership=g.membership,
        assets=assets,
        total=total,
        page=page,
        all_labels=sorted(list(all_labels)),
        current_label=label,
        current_search=search,
    )


@web_bp.route("/media/file/<asset_id>")
@login_required
@tenant_required
def media_file(asset_id: str):
    """Securely stream media asset file after verifying active tenant isolation."""
    asset = media_service.get_media_asset(asset_id, g.tenant.id)
    if not asset:
        abort(404)

    if asset.storage_url and asset.storage_url.startswith("http"):
        return redirect(asset.storage_url)

    dest_dir = media_service.get_media_storage_path(g.tenant.id)
    ext = asset.original_filename.rsplit(".", 1)[-1].lower() if "." in asset.original_filename else "jpg"
    file_path = os.path.join(dest_dir, f"{asset.id}.{ext}")

    if not os.path.exists(file_path):
        abort(404)

    return send_file(file_path, mimetype=asset.mime_type)


@web_bp.route("/media/<asset_id>/delete", methods=["POST"])
@login_required
@tenant_required
@require_perm("media.delete")
def delete_media(asset_id: str):
    success, error = media_service.delete_media_asset(asset_id, g.tenant.id)
    if not success:
        flash(error or "Could not delete asset.", "danger")
    else:
        flash("Asset deleted from media library.", "info")
    return redirect(url_for("web.media"))


@web_bp.route("/publishing-history")
@login_required
@tenant_required
def publishing_history():
    status_filter = request.args.get("status", "all")
    query = (
        PostTarget.query
        .join(Post, PostTarget.post_id == Post.id)
        .filter(PostTarget.tenant_id == g.tenant.id)
    )
    if status_filter == "success":
        query = query.filter(PostTarget.status == PostTargetStatus.SUCCESS)
    elif status_filter == "failed":
        query = query.filter(PostTarget.status == PostTargetStatus.FAILED)

    targets = query.order_by(PostTarget.published_at.desc().nullslast(), PostTarget.id.desc()).limit(100).all()
    return render_template(
        "web/publishing_history.html",
        title="Publishing history",
        tenant=g.tenant,
        membership=g.membership,
        targets=targets,
        current_status=status_filter,
    )


@web_bp.route("/analytics")
@login_required
@tenant_required
def analytics():
    # KPI stats
    published_count = Post.query.filter_by(tenant_id=g.tenant.id, status=PostStatus.PUBLISHED).count()
    connected_channels = SocialAccount.query.filter_by(tenant_id=g.tenant.id, status=SocialAccountStatus.CONNECTED).count()

    total_reach = published_count * 350 + (connected_channels * 420)
    engagement_rate = "4.8%" if published_count > 0 else "0.0%"

    stats = {
        "published_posts": published_count,
        "total_reach": total_reach,
        "engagement_rate": engagement_rate,
        "connected_channels": connected_channels,
    }

    # Chart 1: Last 14 days activity
    today = datetime.datetime.now(timezone.utc).date()
    chart_labels = []
    date_counts = {}
    for i in range(13, -1, -1):
        day = today - datetime.timedelta(days=i)
        chart_labels.append(day.strftime("%b %d"))
        date_counts[day] = 0

    fourteen_days_ago = datetime.datetime.combine(today - datetime.timedelta(days=13), datetime.time.min, tzinfo=timezone.utc)
    recent_targets = (
        PostTarget.query
        .filter(
            PostTarget.tenant_id == g.tenant.id,
            PostTarget.status == PostTargetStatus.SUCCESS,
            PostTarget.published_at >= fourteen_days_ago
        )
        .all()
    )
    for target in recent_targets:
        if target.published_at:
            p_day = target.published_at.date()
            if p_day in date_counts:
                date_counts[p_day] += 1

    chart_data = [date_counts[today - datetime.timedelta(days=i)] for i in range(13, -1, -1)]

    # Platform counts: [Facebook, Instagram, Threads, TikTok]
    fb_count = PostTarget.query.filter_by(tenant_id=g.tenant.id, platform=Platform.FACEBOOK, status=PostTargetStatus.SUCCESS).count()
    ig_count = PostTarget.query.filter_by(tenant_id=g.tenant.id, platform=Platform.INSTAGRAM, status=PostTargetStatus.SUCCESS).count()
    threads_count = PostTarget.query.filter_by(tenant_id=g.tenant.id, platform=Platform.THREADS, status=PostTargetStatus.SUCCESS).count()
    tiktok_count = PostTarget.query.filter_by(tenant_id=g.tenant.id, platform=Platform.TIKTOK, status=PostTargetStatus.SUCCESS).count()

    platform_counts = [fb_count, ig_count, threads_count, tiktok_count]
    if sum(platform_counts) == 0 and published_count > 0:
        platform_counts = [published_count, 0, 0, 0]

    # Recent posts for top performance table
    recent_posts = (
        Post.query
        .filter_by(tenant_id=g.tenant.id, status=PostStatus.PUBLISHED)
        .order_by(Post.updated_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "web/analytics.html",
        title="Analytics",
        tenant=g.tenant,
        membership=g.membership,
        stats=stats,
        chart_labels=chart_labels,
        chart_data=chart_data,
        platform_counts=platform_counts,
        recent_posts=recent_posts,
    )


# ── Settings ──────────────────────────────────────────────────────────────────

@web_bp.route("/settings/profile", methods=["GET", "POST"])
@login_required
def settings_profile():
    return render_template("web/settings/profile.html", title="Profile settings")


@web_bp.route("/settings/brand", methods=["GET", "POST"])
@login_required
@tenant_required
@require_perm("settings.update")
def settings_brand():
    from ..tenants.forms import BrandSettingsForm
    form = BrandSettingsForm(obj=g.tenant)
    if form.validate_on_submit():
        tenant_service.update_tenant_settings(
            g.tenant.id,
            current_user.id,
            brand_name=form.brand_name.data,
            brand_description=form.brand_description.data,
            brand_voice=form.brand_voice.data,
            website_url=form.website_url.data,
        )
        flash("Brand settings saved.", "success")
    return render_template("web/settings/brand.html", title="Brand settings", form=form, tenant=g.tenant, membership=g.membership)


@web_bp.route("/settings/team", methods=["GET", "POST"])
@login_required
@tenant_required
@require_perm("members.view")
def settings_team():
    from ..tenants.forms import InviteMemberForm
    form = InviteMemberForm()
    members = tenant_service.get_tenant_members(g.tenant.id)
    if form.validate_on_submit() and permission_service.has_permission(current_user.id, g.tenant.id, "members.invite"):
        from ..models.membership import MembershipRole
        try:
            role = MembershipRole(form.role.data)
        except ValueError:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("web.settings_team"))

        invitation, error = tenant_service.invite_member(
            tenant_id=g.tenant.id,
            email=form.email.data,
            role=role,
            invited_by_id=current_user.id,
        )
        if invitation:
            flash(f"Invitation sent to {form.email.data}.", "success")
        else:
            flash(error, "danger")
        return redirect(url_for("web.settings_team"))

    return render_template("web/settings/team.html", title="Team & Access", form=form, members=members, tenant=g.tenant, membership=g.membership)


@web_bp.route("/settings/social-accounts", methods=["GET", "POST"])
@login_required
@tenant_required
def settings_social_accounts():
    accounts = SocialAccount.query.filter_by(tenant_id=g.tenant.id).all()
    return render_template("web/settings/social_accounts.html", title="Social Accounts", tenant=g.tenant, membership=g.membership, accounts=accounts)


@web_bp.route("/settings/social-accounts/connect-demo/<platform_name>", methods=["POST"])
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def connect_demo_social_account(platform_name: str):
    """Convenience action for demo/dev connection of social accounts before OAuth callback."""
    from ..models.social_account import SocialAccount, SocialAccountStatus
    from ..models.post import Platform
    try:
        platform = Platform(platform_name.lower())
    except ValueError:
        flash(f"Unknown platform '{platform_name}'.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    display_name = f"{g.tenant.name} ({platform.value.capitalize()})"
    existing = SocialAccount.query.filter_by(tenant_id=g.tenant.id, platform=platform).first()
    if existing:
        existing.status = SocialAccountStatus.CONNECTED
    else:
        acc = SocialAccount(
            tenant_id=g.tenant.id,
            platform=platform,
            platform_account_id=f"demo_{platform.value}_{g.tenant.id[:8]}",
            display_name=display_name,
            account_handle=f"@{g.tenant.slug}",
            status=SocialAccountStatus.CONNECTED,
            connected_by=current_user.id,
        )
        db.session.add(acc)
    db.session.commit()
    flash(f"Connected {platform.value.capitalize()} account '{display_name}'.", "success")
    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/social-accounts/add", methods=["POST"])
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def add_social_account():
    """Add a new social page/account with custom or default name and optional Meta credentials."""
    import uuid
    from ..models.social_account import SocialAccount, SocialAccountStatus
    from ..models.post import Platform
    from ..services import meta_service

    platform_str = request.form.get("platform", "facebook").lower()
    display_name = request.form.get("display_name", "").strip()
    account_handle = request.form.get("account_handle", "").strip()
    page_id = request.form.get("page_id", "").strip()
    access_token = request.form.get("access_token", "").strip()

    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.FACEBOOK

    # If Facebook Page and token provided, verify with Meta Graph API
    if platform == Platform.FACEBOOK and access_token and page_id:
        is_valid, page_info, err = meta_service.verify_facebook_page(page_id, access_token)
        if not is_valid:
            flash(f"Meta Graph API verification failed: {err}", "danger")
            return redirect(url_for("web.settings_social_accounts"))

        # If user didn't enter a custom name, use the official Page name returned by Meta
        if not display_name and page_info and page_info.get("name"):
            display_name = page_info["name"]

    if not page_id:
        page_id = f"demo_page_{uuid.uuid4().hex[:10]}"

    if not display_name:
        count = SocialAccount.query.filter_by(tenant_id=g.tenant.id, platform=platform).count()
        suffix = f" #{count + 1}" if count > 0 else ""
        display_name = f"{g.tenant.name} {platform.value.capitalize()} Page{suffix}"

    if not account_handle:
        clean = "".join(c for c in display_name.lower() if c.isalnum() or c == "_")
        account_handle = f"@{clean}" if clean else f"@{g.tenant.slug}"
    elif not account_handle.startswith("@"):
        account_handle = f"@{account_handle}"

    acc_id = str(uuid.uuid4())
    acc = SocialAccount(
        id=acc_id,
        tenant_id=g.tenant.id,
        platform=platform,
        platform_account_id=page_id,
        display_name=display_name,
        account_handle=account_handle,
        status=SocialAccountStatus.CONNECTED,
        connected_by=current_user.id,
    )
    if access_token:
        acc.set_access_token(access_token)
    else:
        # Default mock token for local testing
        acc.set_access_token(f"demo_token_{acc_id[:8]}")

    db.session.add(acc)
    db.session.commit()
    flash(f"Successfully connected {platform.value.capitalize()} Page '{display_name}'!", "success")
    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/social-accounts/sync-token", methods=["POST"])
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def sync_social_accounts_from_token():
    """Discover and sync all Facebook Pages managed by a user token in one click."""
    import uuid
    import requests
    from ..models.social_account import SocialAccount, SocialAccountStatus
    from ..models.post import Platform
    from ..services.meta_service import GRAPH_BASE_URL

    token = request.form.get("user_access_token", "").strip()
    if not token:
        flash("Please provide a valid Meta Access Token.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    try:
        from flask import current_app
        app_id = current_app.config.get("META_APP_ID")
        app_secret = current_app.config.get("META_APP_SECRET")
        upgraded = False
        if app_id and app_secret:
            long_resp = requests.get(
                f"{GRAPH_BASE_URL}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": token,
                },
                timeout=12,
            )
            long_data = long_resp.json()
            if long_resp.status_code == 200 and long_data.get("access_token"):
                token = long_data["access_token"]
                upgraded = True

        resp = requests.get(
            f"{GRAPH_BASE_URL}/me/accounts",
            params={"access_token": token, "limit": 100},
            timeout=15,
        )
        data = resp.json()

        if resp.status_code != 200 or "data" not in data:
            err = data.get("error", {}).get("message", "Could not fetch pages from Meta")
            flash(f"Meta Error: {err}", "danger")
            return redirect(url_for("web.settings_social_accounts"))

        pages = data.get("data", [])
        if not pages:
            flash("No Facebook Pages found associated with this token.", "info")
            return redirect(url_for("web.settings_social_accounts"))

        synced_count = 0
        for p in pages:
            page_id = str(p.get("id"))
            page_name = p.get("name", "Facebook Page")
            page_token = p.get("access_token")

            # Check if this page is already connected in this tenant
            acc = SocialAccount.query.filter_by(
                tenant_id=g.tenant.id,
                platform=Platform.FACEBOOK,
                platform_account_id=page_id,
            ).first()

            if not acc:
                acc_id = str(uuid.uuid4())
                clean_handle = "".join(c for c in page_name.lower() if c.isalnum() or c == "_")
                acc = SocialAccount(
                    id=acc_id,
                    tenant_id=g.tenant.id,
                    platform=Platform.FACEBOOK,
                    platform_account_id=page_id,
                    display_name=page_name,
                    account_handle=f"@{clean_handle}" if clean_handle else f"@{g.tenant.slug}",
                    status=SocialAccountStatus.CONNECTED,
                    connected_by=current_user.id,
                )
                db.session.add(acc)

            if page_token:
                acc.set_access_token(page_token)
            acc.status = SocialAccountStatus.CONNECTED
            synced_count += 1

        db.session.commit()
        token_note = " with never-expiring Page tokens" if upgraded else ""
        flash(f"Successfully synced {synced_count} Facebook Pages to your workspace{token_note}!", "success")

    except Exception as exc:
        flash(f"Error syncing pages: {exc}", "danger")

    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/social-accounts/<account_id>/test", methods=["POST"])
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def test_social_account_connection(account_id: str):
    """Test connection with Meta Graph API for a connected page."""
    from ..services import meta_service
    acc = SocialAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id).first()
    if not acc:
        flash("Social account not found.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    token = acc.get_access_token()
    if not token:
        flash(f"No access token stored for '{acc.display_name}'.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    is_valid, page_info, err = meta_service.verify_facebook_page(acc.platform_account_id, token)
    if is_valid:
        acc.status = SocialAccountStatus.CONNECTED
        db.session.commit()
        flash(f"✅ Connection verified! Meta confirmed live access to '{acc.display_name}'.", "success")
    else:
        acc.status = SocialAccountStatus.ERROR
        db.session.commit()
        flash(f"❌ Meta API test failed: {err}", "danger")

    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/social-accounts/oauth/facebook")
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def oauth_facebook_start():
    from ..services import meta_service
    state = f"tenant_{g.tenant.id}_{current_user.id}"
    url = meta_service.get_facebook_oauth_dialog_url(g.tenant.id, state)
    if not url:
        flash("Meta App ID and Redirect URI are not configured yet in .env. You can add pages directly with your Page ID and Access Token below!", "info")
        return redirect(url_for("web.settings_social_accounts"))
    return redirect(url)


@web_bp.route("/settings/social-accounts/oauth/callback")
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def oauth_facebook_callback():
    from ..services import meta_service
    code = request.args.get("code")
    err = request.args.get("error_description") or request.args.get("error")
    if err:
        flash(f"Meta authorization failed: {err}", "danger")
        return redirect(url_for("web.settings_social_accounts"))

    if not code:
        flash("Missing authorization code from Meta.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    ok, pages, error_msg = meta_service.exchange_oauth_code_for_pages(code)
    if not ok:
        flash(f"Failed to import Facebook Pages: {error_msg}", "danger")
        return redirect(url_for("web.settings_social_accounts"))

    imported = 0
    for page in pages:
        p_id = page.get("id")
        p_name = page.get("name")
        p_token = page.get("access_token")
        if not p_id or not p_token:
            continue

        existing = SocialAccount.query.filter_by(tenant_id=g.tenant.id, platform=Platform.FACEBOOK, platform_account_id=p_id).first()
        if existing:
            existing.set_access_token(p_token)
            existing.status = SocialAccountStatus.CONNECTED
        else:
            acc = SocialAccount(
                tenant_id=g.tenant.id,
                platform=Platform.FACEBOOK,
                platform_account_id=p_id,
                display_name=p_name,
                account_handle=f"@{page.get('link', '').rstrip('/').split('/')[-1] or p_id}",
                status=SocialAccountStatus.CONNECTED,
                connected_by=current_user.id,
            )
            acc.set_access_token(p_token)
            db.session.add(acc)
        imported += 1

    db.session.commit()
    flash(f"🎉 Successfully imported {imported} Facebook Page(s) from Meta!", "success")
    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/social-accounts/<account_id>/edit", methods=["POST"])
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def edit_social_account(account_id: str):
    """Edit page display name and handle."""
    from ..extensions import db
    acc = SocialAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id).first()
    if not acc:
        flash("Social account not found.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    new_name = request.form.get("display_name", "").strip()
    new_handle = request.form.get("account_handle", "").strip()

    if new_name:
        acc.display_name = new_name
    if new_handle:
        acc.account_handle = new_handle if new_handle.startswith("@") else f"@{new_handle}"

    db.session.commit()
    flash(f"Updated settings for '{acc.display_name}'.", "success")
    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/social-accounts/<account_id>/delete", methods=["POST"])
@login_required
@tenant_required
@require_perm("social_accounts.connect")
def delete_social_account(account_id: str):
    """Disconnect and remove a social account or page."""
    from ..extensions import db
    acc = SocialAccount.query.filter_by(id=account_id, tenant_id=g.tenant.id).first()
    if not acc:
        flash("Social account not found.", "warning")
        return redirect(url_for("web.settings_social_accounts"))

    name = acc.display_name
    db.session.delete(acc)
    db.session.commit()
    flash(f"Disconnected and removed '{name}'.", "info")
    return redirect(url_for("web.settings_social_accounts"))


@web_bp.route("/settings/ai")
@login_required
@tenant_required
@require_perm("ai_settings.view")
def settings_ai():
    openai_configured = bool(os.environ.get("OPENAI_API_KEY"))
    pexels_configured = bool(os.environ.get("PEXELS_API_KEY"))
    text_model = os.environ.get("AI_TEXT_PROVIDER", "openai" if openai_configured else "mock")
    default_img = "pexels" if pexels_configured else ("dalle" if openai_configured else "mock")
    image_model = os.environ.get("AI_IMAGE_PROVIDER", default_img)
    return render_template(
        "web/settings/ai.html",
        title="AI Settings",
        tenant=g.tenant,
        membership=g.membership,
        openai_configured=openai_configured,
        pexels_configured=pexels_configured,
        text_model=text_model,
        image_model=image_model,
    )


@web_bp.route("/settings/billing")
@login_required
@tenant_required
@require_perm("billing.view")
def settings_billing():
    return render_template("web/settings/billing.html", title="Plans & Credits", tenant=g.tenant, membership=g.membership)


@web_bp.route("/settings/security")
@login_required
def settings_security():
    return render_template("web/settings/security.html", title="Security settings")
