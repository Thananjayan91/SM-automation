"""Video generation service — builds 15-30s slideshow videos with FFmpeg, voiceover audio, and Pexels imagery."""
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import current_app

from ..models.media_asset import MediaAsset
from .media_service import save_video_file, read_voiceover_audio
from .security_service import validate_url_safe
from .video_text_renderer import composite_scene

logger = logging.getLogger(__name__)

ASPECT_RATIOS = {
    "9:16": {"width": 720, "height": 1280, "label": "Vertical (Reels / TikTok / Shorts)"},
    "1:1": {"width": 720, "height": 720, "label": "Square (Feed)"},
    "16:9": {"width": 1280, "height": 720, "label": "Landscape (YouTube / Video)"},
}


def get_ffmpeg_binary_path() -> Optional[str]:
    """Locate available FFmpeg binary from imageio_ffmpeg, system PATH, or environment variable."""
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path

    # Check imageio_ffmpeg first
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception as e:
        logger.debug(f"imageio_ffmpeg lookup error: {e}")

    # Fallback to system PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    # Common Linux /tmp fallback for serverless
    if os.path.exists("/tmp/ffmpeg") and os.access("/tmp/ffmpeg", os.X_OK):
        return "/tmp/ffmpeg"

    return None


def probe_audio_duration(ffmpeg_bin: str, audio_path: str) -> float:
    """Probe audio duration in seconds using FFmpeg."""
    try:
        cmd = [
            ffmpeg_bin,
            "-i", audio_path,
            "-f", "null",
            "-"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        # Parse time from stderr like: "time=00:00:14.85"
        for line in proc.stderr.splitlines():
            if "time=" in line:
                idx = line.find("time=")
                time_str = line[idx + 5:].split()[0]
                parts = time_str.split(":")
                if len(parts) == 3:
                    h = float(parts[0])
                    m = float(parts[1])
                    s = float(parts[2])
                    return h * 3600 + m * 60 + s
    except Exception as e:
        logger.warning(f"Could not probe exact audio duration with ffmpeg: {e}")

    # Fallback: estimate from file size if needed, or default to 15s
    return 15.0


def download_image_to_file(image_url: str, dest_path: str, timeout: int = 12) -> bool:
    """Safely download an image URL to a local destination file."""
    is_safe, err = validate_url_safe(image_url)
    if not is_safe:
        logger.warning(f"Rejected unsafe image URL ({image_url}): {err}")
        return False

    try:
        headers = {"User-Agent": "AISocialPublisher/1.0 (VideoGenerator)"}
        resp = requests.get(image_url, headers=headers, stream=True, timeout=timeout)
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
            return os.path.getsize(dest_path) > 1000
        logger.warning(f"Image download failed HTTP {resp.status_code} for {image_url}")
        return False
    except Exception as e:
        logger.error(f"Error downloading image ({image_url}): {e}")
        return False


def get_zoompan_filter(anim: str, width: int, height: int, d_frames: int, fps: int = 25) -> str:
    """Generate FFmpeg zoompan filter string for image animation presets."""
    anim = (anim or "static").lower().strip()
    # Optimized pre-scale: 1.15x is sufficient for 1.15x zoom and renders 4x faster than 2x
    w2 = int(width * 1.15)
    w2 += w2 % 2
    h2 = int(height * 1.15)
    h2 += h2 % 2

    if anim == "zoom_in":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif anim == "zoom_out":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='if(eq(on,1),1.15,max(zoom-0.0015,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif anim == "pan_left":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='1.12':x='(iw-iw/zoom)*(1-on/{d_frames})':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif anim == "pan_right":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='1.12':x='(iw-iw/zoom)*(on/{d_frames})':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif anim == "pan_up":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='1.12':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{d_frames})':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif anim == "pan_down":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='1.12':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{d_frames})':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif anim == "ken_burns":
        return (
            f"scale={w2}:{h2},"
            f"zoompan=z='min(zoom+0.0012,1.14)':x='(iw-iw/zoom)*(on/{d_frames})':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    else:  # static
        return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"


def build_slideshow_video(
    image_paths: Optional[List[str]] = None,
    audio_path: str = "",
    output_mp4_path: str = "",
    width: int = 720,
    height: int = 1280,
    audio_duration: float = 15.0,
    ffmpeg_bin: Optional[str] = None,
    scenes_data: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, Optional[str]]:
    """Build an MP4 slideshow video from images and audio track using FFmpeg.

    Supports scenes_data with image_animation ('zoom_in', 'pan_left', 'ken_burns', etc.)
    and text_animation ('fade_in', 'none'). Also backwards-compatible with simple image_paths.

    Returns (success, error_message).
    """
    bin_path = ffmpeg_bin or get_ffmpeg_binary_path()
    if not bin_path:
        return False, "FFmpeg binary is not available on this server."

    # Normalize scenes data
    if scenes_data is None:
        scenes_data = [
            {"base_path": p, "full_path": None, "image_animation": "static", "text_animation": "none"}
            for p in (image_paths or [])
        ]

    num_scenes = len(scenes_data)
    if num_scenes == 0:
        return False, "No images or scenes provided for slideshow."

    dur = max(4.0, float(audio_duration))
    per_img_duration = max(1.5, dur / num_scenes)
    fps = 25
    d_frames = max(10, int(round(fps * per_img_duration)))

    # Build FFmpeg command inputs and filter graph
    cmd = [bin_path, "-y"]
    filter_parts = []
    concat_inputs = []
    input_idx = 0

    for i, scene in enumerate(scenes_data):
        img_anim = scene.get("image_animation", "static")
        text_anim = scene.get("text_animation", "none")
        base_path = scene.get("base_path")
        full_path = scene.get("full_path")

        zp_filter = get_zoompan_filter(img_anim, width, height, d_frames, fps=fps)

        if text_anim == "fade_in" and full_path and base_path:
            # Two inputs: base (background) and full (foreground with text fading in)
            in_base = input_idx
            cmd.extend(["-loop", "1", "-t", f"{per_img_duration:.2f}", "-i", base_path])
            input_idx += 1

            in_full = input_idx
            cmd.extend(["-loop", "1", "-t", f"{per_img_duration:.2f}", "-i", full_path])
            input_idx += 1

            fade_st = min(0.3, per_img_duration * 0.15)
            fade_dur = min(0.45, per_img_duration * 0.3)

            filter_parts.append(f"[{in_base}:v]{zp_filter},format=yuv420p,setsar=1[bg{i}]")
            filter_parts.append(
                f"[{in_full}:v]{zp_filter},fade=t=in:st={fade_st:.2f}:d={fade_dur:.2f}:alpha=1,format=yuv420p,setsar=1[fg{i}]"
            )
            filter_parts.append(f"[bg{i}][fg{i}]overlay=0:0:format=auto,format=yuv420p,setsar=1[v{i}]")
        else:
            # Single input: use full_path if available (text burned in), otherwise base_path
            chosen_path = full_path if full_path else base_path
            in_img = input_idx
            cmd.extend(["-loop", "1", "-t", f"{per_img_duration:.2f}", "-i", chosen_path])
            input_idx += 1

            filter_parts.append(f"[{in_img}:v]{zp_filter},format=yuv420p,setsar=1[v{i}]")

        concat_inputs.append(f"[v{i}]")

    # Add audio input
    audio_in_idx = input_idx
    cmd.extend(["-i", audio_path])

    # Concat video streams
    concat_filter = f"{''.join(concat_inputs)}concat=n={num_scenes}:v=1:a=0[vconcat]"
    filter_parts.append(concat_filter)

    full_filter = ";".join(filter_parts)

    cmd.extend([
        "-filter_complex", full_filter,
        "-map", "[vconcat]",
        "-map", f"{audio_in_idx}:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "26",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_mp4_path,
    ])

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=50,  # Strict timeout to stay well under Vercel's 60s limit
        )
        if proc.returncode != 0:
            logger.error(f"FFmpeg render error: {proc.stderr[-600:]}")
            return False, f"FFmpeg failed: {proc.stderr[-300:]}"
        return True, None
    except subprocess.TimeoutExpired:
        return False, "Video rendering timed out. Please try with fewer images or shorter duration."
    except Exception as e:
        logger.error(f"Unexpected error running FFmpeg: {e}")
        return False, f"Failed to execute FFmpeg: {str(e)}"


