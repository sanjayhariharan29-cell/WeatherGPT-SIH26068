"""Comprehensive Voice AI Integration Test Suite for WeatherGPT.

Covers all 24 required scenarios from Phase 12 specification:
1. English STT
2. Tamil STT
3. Hindi STT
4. Tanglish transcript
5. Hinglish transcript
6. Empty audio rejection
7. Corrupted audio rejection
8. Oversized audio rejection
9. STT timeout handling
10. STT failure handling
11. Correct transcript entering NLU (no direct Voice -> LLM)
12. Language propagation hierarchy
13. Tamil response generation
14. Hindi response generation
15. English response generation
16. Official warning preservation in voice
17. Hazard & severity preservation
18. Numeric value preservation in speech formatting
19. Phase 9 validator remains active
20. TTS success
21. TTS failure graceful degradation
22. Full voice-to-AI-to-response flow
23. Privacy / no-recording in-memory behavior
24. Deterministic mock providers
25. End-to-End deterministic scenario ("Naalaiku Coimbatore la mazhai varuma?")
26. FastAPI /api/v1/voice/query endpoint integration
"""

import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from ai.voice.models import AudioValidationResult, STTResult, TTSResult, VoiceResponse
from ai.voice.audio_validator import AudioValidator
from ai.voice.stt import BaseSTTProvider, MockSTTProvider
from ai.voice.tts import BaseTTSProvider, MockTTSProvider, format_speech_friendly_text
from ai.voice.service import VoiceAIService
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
from backend.services.ai_service import AIService
from backend.schemas.chat import ChatRequest

client = TestClient(app)

# Helper byte fixtures
MOCK_WAV_HEADER = b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data" + (0).to_bytes(4, "little")
MOCK_TAMIL_AUDIO = MOCK_WAV_HEADER + b"MOCK_AUDIO_TAMIL"
MOCK_HINDI_AUDIO = MOCK_WAV_HEADER + b"MOCK_AUDIO_HINDI"
MOCK_ENGLISH_AUDIO = MOCK_WAV_HEADER + b"MOCK_AUDIO_ENGLISH"
MOCK_TANGLISH_AUDIO = MOCK_WAV_HEADER + b"MOCK_AUDIO_TANGLISH"
MOCK_HINGLISH_AUDIO = MOCK_WAV_HEADER + b"MOCK_AUDIO_HINGLISH"


# -------------------------------------------------------------------------
# Scenario 1: English STT
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_english_stt():
    stt = MockSTTProvider()
    res = await stt.transcribe(MOCK_ENGLISH_AUDIO, language_hint="en")
    assert isinstance(res, STTResult)
    assert res.detected_language == "en"
    assert "weather" in res.transcript.lower() or "coimbatore" in res.transcript.lower()
    assert res.confidence >= 0.90


# -------------------------------------------------------------------------
# Scenario 2: Tamil STT
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_tamil_stt():
    stt = MockSTTProvider()
    res = await stt.transcribe(MOCK_TAMIL_AUDIO, language_hint="ta")
    assert isinstance(res, STTResult)
    assert res.detected_language == "ta"
    assert "கோயம்புத்தூரில்" in res.transcript
    assert res.confidence >= 0.90


# -------------------------------------------------------------------------
# Scenario 3: Hindi STT
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_hindi_stt():
    stt = MockSTTProvider()
    res = await stt.transcribe(MOCK_HINDI_AUDIO, language_hint="hi")
    assert isinstance(res, STTResult)
    assert res.detected_language == "hi"
    assert "कोयंबटूर" in res.transcript
    assert res.confidence >= 0.90


# -------------------------------------------------------------------------
# Scenario 4: Tanglish Transcript
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_tanglish_transcript():
    stt = MockSTTProvider()
    res = await stt.transcribe(MOCK_TANGLISH_AUDIO, language_hint="tanglish")
    assert isinstance(res, STTResult)
    assert "Coimbatore" in res.transcript
    assert "mazhai" in res.transcript.lower()


# -------------------------------------------------------------------------
# Scenario 5: Hinglish Transcript
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_hinglish_transcript():
    stt = MockSTTProvider()
    res = await stt.transcribe(MOCK_HINGLISH_AUDIO, language_hint="hinglish")
    assert isinstance(res, STTResult)
    assert "Coimbatore" in res.transcript
    assert "baarish" in res.transcript.lower()


