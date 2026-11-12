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
    storage_key: str, data_bytes: bytes, content_type: str, token: str, timeout: int = 30
) -> tuple[Optional[str], Optional[str]]:
    """Upload bytes to Vercel Blob via REST API. Returns (url, error)."""
    url = f"{VERCEL_BLOB_API_URL}/{storage_key}"
    headers = {
        "Authorization": f"Bearer {token}",
        "x-api-version": "7",
        "content-type": content_type or "application/octet-stream",
        "x-add-random-suffix": "0",
    }
    try:
        resp = requests.put(url, headers=headers, data=data_bytes, timeout=timeout)
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


def save_video_file(
    video_bytes: bytes,
    tenant_id: str,
    user_id: Optional[str] = None,
    filename: str = "generated_video.mp4",
    width: int = 1080,
    height: int = 1920,
    notes: Optional[str] = None,
    labels: Optional[list] = None,
) -> tuple[Optional[MediaAsset], Optional[str]]:
    """Save an MP4 video file to Vercel Blob (or local storage fallback) and record a MediaAsset."""
    if not video_bytes or len(video_bytes) == 0:
        return None, "Empty video file provided."

    file_id = str(uuid.uuid4())
    safe_name = secure_filename(filename or "video.mp4")
    if not safe_name.endswith(".mp4"):
        safe_name += ".mp4"

    storage_key = f"{tenant_id}/videos/{file_id}.mp4"
    size_bytes = len(video_bytes)

    blob_token = _get_blob_token()
    if blob_token:
        blob_url, blob_err = _upload_to_vercel_blob(
            storage_key=storage_key,
            data_bytes=video_bytes,
            content_type="video/mp4",
            token=blob_token,
            timeout=45,
        )
        if blob_err or not blob_url:
            return None, blob_err or "Failed to upload video to Vercel Blob."
        storage_url = blob_url
    else:
        dest_dir = get_media_storage_path(tenant_id)
        file_path = os.path.join(dest_dir, f"{file_id}.mp4")
        with open(file_path, "wb") as f:
            f.write(video_bytes)
        storage_url = f"/app/media/file/{file_id}"

    asset = MediaAsset(
        id=file_id,
        tenant_id=tenant_id,
        created_by=user_id,
        storage_key=storage_key,
        storage_url=storage_url,
        original_filename=safe_name,
        mime_type="video/mp4",
        size_bytes=size_bytes,
        width=width,
        height=height,
        source_type=MediaSourceType.AI_GENERATED,
        notes=notes,
        labels_json=labels or ["video", "ai-generated"],
    )
    db.session.add(asset)
    db.session.commit()
    return asset, None


def save_voiceover_audio(
    audio_bytes: bytes,
    tenant_id: str,
    mime_type: str = "audio/mpeg",
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Store generated TTS voiceover audio in Vercel Blob or local disk.

    Returns (audio_url, audio_id, error_message).
    """
    if not audio_bytes:
        return None, None, "Empty audio data."

    audio_id = str(uuid.uuid4())
    ext = "wav" if "wav" in (mime_type or "").lower() else "mp3"
    storage_key = f"{tenant_id}/audio/{audio_id}.{ext}"

    blob_token = _get_blob_token()
    if blob_token:
        blob_url, blob_err = _upload_to_vercel_blob(
            storage_key=storage_key,
            data_bytes=audio_bytes,
            content_type=mime_type,
            token=blob_token,
            timeout=30,
        )
        if blob_err or not blob_url:
            return None, None, blob_err or "Failed to upload audio to Vercel Blob."
        return blob_url, f"{audio_id}.{ext}", None

    dest_dir = get_media_storage_path(tenant_id)
    file_path = os.path.join(dest_dir, f"audio_{audio_id}.{ext}")
    with open(file_path, "wb") as f:
        f.write(audio_bytes)
    return f"/app/media/audio/{audio_id}.{ext}", f"{audio_id}.{ext}", None


def read_voiceover_audio(tenant_id: str, audio_id_with_ext: str, audio_url: Optional[str] = None) -> Optional[bytes]:
    """Read voiceover audio bytes from Vercel Blob URL or local disk."""
    if audio_url and audio_url.startswith("http"):
        try:
            resp = requests.get(audio_url, timeout=20)
            if resp.status_code == 200:
                return resp.content
        except requests.RequestException as exc:
            logger.error(f"Failed to download voiceover audio ({audio_url}): {exc}")

    safe_key = secure_filename(audio_id_with_ext or "")
    if not safe_key:
        return None
    dest_dir = get_media_storage_path(tenant_id)
    file_path = os.path.join(dest_dir, f"audio_{safe_key}")
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()
    return None


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

