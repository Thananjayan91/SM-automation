"""Milestone 2 Acceptance & Content Management Tests.

Covers:
- SSRF URL validation
- Draft creation, editing, saving, and reloading
- Post versioning and content hashing
- Version approval and approval invalidation upon edit
- Media asset upload and management
- Cross-tenant isolation on content and media
"""
import io
import pytest
from werkzeug.datastructures import FileStorage
from PIL import Image

from app.extensions import db
from app.models.source import SourceType, SourceStatus, Source
from app.models.post import Post, PostVersion, PostStatus, Platform
from app.models.media_asset import MediaAsset, MediaSourceType
from app.services import content_service, media_service, security_service, permission_service
from .conftest import create_user, create_tenant, add_member


def _create_dummy_image_file(filename: str = "test.png", size: tuple = (200, 200), color: str = "blue") -> FileStorage:
    """Helper to generate an in-memory PNG FileStorage object."""
    stream = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(stream, format="PNG")
    stream.seek(0)
    return FileStorage(stream=stream, filename=filename, content_type="image/png")


class TestSSRFProtection:
    """Ensure submitted URLs cannot target internal network infrastructure."""

    def test_blocks_localhost(self):
        is_safe, err = security_service.validate_url_safe("http://localhost:5000/admin")
        assert is_safe is False
        assert "localhost" in err.lower() or "blocked" in err.lower()

    def test_blocks_loopback_ip(self):
        is_safe, err = security_service.validate_url_safe("http://127.0.0.1:8080/secret")
        assert is_safe is False
        assert "blocked" in err.lower()

    def test_blocks_private_class_c(self):
        is_safe, err = security_service.validate_url_safe("http://192.168.1.1/router")
        assert is_safe is False
        assert "blocked" in err.lower()

    def test_blocks_cloud_metadata_ip(self):
        is_safe, err = security_service.validate_url_safe("http://169.254.169.254/latest/meta-data/")
        assert is_safe is False
        assert "blocked" in err.lower()

    def test_rejects_non_http_schemes(self):
        is_safe, err = security_service.validate_url_safe("file:///etc/passwd")
        assert is_safe is False
        assert "http" in err.lower()

    def test_allows_valid_public_domain(self):
        is_safe, err = security_service.validate_url_safe("https://www.google.com")
        assert is_safe is True
        assert err is None


class TestMediaUpload:
    """Verify image asset validation and scoped storage."""

    def test_save_valid_image(self, app, db, tenant_a, user_a):
        with app.app_context():
            file_storage = _create_dummy_image_file("hero.png", size=(400, 300))
            asset, err = media_service.save_media_file(
                file_storage=file_storage,
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                labels=["social", "summer"],
                notes="Brand campaign visual",
            )
            assert err is None
            assert asset is not None
            assert asset.tenant_id == tenant_a.id
            assert asset.width == 400
            assert asset.height == 300
            assert "social" in asset.labels_json

    def test_rejects_disallowed_extension(self, app, db, tenant_a, user_a):
        with app.app_context():
            fake_exe = io.BytesIO(b"malicious content")
            file_storage = FileStorage(stream=fake_exe, filename="payload.exe", content_type="application/octet-stream")
            asset, err = media_service.save_media_file(
                file_storage=file_storage,
                tenant_id=tenant_a.id,
                user_id=user_a.id,
            )
            assert asset is None
            assert "not supported" in err.lower()


