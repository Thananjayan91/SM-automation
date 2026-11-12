"""Text and caption generation provider."""
import logging
from typing import List, Optional

from .base import BaseTextProvider, CaptionResult, NarrationResult

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

    def generate_narration(
        self,
        topic: str,
        language: str = "english",
        duration_hint: int = 15,
    ) -> NarrationResult:
        lang = _normalize_language(language)
        is_long = int(duration_hint or 15) >= 25

        if lang == "tamil":
            if is_long:
                script = (
                    f"{topic} பற்றிய முக்கிய தகவல்களை இன்று தெரிந்து கொள்வோம். "
                    f"இன்றைய வேகமான உலகில் {topic} மிகப்பெரிய மாற்றத்தை உருவாக்கி வருகிறது. "
                    f"இதன் சிறப்பம்சங்கள் மற்றும் பயன்களை சரியான முறையில் பயன்படுத்தினால் சிறந்த முன்னேற்றம் காணலாம். "
                    f"மேலும் தகவல்களுக்கு எங்கள் பக்கத்தை பின்தொடருங்கள்."
                )
            else:
                script = (
                    f"{topic} பற்றி உங்களுக்கு தெரியுமா? "
                    f"இன்றைய காலத்தில் {topic} புதிய வாய்ப்புகளையும் சிறந்த தீர்வுகளையும் வழங்குகிறது. "
                    f"இதைப் பற்றி மேலும் அறிய இப்போது எங்களோடு இணையுங்கள்."
                )
        elif lang == "sinhala":
            if is_long:
                script = (
                    f"අද අපි {topic} පිළිබඳ වැදගත් කරුණු කිහිපයක් දැනගනිමු. "
                    f"වර්තමාන ලෝකයේ {topic} ඉතා වේගයෙන් වෙනස් වෙමින් පවතිනවා. "
                    f"මෙහි ඇති විශේෂාංග සහ ප්‍රතිලාභ නිවැරදිව භාවිතා කිරීමෙන් ඔබට විශාල දියුණුවක් ලබාගත හැකියි. "
                    f"වැඩිදුර තොරතුරු සඳහා අපගේ පිටුව Follow කරන්න."
                )
            else:
                script = (
                    f"ඔබ {topic} ගැන දැන සිටියාද? "
                    f"වර්තමානයේ {topic} අපට නව අවස්ථා රැසක් නිර්මාණය කර දී තිබෙනවා. "
                    f"වැඩි විස්තර දැනගැනීමට අප සමඟ එකතු වන්න."
                )
        else:
            if is_long:
                script = (
                    f"Have you ever wondered why {topic} is transforming the way we work and live today? "
                    f"Across the industry, people are discovering smarter, faster ways to get real results with {topic}. "
                    f"From everyday efficiency to long-term innovation, the potential is bigger than ever. "
                    f"Start exploring what {topic} can do for you, and follow us for more updates and practical insights."
                )
            else:
                script = (
                    f"Here is why {topic} is gaining attention everywhere right now. "
                    f"It brings together smarter solutions, better performance, and real value in just a few steps. "
                    f"Follow us to learn more today."
                )

        word_count = len(script.split())
        est_duration = round(max(5.0, word_count / 2.5), 1)
        return NarrationResult(
            script=script,
            word_count=word_count,
            estimated_duration_secs=est_duration,
            tokens_used=120,
            cost_usd=0.001,
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

    def generate_narration(
        self,
        topic: str,
        language: str = "english",
        duration_hint: int = 15,
    ) -> NarrationResult:
        lang = _normalize_language(language)
        dur = int(duration_hint or 15)
        target_words = "35 to 42 words" if dur < 22 else "70 to 82 words"

        lang_instructions = {
            "tamil": "Write ONLY in fluent, natural spoken Tamil script (தமிழ்). Avoid mixing long English sentences.",
            "sinhala": "Write ONLY in fluent, natural spoken Sinhala script (සිංහල). Avoid mixing long English sentences.",
            "english": "Write in crisp, engaging, natural spoken English.",
        }

        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            prompt = (
                f"Write a short voiceover narration script for a {dur}-second social media video about: {topic}.\n"
                f"Word count target: strictly around {target_words}.\n"
                f"Language: {lang_instructions[lang]}\n"
                f"IMPORTANT rules:\n"
                f"- Output ONLY the exact spoken words to be read aloud by a text-to-speech voice.\n"
                f"- Do NOT include hashtags, emojis, scene descriptions, brackets, timestamps, or speaker labels.\n"
                f"- Start with an attention-grabbing opening hook and end with a concise call to action."
            )
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            script = (resp.choices[0].message.content or "").strip()
            # Clean any accidental quotes
            if script.startswith('"') and script.endswith('"'):
                script = script[1:-1].strip()
            tokens = resp.usage.total_tokens if resp.usage else 150
            word_count = len(script.split())
            est_duration = round(max(4.0, word_count / 2.5), 1)
            return NarrationResult(
                script=script,
                word_count=word_count,
                estimated_duration_secs=est_duration,
                tokens_used=tokens,
                cost_usd=0.001,
            )
        except Exception as e:
            logger.error(f"OpenAI narration generation failed: {e}. Falling back to MockTextProvider.")
            fallback = MockTextProvider()
            return fallback.generate_narration(topic, language=lang, duration_hint=dur)


