"""Pillow-based text overlay rendering engine for video scenes.

Composites styled visual text, backgrounds, shadows, strokes, and positioning
onto scene images prior to FFmpeg video assembly.
"""
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Available font mapping
FONT_FILES = {
    "montserrat": "Montserrat-Bold.ttf",
    "open sans": "OpenSans-Regular.ttf",
    "roboto": "Roboto-Bold.ttf",
    "inter": "Inter-Regular.ttf",
    "playfair display": "PlayfairDisplay-Bold.ttf",
    "poppins": "Poppins-Bold.ttf",
    "impact": "Impact.ttf",
}

DEFAULT_FONT = "Montserrat-Bold.ttf"

SYSTEM_PRESET_TEMPLATES = [
    {
        "id": "preset-bold-headlines",
        "name": "Bold Headlines",
        "description": "Bold white text with dark outline and shadow, perfect for Reels and TikTok.",
        "is_preset": True,
        "config": {
            "font_family": "Montserrat",
            "font_size": 48,
            "font_weight": "bold",
            "color": "#FFFFFF",
            "stroke_color": "#000000",
            "stroke_width": 3,
            "shadow": {
                "enabled": True,
                "color": "rgba(0, 0, 0, 0.7)",
                "blur": 8,
                "offsetX": 3,
                "offsetY": 3,
            },
            "background": {
                "enabled": False,
                "color": "rgba(0, 0, 0, 0.4)",
                "padding": 12,
                "border_radius": 8,
            },
            "position": {
                "x_percent": 50,
                "y_percent": 40,
                "max_width_percent": 85,
                "text_align": "center",
            },
            "text_animation": "fade_in",
            "image_animation": "zoom_in",
        },
    },
    {
        "id": "preset-minimal-clean",
        "name": "Minimal Clean",
        "description": "Clean, elegant Inter typography with subtle shadow for corporate or aesthetic reels.",
        "is_preset": True,
        "config": {
            "font_family": "Inter",
            "font_size": 38,
            "font_weight": "normal",
            "color": "#FFFFFF",
            "stroke_color": "#000000",
            "stroke_width": 0,
            "shadow": {
                "enabled": True,
                "color": "rgba(0, 0, 0, 0.5)",
                "blur": 5,
                "offsetX": 2,
                "offsetY": 2,
            },
            "background": {
                "enabled": False,
                "color": "rgba(0, 0, 0, 0.3)",
                "padding": 10,
                "border_radius": 6,
            },
            "position": {
                "x_percent": 50,
                "y_percent": 50,
                "max_width_percent": 80,
                "text_align": "center",
            },
            "text_animation": "fade_in",
            "image_animation": "ken_burns",
        },
    },
    {
        "id": "preset-neon-glow",
        "name": "Neon Glow",
        "description": "Vibrant cyan neon styling with glowing blur for tech, gaming, or night scenes.",
        "is_preset": True,
        "config": {
            "font_family": "Poppins",
            "font_size": 44,
            "font_weight": "bold",
            "color": "#00F0FF",
            "stroke_color": "#003366",
            "stroke_width": 2,
            "shadow": {
                "enabled": True,
                "color": "rgba(0, 240, 255, 0.8)",
                "blur": 14,
                "offsetX": 0,
                "offsetY": 0,
            },
            "background": {
                "enabled": False,
                "color": "rgba(0, 0, 0, 0.5)",
                "padding": 12,
                "border_radius": 8,
            },
            "position": {
                "x_percent": 50,
                "y_percent": 45,
                "max_width_percent": 85,
                "text_align": "center",
            },
            "text_animation": "fade_in",
            "image_animation": "zoom_in",
        },
    },
    {
        "id": "preset-cinematic",
        "name": "Cinematic Gold",
        "description": "Luxury gold serif with dark semi-transparent backdrop for travel and premium topics.",
        "is_preset": True,
        "config": {
            "font_family": "Playfair Display",
            "font_size": 42,
            "font_weight": "bold",
            "color": "#FFD700",
            "stroke_color": "#000000",
            "stroke_width": 1,
            "shadow": {
                "enabled": True,
                "color": "rgba(0, 0, 0, 0.8)",
                "blur": 8,
                "offsetX": 2,
                "offsetY": 2,
            },
            "background": {
                "enabled": True,
                "color": "rgba(10, 10, 20, 0.65)",
                "padding": 16,
                "border_radius": 12,
            },
            "position": {
                "x_percent": 50,
                "y_percent": 50,
                "max_width_percent": 85,
                "text_align": "center",
            },
            "text_animation": "fade_in",
            "image_animation": "pan_left",
        },
    },
    {
        "id": "preset-lower-third",
        "name": "Lower Third Banner",
        "description": "Modern lower third caption bar for educational, explainer, and interview reels.",
        "is_preset": True,
        "config": {
            "font_family": "Open Sans",
            "font_size": 34,
            "font_weight": "bold",
            "color": "#FFFFFF",
            "stroke_color": "#000000",
            "stroke_width": 0,
            "shadow": {
                "enabled": False,
                "color": "rgba(0, 0, 0, 0.4)",
                "blur": 4,
                "offsetX": 1,
                "offsetY": 1,
            },
            "background": {
                "enabled": True,
                "color": "rgba(0, 0, 0, 0.75)",
                "padding": 18,
                "border_radius": 10,
            },
            "position": {
                "x_percent": 50,
                "y_percent": 80,
                "max_width_percent": 90,
                "text_align": "center",
            },
            "text_animation": "slide_up",
            "image_animation": "zoom_out",
        },
    },
    {
        "id": "preset-impact",
        "name": "Impact Headline",
        "description": "Maximum attention punchy yellow headline with thick dark outline.",
        "is_preset": True,
        "config": {
            "font_family": "Impact",
            "font_size": 52,
            "font_weight": "bold",
            "color": "#FFE600",
            "stroke_color": "#000000",
            "stroke_width": 4,
            "shadow": {
                "enabled": True,
                "color": "rgba(0, 0, 0, 0.9)",
                "blur": 10,
                "offsetX": 4,
                "offsetY": 4,
            },
            "background": {
                "enabled": False,
                "color": "rgba(0, 0, 0, 0.5)",
                "padding": 12,
                "border_radius": 6,
            },
            "position": {
                "x_percent": 50,
                "y_percent": 30,
                "max_width_percent": 90,
                "text_align": "center",
            },
            "text_animation": "fade_in",
            "image_animation": "zoom_in",
        },
    },
]


