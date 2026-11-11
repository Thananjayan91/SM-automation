"""Tests for Vercel Blob storage integration and Vercel WSGI entrypoint."""
import io
from unittest.mock import patch, MagicMock
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.models.media_asset import MediaSourceType
from app.services import media_service


def _dummy_png() -> FileStorage:
    stream = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="indigo")
    img.save(stream, format="PNG")
    stream.seek(0)
    return FileStorage(stream=stream, filename="banner.png", content_type="image/png")


def test_save_and_delete_media_with_vercel_blob(app, db, user_a, tenant_a):
    """When BLOB_READ_WRITE_TOKEN is set, media uploads directly to Vercel Blob REST API."""
    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 200
    mock_put_resp.json.return_value = {
        "url": "https://abc123.public.blob.vercel-storage.com/test/banner.png",
        "pathname": "test/banner.png",
    }

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.content = b"fake-png-bytes"

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200

    with app.app_context():
        app.config["BLOB_READ_WRITE_TOKEN"] = "vercel_blob_rw_test_token"
        try:
            with patch("app.services.media_service.requests.put", return_value=mock_put_resp) as mock_put:
                asset, err = media_service.save_media_file(
                    file_storage=_dummy_png(),
                    tenant_id=tenant_a.id,
                    user_id=user_a.id,
                    source_type=MediaSourceType.AI_GENERATED,
                )

            assert err is None
            assert asset is not None
            assert asset.storage_url == "https://abc123.public.blob.vercel-storage.com/test/banner.png"
            mock_put.assert_called_once()
            headers = mock_put.call_args.kwargs["headers"]
            assert headers["Authorization"] == "Bearer vercel_blob_rw_test_token"
            assert headers["x-api-version"] == "7"

            # Reading bytes should fetch via CDN URL
            with patch("app.services.media_service.requests.get", return_value=mock_get_resp) as mock_get:
                raw = media_service.read_media_bytes(asset)
                assert raw == b"fake-png-bytes"
                mock_get.assert_called_once_with(asset.storage_url, timeout=15)

            # Deleting asset should invoke Vercel Blob delete API
            with patch("app.services.media_service.requests.post", return_value=mock_post_resp) as mock_post:
                ok, del_err = media_service.delete_media_asset(asset.id, tenant_a.id)
                assert ok is True
                assert del_err is None
                mock_post.assert_called_once()
                assert mock_post.call_args.kwargs["json"] == {"urls": [asset.storage_url]}
        finally:
            app.config["BLOB_READ_WRITE_TOKEN"] = ""
