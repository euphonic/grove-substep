"""Text-to-speech adapter. Mock returns silent WAV audio of a plausible spoken length."""

import io
import wave
from typing import Protocol

from app.config import Settings

WORDS_PER_MINUTE = 150
SAMPLE_RATE = 16_000


def estimated_seconds(text: str) -> float:
    words = len(text.split())
    return max(0.5, words / WORDS_PER_MINUTE * 60)


class TTS(Protocol):
    def synthesize(self, text: str, voice_id: str) -> bytes: ...


class MockTTS:
    def synthesize(self, text: str, voice_id: str) -> bytes:
        frames = int(estimated_seconds(text) * SAMPLE_RATE)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(b"\x00\x00" * frames)
        return buf.getvalue()


def get_tts(settings: Settings) -> TTS:
    if settings.tts_mode == "mock":
        return MockTTS()
    raise NotImplementedError("ElevenLabs TTS is wired up in M6")
