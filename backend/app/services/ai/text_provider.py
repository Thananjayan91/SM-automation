"""Text and caption generation provider."""
import logging
from typing import List, Optional

from .base import BaseTextProvider, CaptionResult

logger = logging.getLogger(__name__)


class MockTextProvider(BaseTextProvider):
    """Generates engaging, context-aware social captions deterministically."""

    def generate_caption(
        self,
        topic: str,
        research_summary: Optional[str] = None,
        tone: str = "professional",
        target_platforms: Optional[List[str]] = None,
    ) -> CaptionResult:
        tone_lower = (tone or "professional").lower()

        # Tone-specific opening styles
        openings = {
            "professional": f"Strategic perspective on {topic}:",
            "playful": f"Big things happening with {topic}! ✨",
            "educational": f"Here is what you need to know about {topic}:",
            "bold": f"Why everyone is talking about {topic} today:",
            "urgent": f"Breaking update on {topic}:",
        }
        opener = openings.get(tone_lower, f"Exploring {topic}:")

        context_body = ""
        if research_summary:
            context_body = f"\n\n{research_summary}\n"
        else:
            context_body = (
                f"\n\nWhether you're scaling operations or exploring fresh opportunities, "
                f"staying ahead of the curve in {topic} unlocks measurable competitive advantage.\n"
            )

        call_to_action = "\nWhat's your take on this? Share your thoughts below! 👇"

        caption = f"{opener}{context_body}{call_to_action}"

        # Clean hashtags
        clean_tag = "".join(c for c in topic if c.isalnum())
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
    ) -> CaptionResult:
        try:
            import openai  # Optional dependency
            client = openai.OpenAI(api_key=self.api_key)
            prompt = (
                f"Write an engaging social media post about: {topic}.\n"
                f"Tone: {tone}.\n"
                f"Research Context: {research_summary or 'None'}\n"
                f"Platforms: {', '.join(target_platforms) if target_platforms else 'General'}\n"
                f"Provide the post text and 4-5 relevant hashtags."
            )
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            raw_text = resp.choices[0].message.content or ""
            tokens = resp.usage.total_tokens if resp.usage else 300
            
            # Simple hashtag extraction
            words = raw_text.split()
            tags = [w for w in words if w.startswith("#")]
            clean_caption = " ".join(w for w in words if not w.startswith("#")).strip()

            return CaptionResult(
                caption=clean_caption,
                hashtags=tags[:8] if tags else ["#Trends", "#Innovation"],
                tokens_used=tokens,
                cost_usd=0.005,
            )
        except Exception as e:
            logger.error(f"OpenAI text generation failed: {e}. Falling back to deterministic provider.")
            fallback = MockTextProvider()
            return fallback.generate_caption(topic, research_summary, tone, target_platforms)

