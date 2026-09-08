"""Voice AI Exception Hierarchy.

Isolates speech recognition, audio validation, and audio synthesis errors
behind predictable domain exceptions.
"""


class VoiceError(Exception):
    """Base exception for all Voice AI operations."""
    def __init__(self, message: str, provider: str = "Voice"):
        self.message = message
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class AudioValidationError(VoiceError):
    """Raised when uploaded or captured audio fails safety and integrity checks."""
    pass


class EmptyAudioError(AudioValidationError):
    """Raised when audio payload contains 0 bytes or empty stream."""
    pass


class CorruptedAudioError(AudioValidationError):
    """Raised when audio payload has corrupted header or unparseable audio stream."""
    pass


class OversizedAudioError(AudioValidationError):
    """Raised when audio payload exceeds configured maximum size limits."""
    pass


class UnsupportedAudioFormatError(AudioValidationError):
    """Raised when audio payload container is not an approved format."""
    pass


class STTError(VoiceError):
    """Raised when Speech-to-Text transcription fails."""
    pass


class STTTimeoutError(STTError):
    """Raised when Speech-to-Text provider times out during recognition."""
    pass


class STTNoSpeechError(STTError):
    """Raised when audio is valid but contains no recognizable speech."""
    pass


class TTSError(VoiceError):
    """Raised when Text-to-Speech audio synthesis fails."""
    pass