def generate_video_from_assets(
    tenant_id: str,
    user_id: Optional[str],
    image_urls: Optional[List[str]] = None,
    scenes: Optional[List[Dict[str, Any]]] = None,
    audio_bytes: Optional[bytes] = None,
    audio_id_with_ext: Optional[str] = None,
    audio_url: Optional[str] = None,
    aspect_ratio: str = "9:16",
    topic: Optional[str] = None,
) -> Tuple[Optional[MediaAsset], Optional[str]]:
    """Download images, composite overlays, invoke FFmpeg, upload MP4 to Vercel Blob, and return MediaAsset."""
    # Normalize scenes vs image_urls
    if not scenes:
        if not image_urls or len(image_urls) < 1:
            return None, "Please select at least 1 image to generate a video."
        scenes = [
            {"image_url": url, "image_animation": "zoom_in", "texts": [], "text_animation": "none"}
            for url in image_urls
        ]

    if len(scenes) < 1:
        return None, "Please provide at least 1 scene."

    ffmpeg_bin = get_ffmpeg_binary_path()
    if not ffmpeg_bin:
        return None, "FFmpeg is not installed or available on this system."

    # Resolve audio bytes
    if not audio_bytes:
        if audio_id_with_ext or audio_url:
            audio_bytes = read_voiceover_audio(tenant_id, audio_id_with_ext or "", audio_url)
    if not audio_bytes or len(audio_bytes) < 100:
        return None, "Voiceover audio is missing or empty. Please generate voiceover first."

    # Aspect ratio lookup
    ar_config = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["9:16"])
    target_w = ar_config["width"]
    target_h = ar_config["height"]

    work_id = str(uuid.uuid4())
    temp_dir = os.path.join(tempfile.gettempdir(), f"sm_video_{work_id}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # 1. Write audio file (auto-detect WAV vs MP3 extension)
        audio_ext = "wav" if audio_bytes[:4] == b"RIFF" else "mp3"
        audio_path = os.path.join(temp_dir, f"voiceover.{audio_ext}")
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        # 2. Probe audio duration
        duration = probe_audio_duration(ffmpeg_bin, audio_path)
        if duration <= 1.0:
            duration = max(5.0, len(scenes) * 3.0)

        # 3. Download images and prepare scenes
        prepared_scenes: List[Dict[str, Any]] = []
        for idx, sc in enumerate(scenes[:8]):  # Max 8 scenes for safety
            url = sc.get("image_url")
            if not url:
                continue

            local_raw = os.path.join(temp_dir, f"raw_{idx:03d}.jpg")
            if not download_image_to_file(url, local_raw):
                continue

            with open(local_raw, "rb") as rf:
                raw_bytes = rf.read()

            texts = sc.get("texts") or []
            img_anim = sc.get("image_animation", "zoom_in")
            text_anim = sc.get("text_animation", "fade_in" if texts else "none")

            # Composite base image (cover cropped to aspect ratio)
            base_png_path = os.path.join(temp_dir, f"scene_{idx:03d}_base.png")
            base_bytes = composite_scene(raw_bytes, texts=None, canvas_w=target_w, canvas_h=target_h)
            with open(base_png_path, "wb") as bf:
                bf.write(base_bytes)

            full_png_path = None
            if texts:
                full_png_path = os.path.join(temp_dir, f"scene_{idx:03d}_full.png")
                full_bytes = composite_scene(raw_bytes, texts=texts, canvas_w=target_w, canvas_h=target_h)
                with open(full_png_path, "wb") as ff:
                    ff.write(full_bytes)

            prepared_scenes.append({
                "base_path": base_png_path,
                "full_path": full_png_path,
                "image_animation": img_anim,
                "text_animation": text_anim,
            })

        if len(prepared_scenes) == 0:
            return None, "Could not download any of the selected images. Please check the URLs."

        # 4. Render MP4
        output_mp4 = os.path.join(temp_dir, "output.mp4")
        success, render_err = build_slideshow_video(
            scenes_data=prepared_scenes,
            audio_path=audio_path,
            output_mp4_path=output_mp4,
            width=target_w,
            height=target_h,
            audio_duration=duration,
            ffmpeg_bin=ffmpeg_bin,
        )

        if not success or not os.path.exists(output_mp4):
            return None, render_err or "Failed to produce MP4 video output."

        # 5. Read generated MP4 bytes
        with open(output_mp4, "rb") as f:
            mp4_bytes = f.read()

        if len(mp4_bytes) < 1000:
            return None, "Rendered video file is corrupted or empty."

        # 6. Save to Vercel Blob via media_service
        video_filename = f"video_{topic[:30] if topic else 'reel'}_{work_id[:8]}.mp4"
        asset, save_err = save_video_file(
            video_bytes=mp4_bytes,
            tenant_id=tenant_id,
            user_id=user_id,
            filename=video_filename,
            width=target_w,
            height=target_h,
            notes=f"Generated video for topic: {topic or 'N/A'}",
            labels=["video", "ai-generated", f"aspect-{aspect_ratio}"],
        )

        if save_err or not asset:
            return None, save_err or "Could not store video in storage."

        return asset, None

    finally:
        # Cleanup temporary files
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
