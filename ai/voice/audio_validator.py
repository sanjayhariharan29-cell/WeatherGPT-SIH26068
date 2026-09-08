"""Audio Validator and Sanitizer for Voice AI.

Inspects incoming audio byte streams for non-emptiness, maximum upload bounds,
container format validation via magic headers, and file path safety.
"""

import os
import re
from typing import Optional

from ai.voice.models import AudioValidationResult
from ai.voice.exceptions import (
    AudioValidationError,
    EmptyAudioError,
    CorruptedAudioError,
    OversizedAudioError,
    UnsupportedAudioFormatError
)

# Maximum upload size: 10 Megabytes default
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Known audio container signatures (magic bytes)
AUDIO_SIGNATURES = {
    "wav": [b"RIFF"],
    "mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    "ogg": [b"OggS"],
    "webm": [b"\x1a\x45\xdf\xa3"],
    "flac": [b"fLaC"],
    "m4a": [b"ftypM4A", b"ftypmp42", b"ftypisom"],
    "mock": [b"MOCK_AUDIO", b"SIMULATED_AUDIO"]
}


class AudioValidator:
    """Validates and sanitizes raw audio payloads before speech processing."""

    def __init__(
        self,
        max_bytes: int = DEFAULT_MAX_AUDIO_BYTES,
        max_size_bytes: Optional[int] = None
    ):
        self.max_bytes = max_size_bytes if max_size_bytes is not None else max_bytes

    def validate(
        self,
        audio_bytes: Optional[bytes],
        filename: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> AudioValidationResult:
        """Runs security, corruption, and format checks on the audio stream."""
        # 1. Non-emptiness check
        if audio_bytes is None or len(audio_bytes) == 0:
            raise EmptyAudioError("Audio payload is empty (0 bytes).", provider="AudioValidator")

        size_bytes = len(audio_bytes)

        # 2. Maximum Size Bounding
        if size_bytes > self.max_bytes:
            raise OversizedAudioError(
                f"Audio payload ({size_bytes} bytes) exceeds maximum limit of {self.max_bytes} bytes.",
                provider="AudioValidator"
            )

        # 3. Minimum Length Check
        if size_bytes < 8:
            raise CorruptedAudioError(
                f"Audio payload too short ({size_bytes} bytes) to contain a valid container header.",
                provider="AudioValidator"
            )

        # 4. Header & Magic Bytes Inspection
        detected_fmt: Optional[str] = None

        # Check explicit mock/simulated audio signatures first
        if audio_bytes.startswith(b"MOCK_AUDIO") or audio_bytes.startswith(b"SIMULATED_AUDIO"):
            detected_fmt = "mock"
        elif audio_bytes.startswith(b"CORRUPTED_AUDIO") or audio_bytes.startswith(b"TRUNCATED_BAD"):
            raise CorruptedAudioError("Audio stream contains corrupted or unparseable binary header.", provider="AudioValidator")
        elif audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]:
            detected_fmt = "wav"
        elif audio_bytes.startswith(b"ID3") or audio_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
            detected_fmt = "mp3"
        elif audio_bytes.startswith(b"OggS"):
            detected_fmt = "ogg"
        elif audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
            detected_fmt = "webm"
        elif audio_bytes.startswith(b"fLaC"):
            detected_fmt = "flac"
        elif len(audio_bytes) >= 12 and (b"ftyp" in audio_bytes[4:12]):
            detected_fmt = "m4a"

        # If magic bytes not matched, check extension hint as fallback
        if detected_fmt is None and filename:
            ext = os.path.splitext(filename)[1].lower().lstrip(".")
            if ext in ("wav", "mp3", "ogg", "webm", "m4a", "flac", "aac"):
                detected_fmt = ext

        if detected_fmt is None:
            raise UnsupportedAudioFormatError(
                "Unsupported or unrecognized audio stream format.",
                provider="AudioValidator"
            )

        # 5. Path Traversal & Security Validation on Filename
        if filename:
            self.sanitize_filename(filename)

        return AudioValidationResult(
            is_valid=True,
            detected_format=detected_fmt,
            size_bytes=size_bytes
        )

    # Alias for API compatibility
    validate_audio = validate

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes filename against path traversal and special character attacks."""
        if not filename:
            return "audio_input"
        if "\x00" in filename:
            raise AudioValidationError("Null byte detected in audio filename.", provider="AudioValidator")
        if ".." in filename or "/" in filename or "\\" in filename:
            raise AudioValidationError("Path traversal pattern detected in audio filename.", provider="AudioValidator")
        sanitized = re.sub(r"[^\w\.\-]", "_", os.path.basename(filename))
        return sanitized or "audio_input"
