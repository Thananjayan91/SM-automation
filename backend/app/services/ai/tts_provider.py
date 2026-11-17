"""Multilingual Text-to-Speech (TTS) voiceover provider supporting English, Tamil, and Sinhala."""
import io
import logging
import math
import struct
import wave
from typing import Any, Dict, List, Optional

from .base import BaseTTSProvider, TTSResult

logger = logging.getLogger(__name__)

VOICE_CATALOG: List[Dict[str, Any]] = [
    # English Voices (OpenAI TTS)
    {"id": "nova", "name": "Nova", "gender": "Female", "language": "english", "label": "English — Nova (Warm, Natural)", "provider": "openai"},
    {"id": "alloy", "name": "Alloy", "gender": "Neutral", "language": "english", "label": "English — Alloy (Versatile, Clear)", "provider": "openai"},
    {"id": "echo", "name": "Echo", "gender": "Male", "language": "english", "label": "English — Echo (Smooth, Confident)", "provider": "openai"},
    {"id": "onyx", "name": "Onyx", "gender": "Male", "language": "english", "label": "English — Onyx (Deep, Authoritative)", "provider": "openai"},
    {"id": "shimmer", "name": "Shimmer", "gender": "Female", "language": "english", "label": "English — Shimmer (Bright, Upbeat)", "provider": "openai"},
    {"id": "fable", "name": "Fable", "gender": "Expressive", "language": "english", "label": "English — Fable (British Accent)", "provider": "openai"},

    # Tamil Voices (Neural TTS - 2 India + 2 Sri Lanka)
    {"id": "ta-pallavi", "name": "Pallavi (பல்லவி)", "gender": "Female", "language": "tamil", "label": "Tamil — Pallavi (பெண் - Female)", "provider": "edge", "voice_name": "ta-IN-PallaviNeural", "gtts_lang": "ta"},
    {"id": "ta-valluvar", "name": "Valluvar (வள்ளுவர்)", "gender": "Male", "language": "tamil", "label": "Tamil — Valluvar (ஆண் - Male)", "provider": "edge", "voice_name": "ta-IN-ValluvarNeural", "gtts_lang": "ta"},
    {"id": "ta-saranya", "name": "Saranya (சரண்யா)", "gender": "Female", "language": "tamil", "label": "Tamil (LK) — Saranya (பெண் - Female)", "provider": "edge", "voice_name": "ta-LK-SaranyaNeural", "gtts_lang": "ta"},
    {"id": "ta-kumar", "name": "Kumar (குமார்)", "gender": "Male", "language": "tamil", "label": "Tamil (LK) — Kumar (ஆண் - Male)", "provider": "edge", "voice_name": "ta-LK-KumarNeural", "gtts_lang": "ta"},

    # Sinhala Voices (Neural TTS - 1 Female + 1 Male)
    {"id": "si-thilini", "name": "Thilini (තිලිණි)", "gender": "Female", "language": "sinhala", "label": "Sinhala — Thilini (කාන්තා - Female)", "provider": "edge", "voice_name": "si-LK-ThiliniNeural", "gtts_lang": "si"},
    {"id": "si-sameera", "name": "Sameera (සමීර)", "gender": "Male", "language": "sinhala", "label": "Sinhala — Sameera (පිරිමි - Male)", "provider": "edge", "voice_name": "si-LK-SameeraNeural", "gtts_lang": "si"},
]

VOICE_MAP = {v["id"]: v for v in VOICE_CATALOG}
SUPPORTED_VOICES = [v["id"] for v in VOICE_CATALOG]
DEFAULT_VOICE = "nova"


def synthesize_neural_speech(text: str, voice_info: Dict[str, Any]) -> Optional[bytes]:
    """Synthesize speech using Microsoft Edge Neural TTS or gTTS fallback."""
    voice_name = voice_info.get("voice_name")
    if voice_name:
        try:
            import asyncio
            import edge_tts

            async def _run():
                comm = edge_tts.Communicate(text, voice_name)
                buf = io.BytesIO()
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                return buf.getvalue()

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        return pool.submit(asyncio.run, _run()).result()
                else:
                    return loop.run_until_complete(_run())
            except RuntimeError:
                return asyncio.run(_run())
        except Exception as e:
            logger.warning(f"edge-tts neural synthesis failed ({voice_name}): {e}. Attempting gTTS fallback.")

    # Fallback to gTTS if available
    gtts_lang = voice_info.get("gtts_lang", "ta")
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=gtts_lang)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"gTTS fallback synthesis failed ({gtts_lang}): {e}")

    return None


