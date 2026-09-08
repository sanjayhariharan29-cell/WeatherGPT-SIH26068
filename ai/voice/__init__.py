"""WeatherGPT Voice AI Integration Package.

Provides Speech-to-Text (STT), Text-to-Speech (TTS), Audio Validation,
and unified VoiceAIService executing the complete pipeline:
VOICE -> STT -> NLU -> WEATHER PIPELINE -> VALIDATOR -> TTS.
"""

from ai.voice.models import (
    AudioValidationResult,
    STTResult,
    TTSResult,
    VoiceResponse
)
from ai.voice.exceptions import (
    VoiceError,
    AudioValidationError,
    EmptyAudioError,
    CorruptedAudioError,
    OversizedAudioError,
    UnsupportedAudioFormatError,
    STTError,
    STTTimeoutError,
    STTNoSpeechError,
    TTSError
)
from ai.voice.audio_validator import AudioValidator
from ai.voice.stt import BaseSTTProvider, MockSTTProvider
from ai.voice.tts import BaseTTSProvider, MockTTSProvider, format_speech_friendly_text
from ai.voice.service import VoiceAIService

__all__ = [
    "AudioValidationResult",
    "STTResult",
    "TTSResult",
    "VoiceResponse",
    "VoiceError",
    "AudioValidationError",
    "EmptyAudioError",
    "CorruptedAudioError",
    "OversizedAudioError",
    "UnsupportedAudioFormatError",
    "STTError",
    "STTTimeoutError",
    "STTNoSpeechError",
    "TTSError",
    "AudioValidator",
    "BaseSTTProvider",
    "MockSTTProvider",
    "BaseTTSProvider",
    "MockTTSProvider",
    "format_speech_friendly_text",
    "VoiceAIService",
]
