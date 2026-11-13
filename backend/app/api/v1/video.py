"""REST API — Video generation endpoints (Narration, TTS Voiceover, FFmpeg Render)."""
import logging
from flask import request, jsonify, session
from flask_login import login_required, current_user

from . import api_v1_bp
from ...services import permission_service, video_service, media_service
from ...services.ai import get_text_provider, get_tts_provider, SUPPORTED_VOICES
from ...extensions import limiter

logger = logging.getLogger(__name__)


def _get_active_tenant_id() -> tuple[str | None, str | None]:
    """Retrieve active tenant ID from session or X-Tenant-ID header, verifying membership."""
    tenant_id = session.get("active_tenant_id") or request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, "No active workspace selected. Set active workspace or pass X-Tenant-ID header."

    membership = permission_service.get_membership(current_user.id, tenant_id)
    if not membership:
        return None, "Access denied to the specified workspace."
    return tenant_id, None


@api_v1_bp.route("/video/voices", methods=["GET"])
@login_required
def api_list_voices():
    """List available TTS voice options."""
    return jsonify({
        "voices": [
            {"id": "nova", "name": "Nova", "gender": "Female", "description": "Warm, engaging, natural (Recommended)"},
            {"id": "alloy", "name": "Alloy", "gender": "Neutral", "description": "Balanced, versatile, clear"},
            {"id": "echo", "name": "Echo", "gender": "Male", "description": "Smooth, authoritative, confident"},
            {"id": "fable", "name": "Fable", "gender": "Expressive", "description": "Dynamic, British accent, storytelling"},
            {"id": "onyx", "name": "Onyx", "gender": "Male", "description": "Deep, calm, professional"},
            {"id": "shimmer", "name": "Shimmer", "gender": "Female", "description": "Bright, upbeat, energetic"},
        ],
        "default": "nova",
    })


@api_v1_bp.route("/video/narration", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def api_generate_narration():
    """Generate concise voiceover narration text for a topic."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "validation_error", "message": "Topic is required."}), 400

    language = (data.get("language") or "english").strip().lower()
    duration_hint = int(data.get("duration", 15))

    text_provider = get_text_provider()
    narration = text_provider.generate_narration(
        topic=topic,
        language=language,
        duration_hint=duration_hint,
    )

    return jsonify({
        "script": narration.script,
        "word_count": narration.word_count,
        "estimated_duration_secs": narration.estimated_duration_secs,
        "language": language,
    })


@api_v1_bp.route("/video/voiceover", methods=["POST"])
@login_required
@limiter.limit("15 per minute")
def api_generate_voiceover():
    """Synthesize voiceover narration text into audio using OpenAI TTS."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    data = request.get_json(silent=True) or {}
    script = (data.get("script") or "").strip()
    if not script:
        return jsonify({"error": "validation_error", "message": "Narration script text is required."}), 400

    voice = (data.get("voice") or "nova").strip().lower()
    tts_provider = get_tts_provider()
    tts_res = tts_provider.generate_speech(text=script, voice=voice)

    # Store audio in Vercel Blob or local disk
    audio_url, audio_id, save_err = media_service.save_voiceover_audio(
        audio_bytes=tts_res.audio_bytes,
        tenant_id=tenant_id,
        mime_type=tts_res.mime_type,
    )
    if save_err or not audio_url:
        return jsonify({"error": "storage_failed", "message": save_err or "Failed to store audio."}), 500

    return jsonify({
        "audio_url": audio_url,
        "audio_id": audio_id,
        "voice": tts_res.voice_used,
        "duration_secs": tts_res.duration_secs,
        "mime_type": tts_res.mime_type,
    })


@api_v1_bp.route("/video/suggest-texts", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_suggest_scene_texts():
    """Generate 2-3 punchy visual text overlay phrases for a video scene."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "validation_error", "message": "Topic is required."}), 400

    scene_number = int(data.get("scene_number", 1))
    total_scenes = int(data.get("total_scenes", 5))
    language = (data.get("language") or "english").strip().lower()

    text_provider = get_text_provider()
    suggestions = text_provider.suggest_scene_texts(
        topic=topic,
        scene_number=scene_number,
        total_scenes=total_scenes,
        language=language,
    )

    return jsonify({
        "suggestions": suggestions,
        "scene_number": scene_number,
        "total_scenes": total_scenes,
    })


@api_v1_bp.route("/video/render", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def api_render_video():
    """Render slideshow MP4 video from selected images or scene configurations and audio track."""
    tenant_id, err = _get_active_tenant_id()
    if err:
        return jsonify({"error": "workspace_required", "message": err}), 403

    if not permission_service.has_permission(current_user.id, tenant_id, "content.create"):
        return jsonify({"error": "forbidden", "message": "Permission denied"}), 403

    data = request.get_json(silent=True) or {}
    scenes = data.get("scenes") or []
    image_urls = data.get("image_urls") or []

    if not scenes and not image_urls:
        return jsonify({"error": "validation_error", "message": "Please provide either scenes or image_urls."}), 400

    audio_id = data.get("audio_id")
    audio_url = data.get("audio_url")
    aspect_ratio = data.get("aspect_ratio", "9:16")
    topic = data.get("topic")

    asset, render_err = video_service.generate_video_from_assets(
        tenant_id=tenant_id,
        user_id=current_user.id,
        image_urls=image_urls if not scenes else None,
        scenes=scenes if scenes else None,
        audio_id_with_ext=audio_id,
        audio_url=audio_url,
        aspect_ratio=aspect_ratio,
        topic=topic,
    )

    if render_err or not asset:
        return jsonify({"error": "render_failed", "message": render_err or "Video generation failed."}), 500

    return jsonify({
        "success": True,
        "asset_id": asset.id,
        "video_url": asset.storage_url,
        "filename": asset.original_filename,
        "width": asset.width,
        "height": asset.height,
        "aspect_ratio": aspect_ratio,
        "size_bytes": asset.size_bytes,
    })
