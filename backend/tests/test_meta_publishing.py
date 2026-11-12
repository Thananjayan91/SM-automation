"""Tests for Milestone 4: Meta Graph API Facebook & Instagram Publishing Integration."""
from unittest.mock import patch, MagicMock
import pytest
from app.extensions import db
from app.models.post import Platform, PostStatus, PostTargetStatus
from app.models.social_account import SocialAccount, SocialAccountStatus
from app.services import meta_service, content_service
from app.services.security_service import encrypt_credential, decrypt_credential


def test_credential_encryption_and_decryption(app):
    with app.app_context():
        secret_token = "EAABwzL138ZA0BOZCu4v718XjLKnw9"
        cipher = encrypt_credential(secret_token)
        assert cipher is not None
        assert cipher != secret_token
        assert "EAA" not in cipher

        decrypted = decrypt_credential(cipher)
        assert decrypted == secret_token


def test_social_account_token_storage(app, db, tenant_a):
    with app.app_context():
        raw_token = "EAALiveProductionTokenExample"
        acc = SocialAccount(
            tenant_id=tenant_a.id,
            platform=Platform.FACEBOOK,
            platform_account_id="104829104829102",
            display_name="Brand Page Downtown",
        )
        acc.set_access_token(raw_token)
        db.session.add(acc)
        db.session.commit()

        # Raw token should NOT be plaintext in database column
        assert acc.encrypted_access_token != raw_token
        # Decrypted token must match
        assert acc.get_access_token() == raw_token


def test_verify_facebook_page_demo_mode():
    ok, page_info, err = meta_service.verify_facebook_page("demo_page_123", "demo_token_abc")
    assert ok is True
    assert page_info is not None
    assert page_info["id"] == "demo_page_123"
    assert err is None


@patch("requests.get")
def test_verify_facebook_page_real_mocked(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "104829104829102",
        "name": "Acme Marketing HQ",
        "category": "Marketing Agency",
    }
    mock_get.return_value = mock_resp

    ok, page_info, err = meta_service.verify_facebook_page("104829104829102", "valid_meta_token")
    assert ok is True
    assert page_info["name"] == "Acme Marketing HQ"
    assert err is None


@patch("requests.post")
def test_publish_to_facebook_page_feed(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "104829104829102_987654321"}
    mock_post.return_value = mock_resp

    ok, post_id, err = meta_service.publish_to_facebook_page(
        page_id="104829104829102",
        access_token="real_token_xyz",
        message="Announcing our latest product update! #growth",
    )
    assert ok is True
    assert post_id == "104829104829102_987654321"
    assert err is None


@patch("requests.post")
def test_publish_to_facebook_page_photo_and_comment(mock_post):
    mock_photo_resp = MagicMock()
    mock_photo_resp.status_code = 200
    mock_photo_resp.json.return_value = {"id": "photo_111", "post_id": "104829104829102_222"}

    mock_comment_resp = MagicMock()
    mock_comment_resp.status_code = 200
    mock_comment_resp.json.return_value = {"id": "comment_333"}

    mock_post.side_effect = [mock_photo_resp, mock_comment_resp]

    ok, post_id, err = meta_service.publish_to_facebook_page(
        page_id="104829104829102",
        access_token="real_token_xyz",
        message="Visual post caption",
        image_bytes=b"dummy-png-bytes",
        image_filename="banner.png",
        first_comment="First comment link: https://example.com",
    )
    assert ok is True
    assert post_id == "104829104829102_222"
    assert err is None
    assert mock_post.call_count == 2


@patch("requests.post")
def test_publish_to_facebook_page_meta_error_handling(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "error": {
            "message": "Error validating access token: The session is invalid because the user logged out.",
            "type": "OAuthException",
            "code": 190,
        }
    }
    mock_post.return_value = mock_resp

    ok, post_id, err = meta_service.publish_to_facebook_page(
        page_id="104829104829102",
        access_token="expired_token",
        message="Test message",
    )
    assert ok is False
    assert post_id is None
    assert "Error validating access token" in err


