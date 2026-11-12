"""Meta Graph API publishing and authentication service.

Supports both direct Page ID + Access Token publishing and full OAuth 2.0.
Supports Facebook Pages, photos, feeds, and first comments.
"""
import io
import logging
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlencode

import requests
from flask import current_app

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def verify_facebook_page(page_id: str, access_token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Verify that a Page ID and Page Access Token are valid with Meta Graph API.
    
    Returns: (is_valid, page_info_dict, error_message)
    """
    if not page_id or not access_token:
        return False, None, "Page ID and Access Token are required."

    page_id = page_id.strip()
    access_token = access_token.strip()

    # Demo/mock bypass for testing without active Meta app
    if page_id.startswith("demo_") or access_token.startswith("demo_") or access_token == "mock_token":
        return True, {
            "id": page_id,
            "name": f"Verified Page ({page_id})",
            "category": "Marketing & Content Brand",
            "mock": True,
        }, None

    url = f"{GRAPH_BASE_URL}/{page_id}"
    params = {
        "fields": "id,name,category,link,picture",
        "access_token": access_token,
    }

    try:
        resp = requests.get(url, params=params, timeout=12)
        data = resp.json()

        if resp.status_code == 200 and "id" in data:
            return True, data, None

        error_data = data.get("error", {})
        err_msg = error_data.get("message", f"Meta verification returned HTTP {resp.status_code}")
        err_code = error_data.get("code")
        logger.warning(f"Meta Page verification failed: {err_msg} (code={err_code})")
        return False, None, f"Meta API Error ({err_code}): {err_msg}"

    except requests.RequestException as exc:
        logger.error(f"Network error connecting to Meta Graph API: {exc}")
        return False, None, f"Could not reach Meta Graph API: {str(exc)}"


def publish_to_facebook_page(
    page_id: str,
    access_token: str,
    message: str,
    image_bytes: Optional[bytes] = None,
    image_filename: str = "post.png",
    first_comment: Optional[str] = None,
    media_items: Optional[List[Tuple[str, bytes, str]]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Publish a post (text, single photo, or multi-photo) to a Facebook Page via Meta Graph API.

    media_items: optional list of (filename, bytes, mime_type).
    Returns: (success: bool, platform_post_id: str | None, error_message: str | None)
    """
    if not page_id or not access_token:
        return False, None, "Missing Facebook Page ID or Access Token."

    page_id = page_id.strip()
    access_token = access_token.strip()

    # Demo mode handling
    if page_id.startswith("demo_") or access_token.startswith("demo_") or access_token == "mock_token":
        import uuid
        mock_id = f"{page_id}_{uuid.uuid4().hex[:12]}"
        logger.info(f"[MOCK META] Successfully simulated post to Page {page_id} -> ID {mock_id}")
        return True, mock_id, None

    # Normalize attached photos list
    images_to_publish: List[Tuple[str, bytes, str]] = []
    if media_items:
        images_to_publish = [m for m in media_items if m[1]]
    elif image_bytes:
        images_to_publish = [(image_filename, image_bytes, "image/png")]

    try:
        post_id = None

        # Check if publishing a video asset
        video_items = [
            m for m in images_to_publish
            if (m[2] and m[2].startswith("video/"))
            or (m[0] and m[0].lower().endswith((".mp4", ".mov", ".m4v", ".webm")))
        ]

        if video_items:
            # Facebook Video post endpoint: /{page_id}/videos
            vname, vdata, vmime = video_items[0]
            video_url = f"{GRAPH_BASE_URL}/{page_id}/videos"
            payload = {
                "description": message,
                "access_token": access_token,
            }
            files = {
                "source": (vname, io.BytesIO(vdata), vmime or "video/mp4")
            }
            resp = requests.post(video_url, data=payload, files=files, timeout=60)
            res_data = resp.json()

            if resp.status_code != 200 or "id" not in res_data:
                err = res_data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                return False, None, f"Meta Video Publish Error: {err}"

            post_id = res_data.get("id")

        elif len(images_to_publish) > 1:
            # Multi-photo post: upload each photo unpublished, then attach to /{page_id}/feed
            import json
            photo_url = f"{GRAPH_BASE_URL}/{page_id}/photos"
            attached_media_ids: List[str] = []

            for fname, img_data, mime in images_to_publish:
                up_resp = requests.post(
                    photo_url,
                    data={"access_token": access_token, "published": "false"},
                    files={"source": (fname, io.BytesIO(img_data), mime or "image/jpeg")},
                    timeout=30,
                )
                up_data = up_resp.json()
                if up_resp.status_code != 200 or "id" not in up_data:
                    err = up_data.get("error", {}).get("message", f"HTTP {up_resp.status_code}")
                    return False, None, f"Meta Multi-Photo Upload Error: {err}"
                attached_media_ids.append(up_data["id"])

            feed_url = f"{GRAPH_BASE_URL}/{page_id}/feed"
            feed_payload = {
                "message": message,
                "access_token": access_token,
            }
            for idx, fb_media_id in enumerate(attached_media_ids):
                feed_payload[f"attached_media[{idx}]"] = json.dumps({"media_fbid": fb_media_id})

            resp = requests.post(feed_url, data=feed_payload, timeout=30)
            res_data = resp.json()
            if resp.status_code != 200 or "id" not in res_data:
                err = res_data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                return False, None, f"Meta Multi-Photo Publish Error: {err}"
            post_id = res_data.get("id")

        elif len(images_to_publish) == 1:
            # Single photo post endpoint: /{page_id}/photos
            fname, img_data, mime = images_to_publish[0]
            photo_url = f"{GRAPH_BASE_URL}/{page_id}/photos"
            payload = {
                "caption": message,
                "access_token": access_token,
                "published": "true",
            }
            files = {
                "source": (fname, io.BytesIO(img_data), mime or "image/png")
            }

            resp = requests.post(photo_url, data=payload, files=files, timeout=30)
            res_data = resp.json()

            if resp.status_code != 200 or "id" not in res_data:
                err = res_data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                return False, None, f"Meta Photo Publish Error: {err}"

            # Photos endpoint returns { "id": "photo_id", "post_id": "pageid_postid" }
            post_id = res_data.get("post_id") or res_data.get("id")

        else:
            # Text/Link post endpoint: /{page_id}/feed
            feed_url = f"{GRAPH_BASE_URL}/{page_id}/feed"
            payload = {
                "message": message,
                "access_token": access_token,
            }

            resp = requests.post(feed_url, data=payload, timeout=20)
            res_data = resp.json()

            if resp.status_code != 200 or "id" not in res_data:
                err = res_data.get("error", {}).get("message", f"HTTP {resp.status_code}")
                return False, None, f"Meta Feed Publish Error: {err}"

            post_id = res_data.get("id")

        # Handle First Comment if configured
        if first_comment and post_id:
            try:
                comment_url = f"{GRAPH_BASE_URL}/{post_id}/comments"
                comment_payload = {
                    "message": first_comment,
                    "access_token": access_token,
                }
                c_resp = requests.post(comment_url, data=comment_payload, timeout=15)
                if c_resp.status_code != 200:
                    logger.warning(f"First comment failed for post {post_id}: {c_resp.text}")
            except Exception as e:
                logger.warning(f"Error publishing first comment: {e}")

        return True, post_id, None

    except requests.RequestException as exc:
        logger.exception(f"Network failure while publishing to Meta: {exc}")
        return False, None, f"Network error during publishing: {str(exc)}"


def get_facebook_oauth_dialog_url(tenant_id: str, state: str) -> Optional[str]:
    """Build the official Meta OAuth Authorization URL."""
    app_id = current_app.config.get("META_APP_ID")
    redirect_uri = current_app.config.get("META_REDIRECT_URI")

    if not app_id or not redirect_uri:
        return None

    scopes = [
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
        "public_profile",
    ]

    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(scopes),
    }

    return f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?{urlencode(params)}"