def get_fonts_directory() -> str:
    """Return absolute path to bundled fonts directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # from backend/app/services -> backend/app/static/fonts
    fonts_dir = os.path.abspath(os.path.join(current_dir, "..", "static", "fonts"))
    return fonts_dir


def parse_color(c: Any, default: Tuple[int, int, int, int] = (255, 255, 255, 255)) -> Tuple[int, int, int, int]:
    """Parse hex, rgb, rgba string or tuple into RGBA tuple."""
    if not c:
        return default
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        alpha = c[3] if len(c) >= 4 else 255
        return (int(c[0]), int(c[1]), int(c[2]), int(alpha))
    s = str(c).strip()
    if s.startswith("#"):
        hex_str = s.lstrip("#")
        if len(hex_str) == 3:
            hex_str = "".join([ch * 2 for ch in hex_str])
        if len(hex_str) == 6:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16), 255)
        elif len(hex_str) == 8:
            return (
                int(hex_str[0:2], 16),
                int(hex_str[2:4], 16),
                int(hex_str[4:6], 16),
                int(hex_str[6:8], 16),
            )
    m = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", s)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        alpha = int(round(a * 255)) if a <= 1.0 else int(a)
        return (r, g, b, max(0, min(255, alpha)))
    try:
        rgb = ImageColor.getrgb(s)
        return (rgb[0], rgb[1], rgb[2], 255)
    except Exception:
        return default


def load_font(family: str, size: int) -> ImageFont.FreeTypeFont:
    """Load TrueType font from bundled static/fonts directory with graceful fallback."""
    fonts_dir = get_fonts_directory()
    clean_family = (family or "").strip().lower()
    filename = FONT_FILES.get(clean_family, DEFAULT_FONT)
    font_path = os.path.join(fonts_dir, filename)

    if not os.path.isfile(font_path):
        # Fallback to default bundled font
        font_path = os.path.join(fonts_dir, DEFAULT_FONT)

    if os.path.isfile(font_path):
        try:
            return ImageFont.truetype(font_path, size=max(12, int(size)))
        except Exception as e:
            logger.warning(f"Error loading TTF {font_path}: {e}")

    # Ultimate fallback to PIL default
    try:
        return ImageFont.load_default()
    except Exception:
        return None  # type: ignore


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wrap text to ensure each line fits within max_width."""
    lines: List[str] = []
    paragraphs = text.split("\n")
    for para in paragraphs:
        words = para.split(" ")
        current_line: List[str] = []
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_w = bbox[2] - bbox[0]
            if line_w <= max_width or not current_line:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
    return lines


