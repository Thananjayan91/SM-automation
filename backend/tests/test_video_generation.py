"""Tests for AI Video Generation: Narration, Voiceover TTS, FFmpeg slideshow, and API endpoints."""
import os
import tempfile
import pytest
from io import BytesIO
from PIL import Image

from app.services.ai.tts_provider import MockTTSProvider, OpenAITTSProvider, SUPPORTED_VOICES
from app.services.ai.text_provider import MockTextProvider
from app.services.video_service import (
    build_slideshow_video,
    get_ffmpeg_binary_path,
    probe_audio_duration,
)
from app.services import media_service
from tests.conftest import create_user, create_tenant


def _create_sample_jpeg(width: int = 400, height: int = 400, color: str = "red") -> bytes:
    """Create a sample JPEG in memory."""
    buf = BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestAITTSProvider:
    def test_mock_tts_provider_generates_audio(self):
        tts = MockTTSProvider()
        result = tts.generate_speech("Welcome to AI Social Publisher. This is a test voiceover.", voice="nova")
        assert result.audio_bytes is not None
        assert len(result.audio_bytes) > 500
        assert result.voice_used == "nova"
        assert result.duration_secs >= 3.0

    def test_supported_voices_contains_nova(self):
        assert "nova" in SUPPORTED_VOICES
        assert "alloy" in SUPPORTED_VOICES
        assert "echo" in SUPPORTED_VOICES


class TestAINarrationGeneration:
    def test_narration_english(self):
        provider = MockTextProvider()
        res_15 = provider.generate_narration("AI marketing tools", language="english", duration_hint=15)
        assert res_15.script
        assert res_15.word_count > 10
        assert "AI marketing tools" in res_15.script

        res_30 = provider.generate_narration("AI marketing tools", language="english", duration_hint=30)
        assert res_30.word_count > res_15.word_count

    def test_narration_tamil(self):
        provider = MockTextProvider()
        res = provider.generate_narration("தொழில்நுட்பம்", language="tamil", duration_hint=15)
        assert "தொழில்நுட்பம்" in res.script
        assert res.word_count >= 10

    def test_narration_sinhala(self):
        provider = MockTextProvider()
        res = provider.generate_narration("නව තාක්ෂණය", language="sinhala", duration_hint=15)
        assert "නව තාක්ෂණය" in res.script
        assert res.word_count >= 10


class TestFFmpegSlideshowRender:
    def test_ffmpeg_binary_available(self):
        bin_path = get_ffmpeg_binary_path()
        assert bin_path is not None
        assert os.path.exists(bin_path)

    def test_build_slideshow_video_end_to_end(self):
        bin_path = get_ffmpeg_binary_path()
        assert bin_path is not None

        temp_dir = tempfile.mkdtemp(prefix="test_video_")
        try:
            # Create 2 sample images
            img1_path = os.path.join(temp_dir, "slide_01.jpg")
            img2_path = os.path.join(temp_dir, "slide_02.jpg")
            with open(img1_path, "wb") as f:
                f.write(_create_sample_jpeg(300, 300, "blue"))
            with open(img2_path, "wb") as f:
                f.write(_create_sample_jpeg(300, 300, "green"))

            # Create audio track using MockTTS
            tts = MockTTSProvider()
            audio_res = tts.generate_speech("Hello world, this is a test audio.", voice="nova")
            audio_path = os.path.join(temp_dir, "audio.wav")
            with open(audio_path, "wb") as f:
                f.write(audio_res.audio_bytes)

            output_mp4 = os.path.join(temp_dir, "output.mp4")

            success, err = build_slideshow_video(
                image_paths=[img1_path, img2_path],
                audio_path=audio_path,
                output_mp4_path=output_mp4,
                width=360,
                height=640,
                audio_duration=3.0,
                ffmpeg_bin=bin_path,
            )

            assert success is True, f"FFmpeg failed with error: {err}"
            assert os.path.exists(output_mp4)
            assert os.path.getsize(output_mp4) > 1000  # Valid MP4
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestVideoAPIEndpoints:
    def test_video_voices_endpoint(self, client, db):
        user = create_user("test_video_voices@example.com")
        tenant = create_tenant("Video Workspace", owner=user)
        db.session.commit()

        # Login
        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        resp = client.get("/api/v1/video/voices")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "voices" in data
        assert any(v["id"] == "nova" for v in data["voices"])

    def test_video_narration_endpoint(self, client, db):
        user = create_user("test_video_narration@example.com")
        tenant = create_tenant("Video Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        payload = {
            "topic": "5 tips for healthy living",
            "language": "english",
            "duration": 15
        }
        resp = client.post("/api/v1/video/narration", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "script" in data
        assert data["word_count"] > 5

    def test_video_voiceover_endpoint(self, client, db):
        user = create_user("test_video_voiceover@example.com")
        tenant = create_tenant("Video Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        payload = {
            "script": "Welcome to our channel. Stay tuned for amazing daily updates.",
            "voice": "nova"
        }
        resp = client.post("/api/v1/video/voiceover", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "audio_url" in data
        assert "audio_id" in data
        assert data["voice"] == "nova"

    def test_web_generate_video_page_loads(self, client, db):
        user = create_user("test_video_page@example.com")
        tenant = create_tenant("Video Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        resp = client.get("/app/generate-video")
        assert resp.status_code == 200
        assert b"Generate AI Video" in resp.data
        assert b"Pexels" in resp.data

    def test_video_render_endpoint_and_create_post(self, client, db, monkeypatch):
        user = create_user("test_video_render@example.com")
        tenant = create_tenant("Video Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        # 1. Generate voiceover first
        vo_resp = client.post("/api/v1/video/voiceover", json={
            "script": "Testing end to end slideshow rendering with FFmpeg.",
            "voice": "nova"
        })
        assert vo_resp.status_code == 200
        vo_data = vo_resp.get_json()

        # 2. Mock image downloader to write sample JPEGs locally without internet
        from app.services import video_service
        def fake_download(image_url, dest_path, timeout=12):
            with open(dest_path, "wb") as f:
                f.write(_create_sample_jpeg(400, 400, "purple"))
            return True

        monkeypatch.setattr(video_service, "download_image_to_file", fake_download)

        # 3. Call /api/v1/video/render
        render_resp = client.post("/api/v1/video/render", json={
            "audio_id": vo_data["audio_id"],
            "audio_url": vo_data["audio_url"],
            "image_urls": [
                "https://images.pexels.com/photos/1/test1.jpg",
                "https://images.pexels.com/photos/2/test2.jpg",
                "https://images.pexels.com/photos/3/test3.jpg",
                "https://images.pexels.com/photos/4/test4.jpg",
            ],
            "aspect_ratio": "9:16",
            "topic": "Test Product Showcase"
        })
        assert render_resp.status_code == 200
        render_data = render_resp.get_json()
        assert render_data["success"] is True
        assert render_data["asset_id"]
        assert render_data["size_bytes"] > 1000

        # 4. Create post from generated video
        post_resp = client.post("/app/generate-video/create-post", data={
            "asset_id": render_data["asset_id"],
            "topic": "Test Product Showcase",
            "script": "Testing end to end slideshow rendering with FFmpeg."
        }, follow_redirects=False)
        assert post_resp.status_code == 302
        assert "/app/posts/" in post_resp.headers["Location"]