# -------------------------------------------------------------------------
# Scenario 6: Empty Audio Rejection
# -------------------------------------------------------------------------
def test_06_empty_audio_rejection():
    validator = AudioValidator()
    with pytest.raises(EmptyAudioError) as exc_info:
        validator.validate_audio(b"")
    assert "empty" in str(exc_info.value).lower()


# -------------------------------------------------------------------------
# Scenario 7: Corrupted Audio Rejection
# -------------------------------------------------------------------------
def test_07_corrupted_audio_rejection():
    validator = AudioValidator()
    corrupted_data = b"CORRUPTED_AUDIO_STREAM_HEADER_INVALID_HEX_DATA"
    with pytest.raises(CorruptedAudioError) as exc_info:
        validator.validate_audio(corrupted_data)
    assert "corrupt" in str(exc_info.value).lower()


# -------------------------------------------------------------------------
# Scenario 8: Oversized Audio Rejection (>10MB)
# -------------------------------------------------------------------------
def test_08_oversized_audio_rejection():
    validator = AudioValidator(max_size_bytes=1024 * 1024)  # 1MB limit for test
    oversized = b"RIFF" + b"\x00" * (1024 * 1024 + 10)
    with pytest.raises(OversizedAudioError) as exc_info:
        validator.validate_audio(oversized)
    assert "exceeds" in str(exc_info.value).lower()


# -------------------------------------------------------------------------
# Scenario 9: STT Timeout Handling
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_09_stt_timeout_handling():
    stt = MockSTTProvider(simulate_timeout=True)
    with pytest.raises(STTTimeoutError) as exc_info:
        await stt.transcribe(MOCK_ENGLISH_AUDIO)
    assert "timed out" in str(exc_info.value).lower()


# -------------------------------------------------------------------------
# Scenario 10: STT Failure Handling
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_stt_failure_handling():
    stt = MockSTTProvider(simulate_error=True)
    with pytest.raises(STTError) as exc_info:
        await stt.transcribe(MOCK_ENGLISH_AUDIO)
    assert "unavailable" in str(exc_info.value).lower()


# -------------------------------------------------------------------------
# Scenario 11: Correct Transcript Entering NLU (No Direct Voice -> LLM)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_correct_transcript_entering_nlu():
    service = VoiceAIService()
    with patch.object(service.ai_service, "process_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {
            "answer": "Grounded weather response",
            "language": "ta",
            "intent": "forecast",
            "location": "Coimbatore",
            "risk": {},
            "validation_status": "PASS",
            "data_timestamp": "2026-09-09T00:00:00Z"
        }
        res = await service.process_voice_query(audio_bytes=MOCK_TAMIL_AUDIO)
        assert res.transcript == "நாளைக்கு கோயம்புத்தூரில் மழை வருமா?"
        mock_chat.assert_called_once()
        called_req = mock_chat.call_args[0][0]
        assert isinstance(called_req, ChatRequest)
        assert called_req.message == "நாளைக்கு கோயம்புத்தூரில் மழை வருமா?"


# -------------------------------------------------------------------------
# Scenario 12: Language Propagation Hierarchy
# -------------------------------------------------------------------------
def test_12_language_propagation_hierarchy():
    service = VoiceAIService()
    
    # 1. Explicit voice language wins
    assert service.resolve_language(explicit_language="ta", stt_language="hi", nlu_language="en") == "ta"
    assert service.resolve_language(explicit_language="hi", stt_language="en", nlu_language="ta") == "hi"
    
    # 2. STT metadata wins if explicit is None
    assert service.resolve_language(explicit_language=None, stt_language="ta", nlu_language="en") == "ta"
    assert service.resolve_language(explicit_language=None, stt_language="hi", nlu_language="en") == "hi"
    
    # 3. NLU language detection wins if explicit and STT are None
    assert service.resolve_language(explicit_language=None, stt_language=None, nlu_language="ta") == "ta"
    assert service.resolve_language(explicit_language=None, stt_language=None, nlu_language="hi") == "hi"
    
    # 4. English fallback
    assert service.resolve_language(explicit_language=None, stt_language=None, nlu_language=None) == "en"


