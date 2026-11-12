"""OpenAI Text-to-Speech (TTS) voiceover provider."""
import io
import logging
import math
import struct
import wave
from typing import Optional

from .base import BaseTTSProvider, TTSResult

logger = logging.getLogger(__name__)

SUPPORTED_VOICES = ["nova", "alloy", "echo", "fable", "onyx", "shimmer"]
DEFAULT_VOICE = "nova"


def _generate_synthetic_tone_wav(duration_secs: float = 5.0, freq_hz: float = 440.0) -> bytes:
    """Generate a clean synthetic WAV audio in memory as a deterministic fallback."""
    sample_rate = 22050
    num_samples = int(sample_rate * max(1.0, duration_secs))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        # Generate gentle fade-in / fade-out tone
        data = bytearray()
        for i in range(num_samples):
            t = float(i) / sample_rate
            # 0.1s envelope fade
            envelope = min(1.0, t / 0.1) * min(1.0, (duration_secs - t) / 0.1)
            val = int(envelope * 8000.0 * math.sin(2.0 * math.pi * freq_hz * t))
            data.extend(struct.pack("<h", max(-32768, min(32767, val))))
        wav_file.writeframes(data)
    return buffer.getvalue()


class MockTTSProvider(BaseTTSProvider):
    """Generates synthetic audio bytes for tests or offline development."""

    def generate_speech(self, text: str, voice: str = DEFAULT_VOICE) -> TTSResult:
        word_count = len((text or "").split())
        duration = round(max(3.0, min(60.0, word_count / 2.5 if word_count > 0 else 5.0)), 1)
        audio_bytes = _generate_synthetic_tone_wav(duration_secs=duration)
        return TTSResult(
            audio_bytes=audio_bytes,
            mime_type="audio/wav",
            voice_used=voice or DEFAULT_VOICE,
            duration_secs=duration,
            cost_usd=0.0,
        )


class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI Text-to-Speech provider using tts-1 / tts-1-hd."""

    def __init__(self, api_key: str, model: str = "tts-1"):
        self.api_key = api_key
        self.model = model

    def generate_speech(self, text: str, voice: str = DEFAULT_VOICE) -> TTSResult:
        selected_voice = voice.lower().strip() if voice else DEFAULT_VOICE
        if selected_voice not in SUPPORTED_VOICES:
            selected_voice = DEFAULT_VOICE

        word_count = len((text or "").split())
        est_duration = round(max(3.0, word_count / 2.5), 1)

        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            response = client.audio.speech.create(
                model=self.model,
                voice=selected_voice,
                input=text,
                response_format="mp3",
            )
            mp3_bytes = response.content
            # OpenAI TTS-1 is $0.015 per 1,000 characters
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
            logger.error(f"OpenAI TTS synthesis failed: {e}. Falling back to MockTTSProvider.")
            fallback = MockTTSProvider()
            return fallback.generate_speech(text, voice=selected_voice)