def _generate_synthetic_tone_wav(duration_secs: float = 5.0, freq_hz: float = 440.0) -> bytes:
    """Generate a clean synthetic WAV audio in memory as a deterministic fallback."""
    sample_rate = 22050
    num_samples = int(sample_rate * max(1.0, duration_secs))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        data = bytearray()
        for i in range(num_samples):
            t = float(i) / sample_rate
            envelope = min(1.0, t / 0.1) * min(1.0, (duration_secs - t) / 0.1)
            val = int(envelope * 8000.0 * math.sin(2.0 * math.pi * freq_hz * t))
            data.extend(struct.pack("<h", max(-32768, min(32767, val))))
        wav_file.writeframes(data)
    return buffer.getvalue()


class MockTTSProvider(BaseTTSProvider):
    """Generates synthetic audio bytes for tests or offline development."""

    def generate_speech(self, text: str, voice: str = DEFAULT_VOICE) -> TTSResult:
        selected_voice = voice.lower().strip() if voice else DEFAULT_VOICE
        if selected_voice not in SUPPORTED_VOICES:
            selected_voice = DEFAULT_VOICE

        word_count = len((text or "").split())
        duration = round(max(3.0, min(60.0, word_count / 2.5 if word_count > 0 else 5.0)), 1)
        audio_bytes = _generate_synthetic_tone_wav(duration_secs=duration)
        return TTSResult(
            audio_bytes=audio_bytes,
            mime_type="audio/wav",
            voice_used=selected_voice,
            duration_secs=duration,
            cost_usd=0.0,
        )


class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI Text-to-Speech provider with native Tamil and Sinhala neural voice support."""

    def __init__(self, api_key: str, model: str = "tts-1"):
        self.api_key = api_key
        self.model = model

    def generate_speech(self, text: str, voice: str = DEFAULT_VOICE) -> TTSResult:
        selected_voice = voice.lower().strip() if voice else DEFAULT_VOICE
        if selected_voice not in SUPPORTED_VOICES:
            selected_voice = DEFAULT_VOICE

        voice_info = VOICE_MAP.get(selected_voice, {})
        provider_type = voice_info.get("provider", "openai")

        word_count = len((text or "").split())
        est_duration = round(max(3.0, word_count / 2.5), 1)

        # 1. Neural TTS for Tamil / Sinhala voices
        if provider_type == "edge":
            audio_bytes = synthesize_neural_speech(text, voice_info)
            if audio_bytes and len(audio_bytes) > 500:
                return TTSResult(
                    audio_bytes=audio_bytes,
                    mime_type="audio/mpeg",
                    voice_used=selected_voice,
                    duration_secs=est_duration,
                    cost_usd=0.0,
                )

        # 2. OpenAI TTS for English voices
        if self.api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                openai_voice = selected_voice if selected_voice in ["nova", "alloy", "echo", "fable", "onyx", "shimmer"] else "nova"
                response = client.audio.speech.create(
                    model=self.model,
                    voice=openai_voice,
                    input=text,
                    response_format="mp3",
                )
                mp3_bytes = response.content
                char_count = len(text)
                cost = round((char_count / 1000.0) * 0.015, 5)

                return TTSResult(
                    audio_bytes=mp3_bytes,
                    mime_type="audio/mpeg",
                    voice_used=selected_voice,
                    duration_secs=est_duration,
                    cost_usd=cost,
                )
            except Exception as e:
                logger.error(f"OpenAI TTS synthesis failed: {e}. Trying neural fallback.")

        # 3. Fallback to neural speech if configured
        if voice_info.get("voice_name") or voice_info.get("gtts_lang"):
            audio_bytes = synthesize_neural_speech(text, voice_info)
            if audio_bytes and len(audio_bytes) > 500:
                return TTSResult(
                    audio_bytes=audio_bytes,
                    mime_type="audio/mpeg",
                    voice_used=selected_voice,
                    duration_secs=est_duration,
                    cost_usd=0.0,
                )

        fallback = MockTTSProvider()
        return fallback.generate_speech(text, voice=selected_voice)
