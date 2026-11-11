"""Text and caption generation provider."""
import logging
from typing import List, Optional

from .base import BaseTextProvider, CaptionResult

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"english", "tamil", "sinhala"}


def _normalize_language(language: Optional[str]) -> str:
    lang = (language or "english").strip().lower()
    return lang if lang in SUPPORTED_LANGUAGES else "english"


class MockTextProvider(BaseTextProvider):
    """Generates engaging, context-aware social captions deterministically."""

    def generate_caption(
        self,
        topic: str,
        research_summary: Optional[str] = None,
        tone: str = "professional",
        target_platforms: Optional[List[str]] = None,
        language: str = "english",
    ) -> CaptionResult:
        tone_lower = (tone or "professional").lower()
        lang = _normalize_language(language)
        clean_tag = "".join(c for c in topic if c.isalnum())

        if lang == "tamil":
            opener = f"✨ {topic} — முக்கிய தகவல்கள்:"
            body = research_summary or (
                f"{topic} பற்றிய புதிய வாய்ப்புகள் மற்றும் பயனுள்ள தகவல்களை இன்று அறிந்து கொள்ளுங்கள்."
            )
            cta = "உங்கள் கருத்துக்களை கீழே பகிருங்கள்! 👇"
            caption = f"{opener}\n\n{body}\n\n{cta}"
            hashtags = [
                f"#{clean_tag}" if clean_tag else "#TamilUpdates",
                "#தமிழ்",
                "#புதியதகவல்",
                "#Trending",
            ]
            return CaptionResult(caption=caption.strip(), hashtags=hashtags, tokens_used=240, cost_usd=0.0048)

        if lang == "sinhala":
            opener = f"✨ {topic} — නවතම තොරතුරු:"
            body = research_summary or (
                f"{topic} පිළිබඳ වැදගත් තොරතුරු සහ නව ප්‍රවණතා අදම දැනගන්න."
            )
            cta = "ඔබේ අදහස් පහතින් සඳහන් කරන්න! 👇"
            caption = f"{opener}\n\n{body}\n\n{cta}"
            hashtags = [
                f"#{clean_tag}" if clean_tag else "#SinhalaUpdates",
                "#සිංහල",
                "#SriLanka",
                "#Trending",
            ]
            return CaptionResult(caption=caption.strip(), hashtags=hashtags, tokens_used=240, cost_usd=0.0048)

        # English default with tone-specific opening styles
        openings = {
            "professional": f"Strategic perspective on {topic}:",
            "playful": f"Big things happening with {topic}! ✨",
            "educational": f"Here is what you need to know about {topic}:",
            "bold": f"Why everyone is talking about {topic} today:",
            "urgent": f"Breaking update on {topic}:",
        }
        opener = openings.get(tone_lower, f"Exploring {topic}:")

        if research_summary:
            context_body = f"\n\n{research_summary}\n"
        else:
            context_body = (
                f"\n\nWhether you're scaling operations or exploring fresh opportunities, "
                f"staying ahead of the curve in {topic} unlocks measurable competitive advantage.\n"
            )

        call_to_action = "\nWhat's your take on this? Share your thoughts below! 👇"
        caption = f"{opener}{context_body}{call_to_action}"

        hashtags = [
            f"#{clean_tag}" if clean_tag else "#SocialStrategy",
            "#MarketingTrends",
            "#Innovation",
            "#GrowthMindset",
            "#ContentCreation",
        ]

        return CaptionResult(
            caption=caption.strip(),
            hashtags=hashtags,
            tokens_used=240,
            cost_usd=0.0048,
        )


class OpenAITextProvider(BaseTextProvider):
    """OpenAI API integration for caption and copy generation."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def generate_caption(
        self,
        topic: str,
        research_summary: Optional[str] = None,
        tone: str = "professional",
        target_platforms: Optional[List[str]] = None,
        language: str = "english",
    ) -> CaptionResult:
        lang = _normalize_language(language)
        lang_instructions = {
            "tamil": "Write the ENTIRE social media post naturally in Tamil script (தமிழ்). Do not mix long English paragraphs—keep the copy natural, fluent Tamil, plus 4-5 relevant hashtags.",
            "sinhala": "Write the ENTIRE social media post naturally in Sinhala script (සිංහල). Do not mix long English paragraphs—keep the copy natural, fluent Sinhala, plus 4-5 relevant hashtags.",
            "english": "Write the social media post in clear, engaging English with 4-5 relevant hashtags.",
        }

        try:
            import openai  # Optional dependency
            client = openai.OpenAI(api_key=self.api_key)
            prompt = (
                f"Write an engaging social media post about: {topic}.\n"
                f"Language requirement: {lang_instructions[lang]}\n"
                f"Tone: {tone}.\n"
                f"Research Context: {research_summary or 'None'}\n"
                f"Platforms: {', '.join(target_platforms) if target_platforms else 'Facebook & Instagram'}\n"
                f"Include an engaging hook, concise body, clear call-to-action, and put 4-5 hashtags on the final line."
            )
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            raw_text = resp.choices[0].message.content or ""
            tokens = resp.usage.total_tokens if resp.usage else 300

            # Extract hashtags while preserving paragraph line breaks
            tags = []
            kept_lines = []
            for line in raw_text.splitlines():
                line_words = line.split()
                line_tags = [w for w in line_words if w.startswith("#")]
                tags.extend(line_tags)
                non_tag_words = [w for w in line_words if not w.startswith("#")]
                if non_tag_words:
                    kept_lines.append(" ".join(non_tag_words))
                elif not line.strip():
                    kept_lines.append("")

            clean_caption = "\n".join(kept_lines).strip()

            return CaptionResult(
                caption=clean_caption or raw_text.strip(),
                hashtags=tags[:8] if tags else ["#Trends", "#Innovation"],
                tokens_used=tokens,
                cost_usd=0.005,
            )
        except Exception as e:
            logger.error(f"OpenAI text generation failed: {e}. Falling back to deterministic provider.")
            fallback = MockTextProvider()
            return fallback.generate_caption(topic, research_summary, tone, target_platforms, language=lang)