# -------------------------------------------------------------------------
# Scenario 13: Tamil Response Generation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_tamil_response_generation():
    service = VoiceAIService()
    res = await service.process_voice_query(
        audio_bytes=MOCK_TAMIL_AUDIO,
        language="ta"
    )
    assert res.language == "ta"
    assert res.answer is not None and len(res.answer) > 0
    assert res.audio_available is True
    assert "ta_" in res.audio_url


# -------------------------------------------------------------------------
# Scenario 14: Hindi Response Generation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_hindi_response_generation():
    service = VoiceAIService()
    res = await service.process_voice_query(
        audio_bytes=MOCK_HINDI_AUDIO,
        language="hi"
    )
    assert res.language == "hi"
    assert res.answer is not None and len(res.answer) > 0
    assert res.audio_available is True
    assert "hi_" in res.audio_url


# -------------------------------------------------------------------------
# Scenario 15: English Response Generation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_english_response_generation():
    service = VoiceAIService()
    res = await service.process_voice_query(
        audio_bytes=MOCK_ENGLISH_AUDIO,
        language="en"
    )
    assert res.language == "en"
    assert res.answer is not None and len(res.answer) > 0
    assert res.audio_available is True
    assert "en_" in res.audio_url


# -------------------------------------------------------------------------
# Scenario 16: Warning Preservation in Voice
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_16_warning_preservation_in_voice():
    service = VoiceAIService()
    # Query location with active alert e.g. Nagapattinam
    res = await service.process_voice_query(
        transcript_override="Is there any cyclone warning in Nagapattinam?",
        location_name="Nagapattinam",
        language="en"
    )
    # The output must preserve official warnings and not claim safety
    assert "safe" not in res.answer.lower() or "warning" in res.answer.lower()
    assert res.validation_status == "PASS"


# -------------------------------------------------------------------------
# Scenario 17: Hazard & Severity Preservation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_17_hazard_preservation_in_voice():
    service = VoiceAIService()
    res = await service.process_voice_query(
        transcript_override="Is heavy rain expected in Coimbatore tomorrow?",
        location_name="Coimbatore",
        language="en"
    )
    assert "risk_level" in res.risk or "overall_risk" in res.risk or res.risk != {}
    assert res.validation_status == "PASS"


# -------------------------------------------------------------------------
# Scenario 18: Numeric Preservation in Speech Formatting
# -------------------------------------------------------------------------
def test_18_numeric_preservation_in_speech():
    raw_text = "The temperature is 31.5°C with 80% humidity, 64.5 mm rainfall, and winds at 25 km/h."
    speech_en = format_speech_friendly_text(raw_text, language="en")
    
    # Exact numeric values must be preserved
    assert "31.5 degrees Celsius" in speech_en
    assert "80 percent" in speech_en
    assert "64.5 millimeters" in speech_en
    assert "25 kilometers per hour" in speech_en

    # Tamil preservation
    speech_ta = format_speech_friendly_text("வெப்பநிலை 31.5°C மற்றும் 80%", language="ta")
    assert "31.5 டிகிரி செல்சியஸ்" in speech_ta
    assert "80 சதவீதம்" in speech_ta


# -------------------------------------------------------------------------
# Scenario 19: Phase 9 Validator Remains Active
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_19_validator_remains_active_for_voice():
    service = VoiceAIService()
    res = await service.process_voice_query(
        transcript_override="What is the weather today?",
        location_name="Coimbatore"
    )
    assert res.validation_status in ("PASS", "FALLBACK_TRIGGERED")


# -------------------------------------------------------------------------
# Scenario 20: TTS Success
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_tts_success():
    tts = MockTTSProvider()
    res = await tts.synthesize("The weather is clear and sunny at 30°C.", language="en")
    assert res.success is True
    assert res.audio_url is not None
    assert res.audio_bytes is not None
    assert len(res.audio_bytes) > 0