def test_test_connection_endpoint(app, client, tenant_a, user_a):
    with app.app_context():
        acc = SocialAccount(
            tenant_id=tenant_a.id,
            platform=Platform.FACEBOOK,
            platform_account_id="demo_page_test",
            display_name="Demo Test Page",
        )
        acc.set_access_token("demo_token_123")
        db.session.add(acc)
        db.session.commit()
        acc_id = acc.id

    with client.session_transaction() as sess:
        sess["_user_id"] = user_a.id
        sess["active_tenant_id"] = tenant_a.id

    # POST to test connection
    resp = client.post(f"/app/settings/social-accounts/{acc_id}/test", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        reloaded = db.session.get(SocialAccount, acc_id)
        assert reloaded.status == SocialAccountStatus.CONNECTED


@patch("requests.post")
def test_publish_multi_photo_to_facebook_page(mock_post):
    up1 = MagicMock()
    up1.status_code = 200
    up1.json.return_value = {"id": "fb_photo_1"}

    up2 = MagicMock()
    up2.status_code = 200
    up2.json.return_value = {"id": "fb_photo_2"}

    feed = MagicMock()
    feed.status_code = 200
    feed.json.return_value = {"id": "104829_999888"}

    mock_post.side_effect = [up1, up2, feed]

    ok, post_id, err = meta_service.publish_to_facebook_page(
        page_id="104829",
        access_token="EAA_valid_token",
        message="Multi-photo gallery",
        media_items=[
            ("photo1.jpg", b"bytes1", "image/jpeg"),
            ("photo2.png", b"bytes2", "image/png"),
        ],
    )
    assert ok is True
    assert post_id == "104829_999888"
    assert err is None
    assert mock_post.call_count == 3
    assert mock_post.call_args_list[0].kwargs["data"]["published"] == "false"
    assert mock_post.call_args_list[2].args[0].endswith("/104829/feed")


@patch("requests.post")
def test_publish_video_to_facebook_page(mock_post):
    vid_resp = MagicMock()
    vid_resp.status_code = 200
    vid_resp.json.return_value = {"id": "104829_video_12345"}
    mock_post.return_value = vid_resp

    ok, post_id, err = meta_service.publish_to_facebook_page(
        page_id="104829",
        access_token="EAA_valid_token",
        message="Check out our new reel!",
        media_items=[
            ("promo.mp4", b"fake_mp4_bytes", "video/mp4"),
        ],
    )
    assert ok is True
    assert post_id == "104829_video_12345"
    assert err is None
    assert mock_post.call_args.args[0].endswith("/104829/videos")
    assert mock_post.call_args.kwargs["data"]["description"] == "Check out our new reel!"


def test_ai_generation_preserves_manual_media(app, db, tenant_a, user_a, client):
    import io
    from PIL import Image
    from werkzeug.datastructures import FileStorage
    from app.models.media_asset import MediaSourceType
    from app.models.post import Post
    from app.services import media_service

    with app.app_context():
        stream = io.BytesIO()
        Image.new("RGB", (120, 120), color="red").save(stream, format="PNG")
        stream.seek(0)
        asset, err = media_service.save_media_file(
            FileStorage(stream=stream, filename="manual.png", content_type="image/png"),
            tenant_id=tenant_a.id,
            user_id=user_a.id,
            source_type=MediaSourceType.UPLOADED,
        )
        assert err is None
        asset_id = asset.id

    with client.session_transaction() as sess:
        sess["_user_id"] = user_a.id
        sess["active_tenant_id"] = tenant_a.id

    resp = client.post(
        "/api/v1/posts/generate",
        json={"topic": "Product launch", "media_asset_id": asset_id},
    )
    assert resp.status_code == 202
    data = resp.get_json()
    post_id = data["post_id"]
    assert post_id is not None

    with app.app_context():
        post = content_service.get_tenant_post(post_id, tenant_a.id)
        assert len(post.media_links) == 1
        assert post.media_links[0].media_asset_id == asset_id


