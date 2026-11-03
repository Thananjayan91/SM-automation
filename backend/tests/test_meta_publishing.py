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