class TestDraftLifecycle:
    """Milestone 2 Acceptance Criterion: Create, edit, save and reload a draft."""

    def test_create_save_and_reload_draft(self, app, db, tenant_a, user_a):
        with app.app_context():
            # 1. Create source
            source, s_err = content_service.submit_source(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                source_type=SourceType.MANUAL,
                headline="AI Social Automation Trends",
                raw_text="Social media management is becoming fully agentic.",
            )
            assert s_err is None

            # 2. Create Draft Post
            post, p_err = content_service.create_draft_post(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Here is our take on automated social publishing.",
                hashtags=["#AI", "#SaaS"],
                source_id=source.id,
            )
            assert p_err is None
            assert post.status == PostStatus.DRAFT
            assert post.content_version == 1
            assert len(post.versions) == 1

            # 3. Edit Draft Post
            updated_post, u_err = content_service.update_post_content(
                post_id=post.id,
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Updated caption: Next-gen AI social tools.",
                hashtags=["#AI", "#SaaS", "#Growth"],
                first_comment="Link in bio for early access!",
                first_comment_enabled=True,
            )
            assert u_err is None
            assert updated_post.content_version == 2
            assert len(updated_post.versions) == 2

            # 4. Reload Post from DB & Verify Persistence
            reloaded = content_service.get_tenant_post(post.id, tenant_a.id)
            assert reloaded is not None
            assert reloaded.caption == "Updated caption: Next-gen AI social tools."
            assert "#Growth" in reloaded.hashtags_json
            assert reloaded.first_comment == "Link in bio for early access!"
            assert reloaded.first_comment_enabled is True
            assert reloaded.content_version == 2


class TestApprovalIntegrity:
    """Verify versioned approvals and approval invalidation on modification."""

    def test_approve_post_locks_version(self, app, db, tenant_a, user_a):
        with app.app_context():
            post, _ = content_service.create_draft_post(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Content to approve.",
            )

            # Approve version 1
            approval, err = content_service.approve_post_version(
                post_id=post.id,
                tenant_id=tenant_a.id,
                user_id=user_a.id,
            )
            assert err is None
            assert approval is not None
            assert post.status == PostStatus.APPROVED
            assert post.approved_by == user_a.id

    def test_editing_invalidates_approval(self, app, db, tenant_a, user_a):
        with app.app_context():
            post, _ = content_service.create_draft_post(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Initial approved copy.",
            )
            content_service.approve_post_version(post.id, tenant_a.id, user_a.id)
            assert post.status == PostStatus.APPROVED

            # Now modify content
            post_after_edit, _ = content_service.update_post_content(
                post_id=post.id,
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Modified text after approval.",
            )

            # Approval must be invalidated
            assert post_after_edit.status == PostStatus.READY_FOR_REVIEW
            assert post_after_edit.approved_by is None
            assert post_after_edit.approved_at is None
            assert post_after_edit.content_version == 2


class TestContentTenantIsolation:
    """Ensure Tenant A cannot read, edit, or approve Tenant B's posts or media."""

    def test_cannot_read_other_tenant_post(self, app, db, tenant_a, tenant_b, user_b):
        with app.app_context():
            post_b, _ = content_service.create_draft_post(
                tenant_id=tenant_b.id,
                user_id=user_b.id,
                caption="Tenant B Private Post",
            )

            # Tenant A queries for Post B's ID
            post_for_a = content_service.get_tenant_post(post_b.id, tenant_a.id)
            assert post_for_a is None

    def test_cannot_update_other_tenant_post(self, app, db, tenant_a, tenant_b, user_a, user_b):
        with app.app_context():
            post_b, _ = content_service.create_draft_post(
                tenant_id=tenant_b.id,
                user_id=user_b.id,
                caption="Tenant B Original",
            )

            # User A attempts to edit Post B using Tenant A context
            updated, err = content_service.update_post_content(
                post_id=post_b.id,
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Malicious injection attempt",
            )
            assert updated is None
            assert "not found" in err.lower()

            # Verify Post B was untouched
            post_b_reload = content_service.get_tenant_post(post_b.id, tenant_b.id)
            assert post_b_reload.caption == "Tenant B Original"

    def test_cannot_access_other_tenant_media(self, app, db, tenant_a, tenant_b, user_b):
        with app.app_context():
            file_storage = _create_dummy_image_file("b_secret.png")
            asset_b, _ = media_service.save_media_file(
                file_storage=file_storage,
                tenant_id=tenant_b.id,
                user_id=user_b.id,
            )

            # Tenant A tries to query Tenant B's media asset
            asset_for_a = media_service.get_media_asset(asset_b.id, tenant_a.id)
            assert asset_for_a is None


