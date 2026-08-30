"""Speech-to-text abstraction.

Mock provider returns a realistic transcript so the demo always works.
Live providers (whisper, bhashini) require API keys.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)


class SpeechProvider(Protocol):
    name: str

    def transcribe(self, *, audio_bytes: bytes, mime: str, language: str) -> Dict[str, Any]:
        ...


class MockSpeechProvider:
    name = "mock"

    _DEFAULT_SCRIPT = "I have been having a headache for the last two weeks."

    def transcribe(self, *, audio_bytes, mime, language) -> Dict[str, Any]:
        return {
            "text": self._DEFAULT_SCRIPT,
            "language": language,
            "confidence": 0.95,
            "provider": self.name,
        }


class WhisperSpeechProvider:
    name = "whisper"

    def __init__(self) -> None:
        self._client = None
        if get_settings().openai_api_key:
            try:
                from openai import OpenAI  # type: ignore
                self._client = OpenAI(api_key=get_settings().openai_api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Whisper init failed: %s", exc)

    def transcribe(self, *, audio_bytes, mime, language) -> Dict[str, Any]:
        if not self._client:
            return MockSpeechProvider().transcribe(audio_bytes=audio_bytes, mime=mime, language=language)
        try:
            tmp = "/tmp/medikiosk_audio." + (mime.split("/")[-1] if mime else "wav")
            with open(tmp, "wb") as f:
                f.write(audio_bytes)
            with open(tmp, "rb") as f:
                r = self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language=language,
                )
            return {"text": r.text, "language": language, "confidence": 0.9, "provider": self.name}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Whisper failed, falling back to mock: %s", exc)
            return MockSpeechProvider().transcribe(audio_bytes=audio_bytes, mime=mime, language=language)


class BhashiniSpeechProvider:
    name = "bhashini"

    def __init__(self) -> None:
        self._api_key = get_settings().bhashini_api_key

    def transcribe(self, *, audio_bytes, mime, language) -> Dict[str, Any]:
        if not self._api_key:
            return MockSpeechProvider().transcribe(audio_bytes=audio_bytes, mime=mime, language=language)
        try:
            # In production, this would call the Bhashini STT API
            # Mocking the API call response for the prototype
            return {
                "text": "Bhashini-transcribed text for demo",
                "language": language,
                "confidence": 0.88,
                "provider": self.name,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Bhashini failed: %s", exc)
            return MockSpeechProvider().transcribe(audio_bytes=audio_bytes, mime=mime, language=language)


def get_speech_provider() -> SpeechProvider:
    s = get_settings()
    if s.speech_provider.lower() == "bhashini":
        return BhashiniSpeechProvider()
    if s.speech_provider.lower() == "whisper":
        return WhisperSpeechProvider()
    return MockSpeechProvider()


# ----------------------------- TTS --------------------------------

class TTSProvider(Protocol):
    name: str

    def synthesize(self, *, text: str, language: str) -> bytes:
        ...


class MockTTSProvider:
    name = "mock"

    def synthesize(self, *, text, language) -> bytes:
        # Return a silent WAV or a small beep
        return b"MOCK_AUDIO_DATA"


class GoogleTTSProvider:
    name = "google"

    def synthesize(self, *, text, language) -> bytes:
        try:
            from gtts import gTTS  # type: ignore
            import io
            tts = gTTS(text=text, lang=language)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            return fp.getvalue()
        except Exception as exc:  # noqa: BLE001
            logger.warning("GoogleTTS failed: %s", exc)
            return MockTTSProvider().synthesize(text=text, language=language)


def get_tts_provider() -> TTSProvider:
    # Default to Google for the prototype as it's free/easy
    return GoogleTTSProvider()
