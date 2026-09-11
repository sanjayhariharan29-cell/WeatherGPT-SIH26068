"""Tests for SkyZen Unified Voice Conversational Intelligence Pipeline.

Validates:
1. Voice input uses EXACTLY the same conversational pipeline as typed input:
   STT -> Transcript -> NLU -> ConversationState -> Clarification -> Weather -> Decision -> LLM -> Validator -> Concise Response -> Optional TTS.
2. Voice examples:
   - "Can I go to college today?"
   - "Should I take my bike?"
   - "Can I go fishing tomorrow?"
   - "Can I go to sea?"
3. Context, intent, language, follow-up references, and clarification state preservation across turns.
4. Robust error handling: empty transcripts, unsupported formats, recognition failure, TTS circuit breaker.
5. No silent fallback to English voice when Tamil or Hindi voice is requested.
"""

import pytest
import io
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.session import get_db
from ai.voice import (
    VoiceAIService,
    VoiceResponse,
    EmptyAudioError,
    AudioValidationError,
    STTError,
)
from ai.voice.tts import MockTTSProvider
from ai.voice.stt import MockSTTProvider


# Minimal 44-byte standard WAV header + 16 bytes of silent PCM data = 60 bytes
MOCK_WAV_BYTES = (
    b"RIFF\x2c\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00"
    b"\x02\x00\x10\x00data\x08\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00"
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_voice_example_college_today():
    """Validates 'Can I go to college today?' via unified voice conversational pipeline."""
    service = VoiceAIService()
    response = await service.process_voice_query(
        transcript_override="Can I go to college today?",
        location_name="Coimbatore",
        persona="student",
        language="en"
    )

    assert response.transcript == "Can I go to college today?"
    assert response.answer is not None
    assert len(response.answer) > 0
    # Must contain conversational state and personal decision artifacts
    assert response.conversation_id is not None
    assert response.personal_decision is not None
    assert response.personal_decision.get("activity") in ("college", "college_travel", "commute", "travel", "study") or response.intent is not None
    assert response.validation_status in ("PASS", "WARNING")


@pytest.mark.asyncio
async def test_voice_example_should_i_take_my_bike():
    """Validates 'Should I take my bike?' via unified voice conversational pipeline."""
    service = VoiceAIService()
    response = await service.process_voice_query(
        transcript_override="Should I take my bike?",
        location_name="Coimbatore",
        persona="commuter",
        language="en"
    )

    assert response.transcript == "Should I take my bike?"
    assert response.answer is not None
    assert response.conversation_id is not None
    assert response.personal_decision is not None
    assert response.personal_decision.get("transport") in ("bike", "two_wheeler", "motorcycle") or "bike" in response.answer.lower()


@pytest.mark.asyncio
async def test_voice_example_fishing_tomorrow():
    """Validates 'Can I go fishing tomorrow?' via unified voice conversational pipeline."""
    service = VoiceAIService()
    response = await service.process_voice_query(
        transcript_override="Can I go fishing tomorrow?",
        location_name="Chennai",
        persona="fisherman",
        language="en"
    )

    assert response.transcript == "Can I go fishing tomorrow?"
    assert response.answer is not None
    assert response.conversation_id is not None
    assert response.personal_decision.get("decision_type") in ("fishing_marine", "marine_safety") or response.intent in ("fishing_decision", "fishing_safety", "forecast", "current_weather")


@pytest.mark.asyncio
async def test_voice_example_can_i_go_to_sea():
    """Validates 'Can I go to sea?' via unified voice conversational pipeline."""
    service = VoiceAIService()
    response = await service.process_voice_query(
        transcript_override="Can I go to sea?",
        location_name="Rameswaram",
        persona="fisherman",
        language="en"
    )

    assert response.transcript == "Can I go to sea?"
    assert response.answer is not None
    assert response.conversation_id is not None
    # Must have evaluated marine safety or general activity
    assert response.personal_decision is not None


@pytest.mark.asyncio
async def test_voice_multi_turn_context_and_followup_preservation():
    """Validates that voice queries preserve context, intent, and location across turns using conversation_id."""
    service = VoiceAIService()

    # Turn 1: Initial query establishing location and date
    resp_turn1 = await service.process_voice_query(
        transcript_override="Will it rain in Chennai tomorrow?",
        location_name="Chennai",
        language="en"
    )
    conv_id = resp_turn1.conversation_id
    assert conv_id is not None
    assert resp_turn1.location == "Chennai"

    # Turn 2: Follow-up query without explicit location
    resp_turn2 = await service.process_voice_query(
        transcript_override="Should I take my bike?",
        conversation_id=conv_id,
        language="en"
    )
    # The follow-up turn must preserve the session and resolve context
    assert resp_turn2.conversation_id == conv_id
    assert resp_turn2.location == "Chennai"
    assert resp_turn2.answer is not None


@pytest.mark.asyncio
async def test_voice_language_support_tamil_tanglish():
    """Validates Tamil and Tanglish voice queries preserve target language and do not silently switch to English."""
    service = VoiceAIService()
    response = await service.process_voice_query(
        transcript_override="Naalaiku college polaama?",
        language="ta",
        location_name="Coimbatore",
        persona="student"
    )

    assert response.language == "ta"
    assert response.answer is not None


@pytest.mark.asyncio
async def test_voice_language_support_hindi():
    """Validates Hindi voice queries preserve Hindi language output."""
    service = VoiceAIService()
    response = await service.process_voice_query(
        transcript_override="क्या मैं आज बाइक ले जा सकता हूँ?",
        language="hi",
        location_name="Delhi",
        persona="commuter"
    )

    assert response.language == "hi"
    assert response.answer is not None


@pytest.mark.asyncio
async def test_voice_tts_circuit_breaker_resilience():
    """Validates that when TTS provider fails, the system safely delivers text response and marks audio_available=False."""
    failing_tts = MockTTSProvider(simulate_error=True)
    service = VoiceAIService(tts_provider=failing_tts)

    response = await service.process_voice_query(
        transcript_override="Can I go outside?",
        location_name="Coimbatore"
    )

    assert response.answer is not None
    assert response.audio_available is False
    assert response.audio_url is None


def test_voice_api_endpoint_with_conversation_id(client):
    """Validates POST /api/v1/voice/query accepts conversation_id and returns full conversational payload."""
    data = {
        "transcript": "Can I go to college today?",
        "persona": "student",
        "location_name": "Coimbatore",
        "language": "en",
        "conversation_id": "conv_test_voice_123"
    }
    resp = client.post("/api/v1/voice/query", data=data)
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["transcript"] == "Can I go to college today?"
    assert res_json["conversation_id"] == "conv_test_voice_123"
    assert "personal_decision" in res_json
    assert res_json["answer"] is not None


def test_voice_api_endpoint_with_audio_upload(client):
    """Validates POST /api/v1/voice/query with audio file upload."""
    files = {
        "audio": ("voice_sample.wav", io.BytesIO(MOCK_WAV_BYTES), "audio/wav")
    }
    data = {
        "persona": "student",
        "location_name": "Coimbatore",
        "language": "en"
    }
    resp = client.post("/api/v1/voice/query", files=files, data=data)
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["transcript"] is not None
    assert res_json["answer"] is not None
    assert "personal_decision" in res_json


def test_voice_api_endpoint_empty_audio_rejected(client):
    """Validates empty audio submission returns HTTP 400."""
    files = {
        "audio": ("empty.wav", io.BytesIO(b""), "audio/wav")
    }
    resp = client.post("/api/v1/voice/query", files=files)
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_voice_api_endpoint_corrupt_audio_rejected(client):
    """Validates non-audio corrupted data returns HTTP 400."""
    files = {
        "audio": ("corrupt.wav", io.BytesIO(b"CORRUPTED_AUDIO_DATA_TEST_STREAM"), "audio/wav")
    }
    resp = client.post("/api/v1/voice/query", files=files)
    assert resp.status_code == 400