def exchange_oauth_code_for_pages(code: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
    """Exchange OAuth code for long-lived user token and fetch user's Facebook Pages."""
    app_id = current_app.config.get("META_APP_ID")
    app_secret = current_app.config.get("META_APP_SECRET")
    redirect_uri = current_app.config.get("META_REDIRECT_URI")

    if not app_id or not app_secret or not redirect_uri:
        return False, [], "Meta OAuth is not configured with app_id and app_secret in environment."

    # 1. Exchange code for short-lived access token
    token_url = f"{GRAPH_BASE_URL}/oauth/access_token"
    token_params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }

    try:
        resp = requests.get(token_url, params=token_params, timeout=15)
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            err = data.get("error", {}).get("message", "Failed to retrieve access token")
            return False, [], f"Token exchange failed: {err}"

        short_token = data["access_token"]

        # 2. Exchange for 60-day long-lived User Access Token
        long_params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        }
        long_resp = requests.get(token_url, params=long_params, timeout=15)
        long_data = long_resp.json()
        user_access_token = long_data.get("access_token") or short_token

        # 3. Retrieve all Facebook Pages managed by user: GET /me/accounts
        pages_url = f"{GRAPH_BASE_URL}/me/accounts"
        pages_params = {
            "access_token": user_access_token,
            "fields": "id,name,category,access_token,tasks,link",
        }
        pages_resp = requests.get(pages_url, params=pages_params, timeout=15)
        pages_data = pages_resp.json()

        if pages_resp.status_code != 200:
            err = pages_data.get("error", {}).get("message", "Failed to fetch Facebook Pages")
            return False, [], f"Fetching pages failed: {err}"

        page_list = pages_data.get("data", [])
        return True, page_list, None

    except requests.RequestException as exc:
        return False, [], f"Meta OAuth connection error: {str(exc)}"

