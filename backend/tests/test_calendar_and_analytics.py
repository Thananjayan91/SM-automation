"""Milestone 5 Tests: Scheduling Engine, Content Calendar, Delivery Audit, and Analytics Dashboard."""
import datetime
from datetime import timezone
import uuid
import pytest

from app.extensions import db
from app.models.post import Post, PostStatus, Platform, PostTarget, PostTargetStatus
from app.models.social_account import SocialAccount, SocialAccountStatus
from app.services import content_service
from app.tasks.publishing import publish_due_scheduled_posts, publish_single_post
from .conftest import create_user, create_tenant, login


def _create_test_account(tenant_id: str, platform=Platform.FACEBOOK, display_name="Test FB Page"):
    acc = SocialAccount(
        tenant_id=tenant_id,
        platform=platform,
        platform_account_id=f"page_{uuid.uuid4().hex[:8]}",
        display_name=display_name,
        status=SocialAccountStatus.CONNECTED,
    )
    acc.set_access_token("demo_token_test")
    db.session.add(acc)
    db.session.flush()
    return acc


class TestCalendarAndScheduling:
    def test_calendar_page_loads(self, client, db, user_a, tenant_a):
        login(client, "user_a@example.com", "Test1234!")
        res = client.get("/app/calendar")
        assert res.status_code == 200
        assert b"Content Calendar" in res.data
        assert b"Reschedule Post" in res.data

    def test_calendar_displays_scheduled_post(self, client, db, user_a, tenant_a):
        login(client, "user_a@example.com", "Test1234!")
        scheduled_time = datetime.datetime.now(timezone.utc) + datetime.timedelta(days=2)
        post, _ = content_service.create_draft_post(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            caption="Launch Day Announcement #CalendarTest",
        )
        post.scheduled_for = scheduled_time
        post.status = PostStatus.READY_FOR_REVIEW
        db.session.commit()

        res = client.get(f"/app/calendar?year={scheduled_time.year}&month={scheduled_time.month}")
        assert res.status_code == 200
        assert b"Launch Day Announcement" in res.data

    def test_reschedule_post_route(self, client, db, user_a, tenant_a):
        login(client, "user_a@example.com", "Test1234!")
        post, _ = content_service.create_draft_post(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            caption="Reschedule Test Post",
        )
        new_date_str = "2026-11-15T14:30:00"
        res = client.post(
            f"/app/posts/{post.id}/reschedule",
            data={"scheduled_for": new_date_str},
            follow_redirects=True,
        )
        assert res.status_code == 200
        db.session.refresh(post)
        assert post.scheduled_for is not None
        assert post.scheduled_for.year == 2026
        assert post.scheduled_for.month == 11
        assert post.scheduled_for.day == 15

    def test_publish_due_scheduled_posts_task(self, client, db, user_a, tenant_a):
        account = _create_test_account(tenant_a.id)
        past_time = datetime.datetime.now(timezone.utc) - datetime.timedelta(minutes=10)

        post, _ = content_service.create_draft_post(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            caption="Automated cron published post",
        )
        post.scheduled_for = past_time
        post.status = PostStatus.APPROVED

        target = PostTarget(
            tenant_id=tenant_a.id,
            post_id=post.id,
            social_account_id=account.id,
            platform=Platform.FACEBOOK,
            status=PostTargetStatus.PENDING,
        )
        db.session.add(target)
        db.session.commit()

        results = publish_due_scheduled_posts()
        assert len(results) == 1
        assert results[0]["status"] == "published"

        db.session.refresh(post)
        db.session.refresh(target)
        assert post.status == PostStatus.PUBLISHED
        assert target.status == PostTargetStatus.SUCCESS
        assert target.platform_post_id is not None


class TestDeliveryAuditAndAnalytics:
    def test_publishing_history_delivery_audit(self, client, db, user_a, tenant_a):
        login(client, "user_a@example.com", "Test1234!")
        account = _create_test_account(tenant_a.id)

        post, _ = content_service.create_draft_post(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            caption="Audit Log Test Post",
        )
        target = PostTarget(
            tenant_id=tenant_a.id,
            post_id=post.id,
            social_account_id=account.id,
            platform=Platform.FACEBOOK,
            status=PostTargetStatus.SUCCESS,
            platform_post_id="fb_receipt_998877",
            published_at=datetime.datetime.now(timezone.utc),
        )
        db.session.add(target)
        db.session.commit()

        res = client.get("/app/publishing-history")
        assert res.status_code == 200
        assert b"Audit Log Test Post" in res.data
        assert b"fb_receipt_998877" in res.data
        assert b"Published" in res.data

        # Test filter status=success
        res_success = client.get("/app/publishing-history?status=success")
        assert res_success.status_code == 200
        assert b"Audit Log Test Post" in res_success.data

        # Test filter status=failed
        res_failed = client.get("/app/publishing-history?status=failed")
        assert res_failed.status_code == 200
        assert b"fb_receipt_998877" not in res_failed.data

    def test_retry_publish_route(self, client, db, user_a, tenant_a):
        login(client, "user_a@example.com", "Test1234!")
        account = _create_test_account(tenant_a.id)

        post, _ = content_service.create_draft_post(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            caption="Post that previously failed",
        )
        target = PostTarget(
            tenant_id=tenant_a.id,
            post_id=post.id,
            social_account_id=account.id,
            platform=Platform.FACEBOOK,
            status=PostTargetStatus.FAILED,
            error_message="Simulated temporary API timeout",
        )
        db.session.add(target)
        db.session.commit()

        res = client.post(
            f"/app/posts/{post.id}/retry-publish",
            follow_redirects=True,
        )
        assert res.status_code == 200
        db.session.refresh(post)
        db.session.refresh(target)
        assert target.status == PostTargetStatus.SUCCESS
        assert post.status == PostStatus.PUBLISHED

    def test_analytics_dashboard_renders_metrics_and_charts(self, client, db, user_a, tenant_a):
        login(client, "user_a@example.com", "Test1234!")
        account = _create_test_account(tenant_a.id)

        # Empty state analytics
        res_empty = client.get("/app/analytics")
        assert res_empty.status_code == 200
        assert b"Performance &amp; Analytics" in res_empty.data or b"Performance & Analytics" in res_empty.data
        assert b"Published Posts" in res_empty.data

        # With published post
        post, _ = content_service.create_draft_post(
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            caption="High Performing Content for Analytics",
        )
        post.status = PostStatus.PUBLISHED
        target = PostTarget(
            tenant_id=tenant_a.id,
            post_id=post.id,
            social_account_id=account.id,
            platform=Platform.FACEBOOK,
            status=PostTargetStatus.SUCCESS,
            published_at=datetime.datetime.now(timezone.utc),
        )
        db.session.add(target)
        db.session.commit()

        res_populated = client.get("/app/analytics")
        assert res_populated.status_code == 200
        assert b"High Performing Content" in res_populated.data
        assert b"activityChart" in res_populated.data
        assert b"platformChart" in res_populated.data