class TestPostSaveAndPublishFlow:
    """Ensure Save Draft does not approve, and Publish publishes to targets."""

    def test_save_draft_does_not_approve(self, app, client, tenant_a, user_a):
        with app.app_context():
            post, _ = content_service.create_draft_post(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Initial Draft Content",
            )
            post_id = post.id

        with client.session_transaction() as sess:
            sess["_user_id"] = user_a.id
            sess["active_tenant_id"] = tenant_a.id

        resp = client.post(
            f"/app/posts/{post_id}/edit",
            data={
                "caption": "Updated Draft Content",
                "hashtags": "#strategy",
                "publish_action": "0",
                "approve_action": "0",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            p = content_service.get_tenant_post(post_id, tenant_a.id)
            assert p.caption == "Updated Draft Content"
            assert p.status != PostStatus.APPROVED
            assert p.status != PostStatus.PUBLISHED

    def test_publish_flow_with_social_targets(self, app, client, tenant_a, user_a):
        from app.models.social_account import SocialAccount, SocialAccountStatus
        with app.app_context():
            acc1 = SocialAccount(
                tenant_id=tenant_a.id,
                platform=Platform.FACEBOOK,
                platform_account_id="page_123",
                display_name="Downtown Branch Page",
                account_handle="@downtown",
                status=SocialAccountStatus.CONNECTED,
            )
            acc2 = SocialAccount(
                tenant_id=tenant_a.id,
                platform=Platform.FACEBOOK,
                platform_account_id="page_456",
                display_name="Global Announcements Page",
                account_handle="@global",
                status=SocialAccountStatus.CONNECTED,
            )
            db.session.add_all([acc1, acc2])
            post, _ = content_service.create_draft_post(
                tenant_id=tenant_a.id,
                user_id=user_a.id,
                caption="Exciting Product Launch",
            )
            db.session.commit()
            post_id = post.id
            acc1_id, acc2_id = acc1.id, acc2.id

        with client.session_transaction() as sess:
            sess["_user_id"] = user_a.id
            sess["active_tenant_id"] = tenant_a.id

        # Publish to both pages
        resp = client.post(
            f"/app/posts/{post_id}/edit",
            data={
                "caption": "Exciting Product Launch",
                "account_ids": [acc1_id, acc2_id],
                "publish_action": "1",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            p = content_service.get_tenant_post(post_id, tenant_a.id)
            assert p.status == PostStatus.PUBLISHED
            assert len(p.targets) == 2
            assert all(t.status.value == "success" for t in p.targets)

    def test_add_multiple_pages_with_custom_names(self, app, client, tenant_a, user_a):
        with client.session_transaction() as sess:
            sess["_user_id"] = user_a.id
            sess["active_tenant_id"] = tenant_a.id

        # Add first page
        r1 = client.post(
            "/app/settings/social-accounts/add",
            data={
                "platform": "facebook",
                "display_name": "Studio Main Page",
                "account_handle": "studiomain",
            },
            follow_redirects=True,
        )
        assert r1.status_code == 200

        # Add second page
        r2 = client.post(
            "/app/settings/social-accounts/add",
            data={
                "platform": "facebook",
                "display_name": "Studio Community Group",
                "account_handle": "studiocommunity",
            },
            follow_redirects=True,
        )
        assert r2.status_code == 200

        with app.app_context():
            from app.models.social_account import SocialAccount
            accounts = SocialAccount.query.filter_by(tenant_id=tenant_a.id, platform=Platform.FACEBOOK).all()
            names = [a.display_name for a in accounts]
            assert "Studio Main Page" in names
            assert "Studio Community Group" in names
            assert len(accounts) == 2


