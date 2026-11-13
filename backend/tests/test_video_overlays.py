"""Unit and integration tests for video text overlays, Ken Burns animations, and template system."""
import io
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from app.models.media_asset import MediaAsset, MediaSourceType
from app.models.video_template import VideoTemplate
from app.services.video_text_renderer import (
    composite_scene,
    parse_color,
    get_fonts_directory,
    SYSTEM_PRESET_TEMPLATES,
)
from app.services.video_service import (
    get_zoompan_filter,
    build_slideshow_video,
    generate_video_from_assets,
    get_ffmpeg_binary_path,
)
from app.services.ai.text_provider import MockTextProvider


from tests.conftest import create_user, create_tenant


class TestPillowTextRenderer:
    """Tests for Pillow-based scene text compositing."""

    def test_parse_color_formats(self):
        assert parse_color("#FFFFFF") == (255, 255, 255, 255)
        assert parse_color("#000000") == (0, 0, 0, 255)
        assert parse_color("rgba(0, 0, 0, 0.5)") == (0, 0, 0, 128)
        assert parse_color("rgb(255, 0, 0)") == (255, 0, 0, 255)
        assert parse_color(None, default=(10, 20, 30, 255)) == (10, 20, 30, 255)

    def test_bundled_fonts_exist(self):
        fonts_dir = get_fonts_directory()
        assert os.path.isdir(fonts_dir), "static/fonts directory must exist"
        font_files = os.listdir(fonts_dir)
        assert any(f.endswith(".ttf") for f in font_files), "At least one .ttf font must be present"

    def test_composite_scene_with_overlay(self):
        # Create small test base image
        base = Image.new("RGB", (600, 800), (30, 60, 120))
        buf = io.BytesIO()
        base.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        texts = [
            {
                "content": "5 AMAZING BENEFITS\nOF GREEN TEA",
                "x_percent": 50,
                "y_percent": 45,
                "font_family": "Montserrat",
                "font_size": 40,
                "color": "#FFFFFF",
                "stroke_color": "#000000",
                "stroke_width": 2,
                "shadow": {"enabled": True, "color": "rgba(0,0,0,0.8)", "blur": 6, "offsetX": 2, "offsetY": 2},
                "background": {"enabled": True, "color": "rgba(0,0,0,0.5)", "padding": 12, "border_radius": 8},
                "max_width_percent": 85,
                "text_align": "center",
            }
        ]

        out_png = composite_scene(raw_bytes, texts=texts, canvas_w=720, canvas_h=1280)
        assert isinstance(out_png, bytes)
        assert len(out_png) > 1000

        # Validate rendered dimensions
        with Image.open(io.BytesIO(out_png)) as img:
            assert img.size == (720, 1280)
            assert img.format == "PNG"

    def test_composite_scene_without_text(self):
        base = Image.new("RGB", (400, 400), (50, 100, 150))
        buf = io.BytesIO()
        base.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        out_png = composite_scene(raw_bytes, texts=[], canvas_w=720, canvas_h=720)
        with Image.open(io.BytesIO(out_png)) as img:
            assert img.size == (720, 720)


