"""Image generation provider."""
import io
import logging
from PIL import Image, ImageDraw, ImageFont

from .base import BaseImageProvider, ImageGenResult

logger = logging.getLogger(__name__)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a crisp TrueType font across Windows and Linux, falling back cleanly."""
    candidates = [
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


class MockImageProvider(BaseImageProvider):
    """Generates high quality branded social media banner images locally using Pillow."""

    def generate_image(self, prompt: str, style: str = "modern") -> ImageGenResult:
        # Create a 1080x1080 image (Instagram standard square)
        width, height = 1080, 1080
        
        # Color palettes based on style
        styles = {
            "modern": ((15, 23, 42), (59, 130, 246)),      # Slate to Electric Blue
            "vibrant": ((79, 70, 229), (236, 72, 153)),    # Indigo to Pink
            "minimal": ((24, 24, 27), (63, 63, 70)),       # Zinc Dark
            "nature": ((6, 78, 59), (16, 185, 129)),       # Deep Forest to Emerald
        }
        color_start, color_end = styles.get(style.lower(), styles["modern"])

        # Create gradient image
        base = Image.new("RGB", (width, height), color=color_start)
        draw = ImageDraw.Draw(base)

        # Draw vertical subtle gradient
        for y in range(height):
            ratio = y / height
            r = int(color_start[0] * (1 - ratio) + color_end[0] * ratio)
            g = int(color_start[1] * (1 - ratio) + color_end[1] * ratio)
            b = int(color_start[2] * (1 - ratio) + color_end[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add decorative modern card container
        card_margin = 80
        draw.rounded_rectangle(
            [card_margin, card_margin, width - card_margin, height - card_margin],
            radius=32,
            outline=(255, 255, 255, 60),
            width=2,
        )

        # Draw badge/pill at top of card
        badge_y = card_margin + 60
        draw.rounded_rectangle(
            [card_margin + 60, badge_y, card_margin + 280, badge_y + 44],
            radius=22,
            fill=(255, 255, 255, 40),
        )

        # Draw text using system TrueType font or sized Pillow default font
        font_title = _load_font(46)
        font_meta = _load_font(26)

        draw.text((card_margin + 80, badge_y + 10), "AI SOCIAL STUDIO", fill=(255, 255, 255), font=font_meta)

        # Wrap headline text cleanly
        words = prompt.split()
        lines = []
        cur_line = []
        for word in words:
            cur_line.append(word)
            if len(" ".join(cur_line)) > 30:
                lines.append(" ".join(cur_line))
                cur_line = []
        if cur_line:
            lines.append(" ".join(cur_line))

        # Take first 4 lines max
        headline = "\n".join(lines[:4])
        text_y = height // 2 - 80
        draw.multiline_text(
            (card_margin + 80, text_y),
            headline,
            fill=(255, 255, 255),
            font=font_title,
            spacing=16,
        )

        # Brand watermark footer
        draw.text(
            (card_margin + 80, height - card_margin - 80),
            "Generated with AI Social Publisher • Verified Authentic",
            fill=(203, 213, 225),
            font=font_meta,
        )

        buffer = io.BytesIO()
        base.save(buffer, format="PNG", quality=95)
        image_bytes = buffer.getvalue()

        return ImageGenResult(
            image_bytes=image_bytes,
            mime_type="image/png",
            prompt_used=prompt,
            cost_usd=0.04,
        )


class DallEImageProvider(BaseImageProvider):
    """OpenAI DALL-E image generation integration."""

    def __init__(self, api_key: str, model: str = "dall-e-3"):
        self.api_key = api_key
        self.model = model

    def generate_image(self, prompt: str, style: str = "modern") -> ImageGenResult:
        try:
            import openai
            import requests

            client = openai.OpenAI(api_key=self.api_key)
            enhanced_prompt = f"Professional social media banner image about {prompt}, {style} style, clean composition, 4k resolution."
            resp = client.images.generate(
                model=self.model,
                prompt=enhanced_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = resp.data[0].url
            download_resp = requests.get(image_url, timeout=30)
            download_resp.raise_for_status()

            return ImageGenResult(
                image_bytes=download_resp.content,
                mime_type="image/png",
                prompt_used=prompt,
                cost_usd=0.04,
            )
        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}. Falling back to local generation.")
            fallback = MockImageProvider()
            return fallback.generate_image(prompt, style)


def _clean_pexels_query(prompt: str) -> str:
    """Turn a post topic or prompt into clean Pexels stock-search keywords."""
    import re
    cleaned = re.sub(r"https?://\S+", "", prompt or "")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    words = [w for w in cleaned.split() if len(w) > 1]
    return " ".join(words[:5]) or "modern business"


def search_pexels_photos(query: str, api_key: str, per_page: int = 8) -> list[dict]:
    """Search Pexels for free stock photos matching a query."""
    import requests

    if not api_key:
        return []

    search_term = _clean_pexels_query(query)
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key.strip()},
            params={"query": search_term, "per_page": per_page},
            timeout=12,
        )
        if resp.status_code != 200:
            logger.warning(f"Pexels search returned HTTP {resp.status_code}: {resp.text[:200]}")
            return []

        photos = resp.json().get("photos", [])
        results = []
        for p in photos:
            src = p.get("src", {})
            results.append({
                "id": p.get("id"),
                "alt": p.get("alt") or search_term,
                "photographer": p.get("photographer") or "Pexels",
                "thumb": src.get("medium") or src.get("small"),
                "full": src.get("large") or src.get("large2x") or src.get("original"),
            })
        return [r for r in results if r["thumb"] and r["full"]]
    except Exception as exc:
        logger.warning(f"Pexels search error: {exc}")
        return []


class PexelsImageProvider(BaseImageProvider):
    """Fetches free topic-matched stock photography from the Pexels API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_image(self, prompt: str, style: str = "modern") -> ImageGenResult:
        import os
        import requests

        query = _clean_pexels_query(prompt)
        photos = search_pexels_photos(query, self.api_key, per_page=5)
        if photos:
            chosen = photos[0]
            try:
                img_resp = requests.get(chosen["full"], timeout=20)
                img_resp.raise_for_status()
                content_type = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                if not content_type.startswith("image/"):
                    content_type = "image/jpeg"
                return ImageGenResult(
                    image_bytes=img_resp.content,
                    mime_type=content_type,
                    prompt_used=query,
                    cost_usd=0.0,
                )
            except Exception as exc:
                logger.warning(f"Failed downloading Pexels photo: {exc}")

        # Fallback to DALL-E if OpenAI key exists, otherwise local Pillow banner
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            return DallEImageProvider(api_key=openai_key).generate_image(prompt, style)
        return MockImageProvider().generate_image(prompt, style)