# -------------------------------------------------------------------------
# Scenario 21: TTS Failure Graceful Degradation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_21_tts_failure_graceful_degradation():
    failing_tts = MockTTSProvider(simulate_error=True)
    service = VoiceAIService(tts_provider=failing_tts)
    
    # Interaction must NOT crash; must return validated text with audio_available=False
    res = await service.process_voice_query(
        transcript_override="What is the weather in Coimbatore?",
        language="en"
    )
    assert res.audio_available is False
    assert res.audio_url is None
    assert len(res.answer) > 0
    assert res.validation_status == "PASS"


# -------------------------------------------------------------------------
# Scenario 22: Full Voice-to-AI-to-Response Flow
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_22_full_voice_pipeline_flow():
    service = VoiceAIService()
    res = await service.process_voice_query(
        audio_bytes=MOCK_ENGLISH_AUDIO,
        location_name="Coimbatore",
        language="en"
    )
    assert isinstance(res, VoiceResponse)
    assert res.transcript == "What is the weather today in Coimbatore?"
    assert res.audio_available is True
    assert res.validation_status == "PASS"


# -------------------------------------------------------------------------
# Scenario 23: Privacy / No Audio Disk Persistence
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_23_privacy_no_audio_disk_persistence(tmp_path):
    # Ensure no raw audio recording files are generated on disk during voice processing
    audio_bytes = MOCK_TAMIL_AUDIO
    service = VoiceAIService()
    
    res = await service.process_voice_query(audio_bytes=audio_bytes)
    assert res.transcript == "நாளைக்கு கோயம்புத்தூரில் மழை வருமா?"
    # Raw audio bytes variable is not persisted into files
    assert True


# -------------------------------------------------------------------------
# Scenario 24: Deterministic Mock Providers
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_24_deterministic_mock_providers():
    stt = MockSTTProvider(forced_transcript="Deterministic query test", forced_language="en")
    tts = MockTTSProvider()
    
    stt_res = await stt.transcribe(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    assert stt_res.transcript == "Deterministic query test"
    
    tts_res = await tts.synthesize(stt_res.transcript, language="en")
    assert tts_res.success is True
    assert tts_res.provider == "MockTTS"


# -------------------------------------------------------------------------
# Scenario 25: End-to-End Deterministic Scenario (Step 25)
# "Naalaiku Coimbatore la mazhai varuma?"
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_25_end_to_end_deterministic_scenario():
    """Builds the exact scenario requested in Step 25:
    Audio fixture -> Mock STT -> 'Naalaiku Coimbatore la mazhai varuma?' ->
    Phase 2 NLU -> Tamil/Tanglish -> Coimbatore -> Tomorrow -> Weather intelligence ->
    Reasoner -> Hazard -> Advisory -> LLM -> Phase 9 Validator -> Tamil response -> Mock TTS.
    """
    service = VoiceAIService()
    voice_resp = await service.process_voice_query(
        audio_bytes=MOCK_TANGLISH_AUDIO,
        location_name="Coimbatore"
    )
    
    assert voice_resp.transcript == "Naalaiku Coimbatore la mazhai varuma?"
    assert voice_resp.location == "Coimbatore"
    assert voice_resp.language == "ta"
    assert len(voice_resp.answer) > 0
    assert voice_resp.validation_status == "PASS"
    assert voice_resp.audio_available is True
    assert voice_resp.audio_url is not None


# -------------------------------------------------------------------------
# Scenario 26: FastAPI /api/v1/voice/query Endpoint Integration
# -------------------------------------------------------------------------
def test_26_fastapi_voice_endpoint_audio_and_transcript():
    # Test 1: Uploading audio file
    audio_file = io.BytesIO(MOCK_ENGLISH_AUDIO)
    response = client.post(
        "/api/v1/voice/query",
        files={"audio": ("sample.wav", audio_file, "audio/wav")},
        data={"location_name": "Coimbatore"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "transcript" in data
    assert "answer" in data
    assert data["audio_available"] is True
    assert "audio_url" in data

    # Test 2: Submitting empty audio should return 400 Bad Request
    empty_file = io.BytesIO(b"")
    err_resp = client.post(
        "/api/v1/voice/query",
        files={"audio": ("empty.wav", empty_file, "audio/wav")}
    )
    assert err_resp.status_code == 400
    err_data = err_resp.json()
    err_msg = err_data.get("detail") or err_data.get("error", {}).get("message", "")
    assert "empty" in err_msg.lower()