def cover_crop_image(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize and crop an image to fill target_w x target_h while maintaining aspect ratio."""
    src_w, src_h = img.size
    ratio = max(target_w / src_w, target_h / src_h)
    new_w = int(round(src_w * ratio))
    new_h = int(round(src_h * ratio))

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def render_text_overlay_layer(
    canvas_w: int,
    canvas_h: int,
    texts: List[Dict[str, Any]],
) -> Image.Image:
    """Render all text overlays onto a transparent RGBA layer."""
    overlay = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(overlay)

    for item in texts:
        content = (item.get("content") or "").strip()
        if not content:
            continue

        font_family = item.get("font_family", "Montserrat")
        # Relative scaling: baseline size calibrated for 720x1280
        base_size = int(item.get("font_size", 42))
        scaled_size = max(14, int(base_size * (canvas_w / 720.0)))

        font = load_font(font_family, scaled_size)
        color = parse_color(item.get("color", "#FFFFFF"))
        stroke_color = parse_color(item.get("stroke_color", "#000000"))
        stroke_width = int(item.get("stroke_width", 0))

        # Position percentages (0-100)
        x_pct = float(item.get("x_percent", 50))
        y_pct = float(item.get("y_percent", 50))
        max_w_pct = float(item.get("max_width_percent", 85))
        text_align = item.get("text_align", "center").lower()

        max_text_width = int((max_w_pct / 100.0) * canvas_w)
        lines = wrap_text(content, font, max_text_width, temp_draw)
        if not lines:
            continue

        # Measure lines
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = temp_draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            line_widths.append(lw)
            line_heights.append(lh)

        spacing = int(scaled_size * 0.25)
        total_text_h = sum(line_heights) + spacing * (len(lines) - 1)
        max_line_w = max(line_widths) if line_widths else 0

        # Anchor coordinates
        center_x = int((x_pct / 100.0) * canvas_w)
        center_y = int((y_pct / 100.0) * canvas_h)
        block_top = center_y - (total_text_h // 2)

        # 1. Background Box (if enabled)
        bg_config = item.get("background") or {}
        if bg_config.get("enabled"):
            raw_bg = bg_config.get("color")
            bg_color = parse_color(raw_bg, default=(0, 0, 0, 180)) if raw_bg else (0, 0, 0, 180)
            pad = int(bg_config.get("padding", 14) * (canvas_w / 720.0))
            radius = int(bg_config.get("border_radius", 8) * (canvas_w / 720.0))

            bg_left = center_x - (max_line_w // 2) - pad
            bg_top = block_top - pad
            bg_right = center_x + (max_line_w // 2) + pad
            bg_bottom = block_top + total_text_h + pad

            bg_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg_layer)
            bg_draw.rounded_rectangle(
                [bg_left, bg_top, bg_right, bg_bottom],
                radius=radius,
                fill=bg_color,
            )
            overlay = Image.alpha_composite(overlay, bg_layer)

        # 2. Drop Shadow (if enabled)
        shadow_config = item.get("shadow") or {}
        if shadow_config.get("enabled"):
            sh_color = parse_color(shadow_config.get("color", "rgba(0,0,0,0.7)"))
            sh_blur = int(shadow_config.get("blur", 6))
            sh_off_x = int(shadow_config.get("offsetX", 2))
            sh_off_y = int(shadow_config.get("offsetY", 2))

            sh_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            sh_draw = ImageDraw.Draw(sh_layer)

            curr_y = block_top
            for idx, line in enumerate(lines):
                lw = line_widths[idx]
                if text_align == "left":
                    line_x = center_x - (max_line_w // 2)
                elif text_align == "right":
                    line_x = center_x + (max_line_w // 2) - lw
                else:
                    line_x = center_x - (lw // 2)

                sh_draw.text(
                    (line_x + sh_off_x, curr_y + sh_off_y),
                    line,
                    font=font,
                    fill=sh_color,
                    stroke_width=stroke_width,
                    stroke_fill=sh_color,
                )
                curr_y += line_heights[idx] + spacing

            if sh_blur > 0:
                sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(radius=sh_blur / 2))
            overlay = Image.alpha_composite(overlay, sh_layer)

        # 3. Main Text Drawing
        txt_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_layer)
        curr_y = block_top
        for idx, line in enumerate(lines):
            lw = line_widths[idx]
            if text_align == "left":
                line_x = center_x - (max_line_w // 2)
            elif text_align == "right":
                line_x = center_x + (max_line_w // 2) - lw
            else:
                line_x = center_x - (lw // 2)

            txt_draw.text(
                (line_x, curr_y),
                line,
                font=font,
                fill=color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )
            curr_y += line_heights[idx] + spacing

        overlay = Image.alpha_composite(overlay, txt_layer)

    return overlay


def composite_scene(
    base_image_bytes: bytes,
    texts: Optional[List[Dict[str, Any]]] = None,
    canvas_w: int = 720,
    canvas_h: int = 1280,
) -> bytes:
    """Take raw base image bytes, crop/scale to target dimensions, overlay visual texts, and return PNG bytes."""
    with Image.open(io.BytesIO(base_image_bytes)) as base_img:
        # Normalize to RGB/RGBA
        base_img = base_img.convert("RGBA")
        base_cropped = cover_crop_image(base_img, canvas_w, canvas_h)

        if texts and len(texts) > 0:
            overlay = render_text_overlay_layer(canvas_w, canvas_h, texts)
            final_img = Image.alpha_composite(base_cropped, overlay).convert("RGB")
        else:
            final_img = base_cropped.convert("RGB")

        out_buf = io.BytesIO()
        final_img.save(out_buf, format="PNG", optimize=True)
        return out_buf.getvalue()
