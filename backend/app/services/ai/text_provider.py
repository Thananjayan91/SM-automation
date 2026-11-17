"""Text and caption generation provider."""
import logging
from typing import Any, Dict, List, Optional

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

    def suggest_scene_texts(
        self,
        topic: str,
        scene_number: int = 1,
        total_scenes: int = 5,
        language: str = "english",
        script: Optional[str] = None,
    ) -> List[str]:
        lang = _normalize_language(language)
        clean_topic = topic.strip()
        if script and len(script.strip()) > 10:
            extracted = self.extract_phrases_from_narration(script, topic=clean_topic, total_scenes=total_scenes, language=lang)
            phrases = extracted.get("all_phrases") or []
            if phrases:
                start = (scene_number - 1) % len(phrases)
                return phrases[start:start + 3] if len(phrases) >= start + 3 else (phrases[start:] + phrases[:3])[:3]

        if lang == "tamil":
            if scene_number == 1:
                return [f"{clean_topic} — சிறப்பம்சம்", "முக்கிய தகவல்", "இன்றே தெரிந்து கொள்ளுங்கள்"]
            elif scene_number >= total_scenes:
                return ["இன்றே தொடங்குங்கள்!", "மேலும் அறிய பின்தொடருங்கள்", "முக்கிய முடிவு"]
            else:
                return [f"பயன் #{scene_number}", "வேகமான வளர்ச்சி", "சிறந்த பலன்கள்"]
        elif lang == "sinhala":
            if scene_number == 1:
                return [f"{clean_topic} — විශේෂ කරුණු", "නවතම තොරතුරු", "අදම දැනගන්න"]
            elif scene_number >= total_scenes:
                return ["අදම ආරම්භ කරන්න!", "වැඩි විස්තර සඳහා Follow කරන්න", "අවසාන තීරණය"]
            else:
                return [f"ප්‍රතිලාභ #{scene_number}", "වේගවත් දියුණුවක්", "විශිෂ්ට ප්‍රතිඵල"]
        else:
            upper_topic = clean_topic.upper()[:25]
            if scene_number == 1:
                return [f"WHY {upper_topic}?", "THE BIG SECRET", "DON'T MISS THIS"]
            elif scene_number >= total_scenes:
                return ["TRY IT TODAY!", "FOLLOW FOR MORE", "KEY TAKEAWAY"]
            else:
                return [f"BENEFIT #{scene_number}", "GAME CHANGER", "EASY TO IMPLEMENT"]

    def extract_phrases_from_narration(
        self,
        script: str,
        topic: str = "",
        total_scenes: int = 4,
        language: str = "english",
    ) -> Dict[str, Any]:
        """Extract or generate attractive keywords and scene phrases from a narration script."""
        lang = _normalize_language(language)
        clean_topic = topic.strip()
        phrases = []

        clean_script = (script or "").strip()
        if clean_script:
            import re
            sentences = [s.strip() for s in re.split(r"[.!?\n]+", clean_script) if len(s.strip()) > 3]
            for s in sentences[:8]:
                words = s.split()
                if len(words) <= 5:
                    phrase = " ".join(words)
                else:
                    phrase = " ".join(words[:4])
                phrase = re.sub(r'["\',;:()]+', '', phrase).strip()
                if phrase and len(phrase) > 2 and phrase not in phrases:
                    phrases.append(phrase.upper() if lang == "english" else phrase)

        if lang == "tamil":
            default_pool = [
                f"{clean_topic} — முக்கிய தகவல்",
                "அற்புதமான நன்மைகள்",
                "வேகமான முடிவுகள்",
                "இயற்கையான வழிமுறை",
                "ஆரோக்கியமான வாழ்க்கை",
                "இன்றே முயற்சி செய்யுங்கள்!",
                "பயனுள்ள குறிப்புகள்",
                "மேலும் அறிய பின்தொடருங்கள்",
            ]
        elif lang == "sinhala":
            default_pool = [
                f"{clean_topic} — විශේෂ කරුණු",
                "විශිෂ්ට ප්‍රතිඵල",
                "වේගවත් දියුණුවක්",
                "ස්වාභාවික ක්‍රමවේදය",
                "නිරෝගී ජීවිතයක්",
                "අදම උත්සාහ කරන්න!",
                "වැදගත් උපදෙස්",
                "වැඩි විස්තර සඳහා Follow කරන්න",
            ]
        else:
            upper_t = clean_topic.upper()[:25] if clean_topic else "THIS"
            default_pool = [
                f"WHY {upper_t}?",
                "THE BIG BENEFIT",
                "HOW IT WORKS",
                "KEY TAKEAWAY",
                "GAME CHANGER",
                "PRO TIP",
                "EASY TO START",
                "TRY IT TODAY!",
            ]

        for p in default_pool:
            if p not in phrases:
                phrases.append(p)

        scene_phrases = {}
        for s_idx in range(1, total_scenes + 1):
            if s_idx == 1:
                scene_phrases[str(s_idx)] = phrases[0] if phrases else default_pool[0]
            elif s_idx >= total_scenes:
                scene_phrases[str(s_idx)] = default_pool[-1]
            else:
                p_idx = min(s_idx - 1, len(phrases) - 1)
                scene_phrases[str(s_idx)] = phrases[p_idx] if p_idx < len(phrases) else default_pool[min(s_idx, len(default_pool) - 1)]

        return {
            "all_phrases": phrases[:10],
            "scene_phrases": scene_phrases,
        }


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

    def suggest_scene_texts(
        self,
        topic: str,
        scene_number: int = 1,
        total_scenes: int = 5,
        language: str = "english",
        script: Optional[str] = None,
    ) -> List[str]:
        lang = _normalize_language(language)
        fallback = MockTextProvider()
        if script and len(script.strip()) > 10:
            extracted = self.extract_phrases_from_narration(script, topic=topic, total_scenes=total_scenes, language=lang)
            phrases = extracted.get("all_phrases") or []
            if phrases:
                start = (scene_number - 1) % len(phrases)
                return phrases[start:start + 3] if len(phrases) >= start + 3 else (phrases[start:] + phrases[:3])[:3]

        lang_prompt = {
            "tamil": "Suggest 2-3 short, punchy visual keywords/phrases in Tamil script (தமிழ்) (3-5 words each).",
            "sinhala": "Suggest 2-3 short, punchy visual keywords/phrases in Sinhala script (සිංහල) (3-5 words each).",
            "english": "Suggest 2-3 short, punchy visual keywords/phrases in uppercase English (3-5 words each).",
        }
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            prompt = (
                f"Topic: {topic}\n"
                f"Scene {scene_number} of {total_scenes} in a short social video reel.\n"
                f"{lang_prompt[lang]}\n"
                f"These will be bold text overlays on the video slide.\n"
                f"Return ONLY the phrases, one per line, no numbering, no bullets, no quotes."
            )
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
            )
            lines = [
                line.strip().strip('"').strip("'")
                for line in (resp.choices[0].message.content or "").splitlines()
                if line.strip()
            ]
            return lines[:3] if lines else fallback.suggest_scene_texts(topic, scene_number, total_scenes, language=lang)
        except Exception as e:
            logger.error(f"OpenAI text suggestion failed: {e}. Falling back to MockTextProvider.")
            return fallback.suggest_scene_texts(topic, scene_number, total_scenes, language=lang)

    def extract_phrases_from_narration(
        self,
        script: str,
        topic: str = "",
        total_scenes: int = 4,
        language: str = "english",
    ) -> Dict[str, Any]:
        """Extract attractive keywords and scene phrases from a narration script using OpenAI."""
        lang = _normalize_language(language)
        fallback = MockTextProvider()
        if not self.api_key:
            return fallback.extract_phrases_from_narration(script, topic, total_scenes, language=lang)

        lang_instructions = {
            "tamil": "Extract 6-8 short, attractive keywords or phrases in Tamil script (தமிழ்) (2-5 words each).",
            "sinhala": "Extract 6-8 short, attractive keywords or phrases in Sinhala script (සිංහල) (2-5 words each).",
            "english": "Extract 6-8 short, attractive keywords or phrases in UPPERCASE English (2-4 words each).",
        }

        prompt = (
            f"Topic: {topic}\n"
            f"Narration Script:\n\"{script}\"\n\n"
            f"{lang_instructions[lang]}\n"
            f"These phrases will be placed as bold, punchy text overlays on video slides.\n"
            f"Each phrase should capture a key insight, benefit, hook, or call to action.\n"
            f"Return ONLY the phrases, one per line, no numbering, no bullet points, no quotes."
        )

        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
            )
            raw_lines = [
                line.strip().strip('"').strip("'").lstrip("-*123456789. ")
                for line in (resp.choices[0].message.content or "").splitlines()
                if line.strip()
            ]
            phrases = raw_lines if raw_lines else fallback.extract_phrases_from_narration(script, topic, total_scenes, language=lang)["all_phrases"]

            scene_phrases = {}
            for s_idx in range(1, total_scenes + 1):
                p_idx = s_idx - 1
                scene_phrases[str(s_idx)] = phrases[p_idx % len(phrases)] if phrases else f"SCENE {s_idx}"

            return {
                "all_phrases": phrases[:10],
                "scene_phrases": scene_phrases,
            }
        except Exception as e:
            logger.error(f"OpenAI phrase extraction failed: {e}. Using fallback.")
            return fallback.extract_phrases_from_narration(script, topic, total_scenes, language=lang)



