"""Speech-to-Text (STT) Provider Architecture for WeatherGPT.

Provides abstract provider interface and deterministic mock implementations
for offline and unit testing across English, Tamil, Hindi, Tanglish, and Hinglish.
"""

from abc import ABC, abstractmethod
from typing import Optional

from ai.voice.models import STTResult
from ai.voice.exceptions import (
    STTError,
    STTTimeoutError,
    STTNoSpeechError
)


class BaseSTTProvider(ABC):
    """Abstract base class for all Speech-to-Text transcription providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        language_hint: Optional[str] = None
    ) -> STTResult:
        """Transcribes raw audio bytes into an untrusted text transcript."""
        pass


class MockSTTProvider(BaseSTTProvider):
    """Deterministic Speech-to-Text provider for local and automated testing."""

    def __init__(
        self,
        forced_transcript: Optional[str] = None,
        forced_language: Optional[str] = None,
        simulate_timeout: bool = False,
        simulate_error: bool = False,
        simulate_no_speech: bool = False
    ):
        self.forced_transcript = forced_transcript
        self.forced_language = forced_language
        self.simulate_timeout = simulate_timeout
        self.simulate_error = simulate_error
        self.simulate_no_speech = simulate_no_speech

    async def transcribe(
        self,
        audio_bytes: bytes,
        language_hint: Optional[str] = None
    ) -> STTResult:
        """Deterministically resolves audio bytes to realistic transcripts."""
        # Simulated fault injection
        if self.simulate_timeout:
            raise STTTimeoutError("Speech recognition request timed out after 5000ms.", provider="MockSTT")
        if self.simulate_error:
            raise STTError("External speech service unavailable (status 503).", provider="MockSTT")
        if self.simulate_no_speech:
            raise STTNoSpeechError("No voice activity detected in audio payload.", provider="MockSTT")

        # In-payload simulation tokens for targeted scenario tests
        if b"SIMULATE_TIMEOUT" in audio_bytes:
            raise STTTimeoutError("Speech recognition request timed out.", provider="MockSTT")
        if b"SIMULATE_ERROR" in audio_bytes:
            raise STTError("Speech-to-text service error.", provider="MockSTT")
        if b"SIMULATE_SILENCE" in audio_bytes:
            raise STTNoSpeechError("Audio stream contains only background noise/silence.", provider="MockSTT")

        # Static overrides
        if self.forced_transcript:
            return STTResult(
                transcript=self.forced_transcript,
                detected_language=self.forced_language or language_hint or "en",
                confidence=0.98,
                duration_sec=3.2,
                provider="MockSTT"
            )

        # Content-based deterministic resolution for language test fixtures
        if b"MOCK_AUDIO_TAMIL" in audio_bytes:
            return STTResult(
                transcript="நாளைக்கு கோயம்புத்தூரில் மழை வருமா?",
                detected_language="ta",
                confidence=0.95,
                duration_sec=2.5,
                provider="MockSTT"
            )
        elif b"MOCK_AUDIO_HINDI" in audio_bytes:
            return STTResult(
                transcript="कल कोयंबटूर में बारिश होगी क्या?",
                detected_language="hi",
                confidence=0.94,
                duration_sec=2.8,
                provider="MockSTT"
            )
        elif b"MOCK_AUDIO_TANGLISH" in audio_bytes:
            return STTResult(
                transcript="Naalaiku Coimbatore la mazhai varuma?",
                detected_language="tanglish",
                confidence=0.92,
                duration_sec=2.6,
                provider="MockSTT"
            )
        elif b"MOCK_AUDIO_HINGLISH" in audio_bytes:
            return STTResult(
                transcript="Aaj Coimbatore mein baarish hogi kya?",
                detected_language="hinglish",
                confidence=0.93,
                duration_sec=2.7,
                provider="MockSTT"
            )
        elif b"MOCK_AUDIO_ENGLISH" in audio_bytes:
            return STTResult(
                transcript="What is the weather today in Coimbatore?",
                detected_language="en",
                confidence=0.99,
                duration_sec=2.1,
                provider="MockSTT"
            )

        # Fallback based on language hint
        hint = (language_hint or "ta").lower()
        if hint == "ta":
            return STTResult(
                transcript="நாளைக்கு கோயம்புத்தூரில் மழை வருமா?",
                detected_language="ta",
                confidence=0.92,
                duration_sec=2.5,
                provider="MockSTT"
            )
        elif hint == "hi":
            return STTResult(
                transcript="कल कोयंबटूर में बारिश होगी क्या?",
                detected_language="hi",
                confidence=0.91,
                duration_sec=2.6,
                provider="MockSTT"
            )
        elif hint == "tanglish":
            return STTResult(
                transcript="Naalaiku morning college pogalama?",
                detected_language="tanglish",
                confidence=0.90,
                duration_sec=2.3,
                provider="MockSTT"
            )
        elif hint == "hinglish":
            return STTResult(
                transcript="Aaj Coimbatore mein baarish hogi kya?",
                detected_language="hinglish",
                confidence=0.90,
                duration_sec=2.4,
                provider="MockSTT"
            )
        else:
            return STTResult(
                transcript="What is the current weather in Coimbatore?",
                detected_language="en",
                confidence=0.96,
                duration_sec=2.2,
                provider="MockSTT"
            )
