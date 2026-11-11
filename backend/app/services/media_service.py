"""Media storage and management service."""
import logging
import os
import uuid
from typing import Optional

import requests
from flask import current_app
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models.media_asset import MediaAsset, MediaSourceType
from .security_service import validate_uploaded_image

logger = logging.getLogger(__name__)

VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"


def _get_blob_token() -> str:
    """Return Vercel Blob read/write token if configured."""
    return (
        current_app.config.get("BLOB_READ_WRITE_TOKEN")
        or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
    ).strip()


def _upload_to_vercel_blob(
    storage_key: str, data_bytes: bytes, content_type: str, token: str
) -> tuple[Optional[str], Optional[str]]:
    """Upload image bytes to Vercel Blob via REST API. Returns (url, error)."""
    url = f"{VERCEL_BLOB_API_URL}/{storage_key}"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-version": "7",
        "content-type": content_type or "application/octet-stream",
        "x-add-random-suffix": "0",
    }
    try:
        resp = requests.put(url, headers=headers, data=data_bytes, timeout=20)
        if resp.status_code == 200:
            payload = resp.json()
            blob_url = payload.get("url")
            if blob_url:
                return blob_url, None
        return None, f"Vercel Blob upload failed (HTTP {resp.status_code}): {resp.text}"
    except requests.RequestException as exc:
        logger.error(f"Network error uploading to Vercel Blob: {exc}")
        return None, f"Could not reach Vercel Blob storage: {str(exc)}"


def _delete_from_vercel_blob(blob_url: str, token: str) -> None:
    """Delete an asset URL from Vercel Blob via REST API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-version": "7",
        "content-type": "application/json",
    }
    try:
        requests.post(
            f"{VERCEL_BLOB_API_URL}/delete",
            headers=headers,
            json={"urls": [blob_url]},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning(f"Failed to delete from Vercel Blob ({blob_url}): {exc}")


def get_media_storage_path(tenant_id: str) -> str:
    """Return the absolute filesystem path for local media storage."""
    base = os.path.join(current_app.instance_path, "media", tenant_id)
    os.makedirs(base, exist_ok=True)
    return base


def save_media_file(file_storage, tenant_id: str, user_id: Optional[str] = None, source_type: MediaSourceType = MediaSourceType.UPLOADED, labels: Optional[list] = None, notes: Optional[str] = None) -> tuple[Optional[MediaAsset], Optional[str]]:
    """Validate, store, and record a new media asset for a tenant.

    Uses Vercel Blob when BLOB_READ_WRITE_TOKEN is configured; otherwise falls back to local disk.
    Returns (media_asset, error_message).
    """
    is_valid, error, metadata = validate_uploaded_image(file_storage)
    if not is_valid:
        return None, error

    file_id = str(uuid.uuid4())
    safe_name = secure_filename(metadata["filename"])
    ext = metadata["extension"]
    storage_key = f"{tenant_id}/{file_id}.{ext}"

    blob_token = _get_blob_token()
    if blob_token:
        file_storage.seek(0)
        data_bytes = file_storage.read()
        blob_url, blob_err = _upload_to_vercel_blob(
            storage_key=storage_key,
            data_bytes=data_bytes,
            content_type=metadata["mime_type"],
            token=blob_token,
        )
        if blob_err or not blob_url:
            return None, blob_err or "Failed to upload media to Vercel Blob."
        storage_url = blob_url
    else:
        # Local file saving
        dest_dir = get_media_storage_path(tenant_id)
        file_path = os.path.join(dest_dir, f"{file_id}.{ext}")
        file_storage.seek(0)
        file_storage.save(file_path)
        storage_url = f"/app/media/file/{file_id}"

    asset = MediaAsset(
        id=file_id,
        tenant_id=tenant_id,
        created_by=user_id,
        storage_key=storage_key,
        storage_url=storage_url,
        original_filename=safe_name,
        mime_type=metadata["mime_type"],
        size_bytes=metadata["size_bytes"],
        width=metadata["width"],
        height=metadata["height"],
        source_type=source_type,
        notes=notes,
        labels_json=labels or [],
    )
    db.session.add(asset)
    db.session.commit()

    return asset, None


def get_tenant_media(tenant_id: str, label: Optional[str] = None, search: Optional[str] = None, page: int = 1, per_page: int = 24) -> tuple[list[MediaAsset], int]:
    """Retrieve media assets belonging strictly to the active tenant with optional filters."""
    query = MediaAsset.query.filter_by(tenant_id=tenant_id)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            (MediaAsset.original_filename.ilike(search_pattern)) |
            (MediaAsset.notes.ilike(search_pattern))
        )

    query = query.order_by(MediaAsset.created_at.desc())
    total = query.count()
    assets = query.offset((page - 1) * per_page).limit(per_page).all()

    if label:
        assets = [a for a in assets if label in (a.labels_json or [])]

    return assets, total


def get_media_asset(asset_id: str, tenant_id: str) -> Optional[MediaAsset]:
    """Retrieve an asset guaranteeing it belongs to the active tenant."""
    return MediaAsset.query.filter_by(id=asset_id, tenant_id=tenant_id).first()


def delete_media_asset(asset_id: str, tenant_id: str) -> tuple[bool, Optional[str]]:
    """Delete a media asset from storage (Vercel Blob or local disk) and database."""
    asset = get_media_asset(asset_id, tenant_id)
    if not asset:
        return False, "Media asset not found."

    if asset.storage_url and asset.storage_url.startswith("http"):
        blob_token = _get_blob_token()
        if blob_token and "blob.vercel-storage.com" in asset.storage_url:
            _delete_from_vercel_blob(asset.storage_url, blob_token)
    else:
        try:
            dest_dir = get_media_storage_path(tenant_id)
            ext = asset.original_filename.rsplit(".", 1)[-1].lower() if "." in asset.original_filename else "jpg"
            file_path = os.path.join(dest_dir, f"{asset.id}.{ext}")
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    db.session.delete(asset)
    db.session.commit()
    return True, None


def read_media_bytes(asset: MediaAsset) -> Optional[bytes]:
    """Read raw media file bytes from Vercel Blob CDN or local disk."""
    if not asset:
        return None

    if asset.storage_url and asset.storage_url.startswith("http"):
        try:
            resp = requests.get(asset.storage_url, timeout=15)
            if resp.status_code == 200:
                return resp.content
        except requests.RequestException as exc:
            logger.error(f"Failed to read remote media asset ({asset.storage_url}): {exc}")
        return None

    dest_dir = get_media_storage_path(asset.tenant_id)
    ext = asset.original_filename.rsplit(".", 1)[-1].lower() if "." in asset.original_filename else "jpg"
    file_path = os.path.join(dest_dir, f"{asset.id}.{ext}")
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()
    return None