class TestKenBurnsAnimations:
    """Tests for FFmpeg zoompan animation filters."""

    def test_zoompan_filter_presets(self):
        presets = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "ken_burns", "static"]
        for p in presets:
            f = get_zoompan_filter(p, width=720, height=1280, d_frames=50)
            assert isinstance(f, str)
            assert len(f) > 10
            if p == "static":
                assert "crop=" in f
            else:
                assert "zoompan=" in f

    def test_build_slideshow_with_scenes_data(self):
        ffmpeg_bin = get_ffmpeg_binary_path()
        if not ffmpeg_bin:
            pytest.skip("FFmpeg not available")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create 2 scene images
            s1_base = os.path.join(tmp_dir, "s1_base.png")
            s1_full = os.path.join(tmp_dir, "s1_full.png")
            s2_base = os.path.join(tmp_dir, "s2_base.png")
            audio_path = os.path.join(tmp_dir, "audio.wav")
            out_mp4 = os.path.join(tmp_dir, "out.mp4")

            Image.new("RGB", (720, 1280), (120, 30, 30)).save(s1_base)
            Image.new("RGB", (720, 1280), (120, 30, 30)).save(s1_full)
            Image.new("RGB", (720, 1280), (30, 120, 30)).save(s2_base)

            # Generate short silent audio with FFmpeg
            import subprocess
            subprocess.run(
                [ffmpeg_bin, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "3", audio_path],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            scenes_data = [
                {
                    "base_path": s1_base,
                    "full_path": s1_full,
                    "image_animation": "zoom_in",
                    "text_animation": "fade_in",
                },
                {
                    "base_path": s2_base,
                    "full_path": None,
                    "image_animation": "ken_burns",
                    "text_animation": "none",
                },
            ]

            success, err = build_slideshow_video(
                scenes_data=scenes_data,
                audio_path=audio_path,
                output_mp4_path=out_mp4,
                width=720,
                height=1280,
                audio_duration=3.0,
                ffmpeg_bin=ffmpeg_bin,
            )

            assert success is True, f"FFmpeg failed: {err}"
            assert os.path.exists(out_mp4)
            assert os.path.getsize(out_mp4) > 5000


class TestAITextSuggestions:
    """Tests for scene punchy keyword suggestions."""

    def test_mock_suggest_scene_texts(self):
        provider = MockTextProvider()
        en_texts = provider.suggest_scene_texts(topic="Green Tea", scene_number=1, total_scenes=5, language="english")
        assert len(en_texts) >= 2
        assert any("GREEN TEA" in t for t in en_texts)

        ta_texts = provider.suggest_scene_texts(topic="இயற்கை உணவு", scene_number=1, total_scenes=5, language="tamil")
        assert len(ta_texts) >= 2

        si_texts = provider.suggest_scene_texts(topic="තේ", scene_number=1, total_scenes=5, language="sinhala")
        assert len(si_texts) >= 2


class TestVideoTemplatesAPI:
    """Tests for Video Templates REST endpoints."""

    def test_list_templates_returns_presets(self, client, db):
        user = create_user("test_tpl_list@example.com")
        tenant = create_tenant("Template Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        resp = client.get("/api/v1/video/templates")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "templates" in data
        assert len(data["templates"]) >= len(SYSTEM_PRESET_TEMPLATES)
        names = [t["name"] for t in data["templates"]]
        assert "Bold Headlines" in names
        assert "Neon Glow" in names
        assert "Cinematic Gold" in names

    def test_create_and_delete_custom_template(self, client, db):
        user = create_user("test_tpl_crud@example.com")
        tenant = create_tenant("Template Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        # 1. Create custom template
        create_payload = {
            "name": "My Custom Reel Style",
            "description": "Custom yellow header with drop shadow",
            "config": {
                "font_family": "Montserrat",
                "font_size": 44,
                "color": "#FFE500",
                "stroke_color": "#000000",
                "stroke_width": 2,
                "shadow": {"enabled": True, "color": "rgba(0,0,0,0.8)", "blur": 8},
                "image_animation": "zoom_in",
                "text_animation": "fade_in",
            },
        }
        resp = client.post("/api/v1/video/templates", json=create_payload)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        tpl_id = data["template"]["id"]
        assert data["template"]["name"] == "My Custom Reel Style"

        # 2. Get single template
        get_resp = client.get(f"/api/v1/video/templates/{tpl_id}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["template"]["id"] == tpl_id

        # 3. Update template
        patch_resp = client.patch(
            f"/api/v1/video/templates/{tpl_id}",
            json={"name": "Updated Custom Style"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.get_json()["template"]["name"] == "Updated Custom Style"

        # 4. Delete custom template
        del_resp = client.delete(f"/api/v1/video/templates/{tpl_id}")
        assert del_resp.status_code == 200
        assert del_resp.get_json()["success"] is True

    def test_cannot_modify_or_delete_preset_template(self, client, db):
        user = create_user("test_tpl_lock@example.com")
        tenant = create_tenant("Template Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        # Try to modify system preset
        patch_resp = client.patch(
            "/api/v1/video/templates/preset-bold-headlines",
            json={"name": "Hacked Preset"},
        )
        assert patch_resp.status_code == 403

        # Try to delete system preset
        del_resp = client.delete(
            "/api/v1/video/templates/preset-bold-headlines",
        )
        assert del_resp.status_code == 403

    def test_suggest_texts_endpoint(self, client, db):
        user = create_user("test_suggest_text@example.com")
        tenant = create_tenant("Template Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        resp = client.post(
            "/api/v1/video/suggest-texts",
            json={"topic": "Benefits of Morning Routine", "scene_number": 1, "total_scenes": 5, "language": "english"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "suggestions" in data
        assert len(data["suggestions"]) >= 2
        assert data["scene_number"] == 1


class TestVideoRenderWithScenes:
    """Test /api/v1/video/render with enhanced scenes payload."""

    def test_render_with_scenes_payload(self, client, db, monkeypatch):
        user = create_user("test_render_scenes@example.com")
        tenant = create_tenant("Render Workspace", owner=user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = user.id
            sess["active_tenant_id"] = tenant.id

        ffmpeg_bin = get_ffmpeg_binary_path()
        if not ffmpeg_bin:
            pytest.skip("FFmpeg not available")

        # 1. Generate real test voiceover with MockTTS
        vo_resp = client.post("/api/v1/video/voiceover", json={
            "script": "Testing end to end scene rendering with text overlays and zoom animation.",
            "voice": "nova"
        })
        assert vo_resp.status_code == 200
        vo_data = vo_resp.get_json()

        # 2. Mock download_image_to_file to write a real small JPEG
        from app.services import video_service
        def fake_download(url, dest, timeout=12):
            Image.new("RGB", (720, 1280), (50, 100, 180)).save(dest, format="JPEG")
            return True

        monkeypatch.setattr(video_service, "download_image_to_file", fake_download)

        payload = {
            "topic": "5 Quick Health Tips",
            "audio_id": vo_data["audio_id"],
            "audio_url": vo_data["audio_url"],
            "aspect_ratio": "9:16",
            "scenes": [
                {
                    "image_url": "https://images.pexels.com/photos/111/test1.jpg",
                    "image_animation": "zoom_in",
                    "text_animation": "fade_in",
                    "texts": [
                        {
                            "content": "TIP #1: DRINK WATER",
                            "x_percent": 50,
                            "y_percent": 45,
                            "font_family": "Montserrat",
                            "font_size": 42,
                            "color": "#FFFFFF",
                            "stroke_color": "#000000",
                            "stroke_width": 2,
                            "shadow": {"enabled": True, "color": "rgba(0,0,0,0.7)", "blur": 6},
                        }
                    ],
                },
                {
                    "image_url": "https://images.pexels.com/photos/222/test2.jpg",
                    "image_animation": "ken_burns",
                    "text_animation": "none",
                    "texts": [],
                },
            ],
        }

        resp = client.post("/api/v1/video/render", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "asset_id" in data
        assert "video_url" in data
