"""Text-to-Speech (TTS) Provider Architecture for WeatherGPT.

Provides abstract provider interface, phonetic speech-formatting utilities,
and deterministic mock implementations for English, Tamil, and Hindi.
Preserves official warning authority and exact numeric values.
"""

import re
from abc import ABC, abstractmethod
from typing import Optional

from ai.voice.models import TTSResult
from ai.voice.exceptions import TTSError


def format_concise_speech_text(text: str, language: str = "en") -> str:
    """Extracts and formats a concise, speech-friendly summary for voice output.
    
    CRITICAL POLICIES:
    1. Warning Priority: Active warnings are stated upfront (Status -> Area -> Critical Action).
    2. Brevity: Excludes technical debug metadata (Source, age, consistency scores), markdown symbols, and HTML tags.
    3. Multilingual Phonetics: Expands units phonetically in English, Tamil, and Hindi.
    """
    if not text:
        return ""

    raw = text.strip()

    # 1. Remove parenthetical telemetry/source citations e.g. (Source: ... | Updated ...)
    raw = re.sub(r'\([^)|\n]*?(?:Source|Updated|Forecast Consistency|स्रोत|தகவல் மூலம்)[^)|\n]*?\)', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\(தகவல் மூலம்:[^)\n]*?\)', '', raw)
    raw = re.sub(r'\(स्रोत:[^)\n]*?\)', '', raw)

    # 2. Remove emojis and HTML tags
    raw = re.sub(r'<[^>]+>', '', raw)
    raw = re.sub(r'[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\u2700-\u27BF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF]', '', raw)

    # 3. Clean markdown headers, bold, bullets, links
    raw = re.sub(r'^#{1,6}\s+', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\*\*([^*]+)\*\*', r'\1', raw)
    raw = re.sub(r'\*([^*]+)\*', r'\1', raw)
    raw = re.sub(r'^\s*[-•*]\s+', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', raw)

    # 4. Filter and select high-priority sentences (Warning, current weather, advisory)
    lines = [line.strip() for line in raw.split('\n') if line.strip()]
    selected_lines = []

    has_warning = any("warning" in l.lower() or "எச்சரிக்கை" in l or "चेतावनी" in l for l in lines)

    for line in lines:
        lower = line.lower()
        # Skip technical disclaimers or repetitive headings in voice
        if any(skip in lower for skip in [
            "forecast consistency (", "forecast consistency score", "data confidence indicator",
            "historical records reflect", "historical data represents", "skyzen does not fabricate"
        ]):
            continue
        selected_lines.append(line)
        # For voice brevity, limit normal non-warning answers to 4 key sentences
        if not has_warning and len(selected_lines) >= 3:
            break
        elif has_warning and len(selected_lines) >= 5:
            break

    concise = " ".join(selected_lines) if selected_lines else raw

    # 5. Phonetic unit expansions
    return format_speech_friendly_text(concise, language=language)


def format_speech_friendly_text(text: str, language: str = "en") -> str:
    """Formats validated meteorological text for clear and accurate speech synthesis.
    
    CRITICAL RULES:
    1. Numeric Preservation: Never alter the underlying numeric value (e.g., 31.5°C -> 31.5 degrees Celsius).
    2. Warning Authority: Never alter official alerts ("Official IMD warning" stays authoritative).
    3. Multilingual expansions: Expand units cleanly in English, Tamil, and Hindi.
    """
    if not text:
        return ""

    formatted = text

    # Standardize unit pronunciation while strictly keeping the numeric digits intact
    if language in ("ta", "tanglish"):
        # Tamil expansions
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*°C', r'\1 டிகிரி செல்சியஸ்', formatted)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 சதவீதம்', formatted)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*mm\b', r'\1 மில்லிமீட்டர்', formatted, flags=re.IGNORECASE)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*km/h\b', r'\1 கிலோமீட்டர்/மணி', formatted, flags=re.IGNORECASE)
    elif language in ("hi", "hinglish"):
        # Hindi expansions
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*°C', r'\1 डिग्री सेल्सियस', formatted)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 प्रतिशत', formatted)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*mm\b', r'\1 मिलीमीटर', formatted, flags=re.IGNORECASE)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*km/h\b', r'\1 किलोमीटर प्रति घंटा', formatted, flags=re.IGNORECASE)
    else:
        # English / default expansions
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*°C', r'\1 degrees Celsius', formatted)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', formatted)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*mm\b', r'\1 millimeters', formatted, flags=re.IGNORECASE)
        formatted = re.sub(r'(\d+(?:\.\d+)?)\s*km/h\b', r'\1 kilometers per hour', formatted, flags=re.IGNORECASE)

    # Clean double spaces
    formatted = re.sub(r'\s{2,}', ' ', formatted).strip()
    return formatted


class BaseTTSProvider(ABC):
    """Abstract base class for all Text-to-Speech synthesis providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str = "en"
    ) -> TTSResult:
        """Synthesizes validated text into speech audio."""
        pass


class MockTTSProvider(BaseTTSProvider):
    """Deterministic Text-to-Speech provider for local development and test suites."""

    def __init__(
        self,
        simulate_error: bool = False,
        base_audio_url: str = "simulated_tts_audio.mp3"
    ):
        self.simulate_error = simulate_error
        self.base_audio_url = base_audio_url

    async def synthesize(
        self,
        text: str,
        language: str = "en"
    ) -> TTSResult:
        """Deterministically synthesizes speech result or raises TTSError upon fault injection."""
        if self.simulate_error or "SIMULATE_TTS_ERROR" in text:
            raise TTSError("Speech synthesis provider unavailable (HTTP 503).", provider="MockTTS")

        speech_text = format_concise_speech_text(text, language=language)
        
        # Estimate duration (~3 words per second, min 1.0s)
        words = speech_text.split()
        estimated_duration = max(1.0, round(len(words) / 3.0, 1))

        # Simulated audio bytes (ID3 header mock representation)
        simulated_bytes = b"ID3\x04\x00\x00\x00\x00\x00#MOCK_TTS_AUDIO_STREAM#" + speech_text.encode("utf-8")[:100]

        return TTSResult(
            audio_bytes=simulated_bytes,
            audio_url=f"/static/audio/{language}_{self.base_audio_url}",
            audio_format="mp3",
            duration_sec=estimated_duration,
            success=True,
            provider="MockTTS"
        )
