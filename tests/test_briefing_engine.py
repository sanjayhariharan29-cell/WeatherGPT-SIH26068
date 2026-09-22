"""Automated tests for Skizen Personalized Weather SMS Briefing Engine (Phase 1)."""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.briefing_service import PersonalizedBriefingService
from backend.schemas.briefing import PersonalizedBriefingResponse


@pytest.fixture
def briefing_service():
    return PersonalizedBriefingService()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_fisherman_briefing(briefing_service):
    """Verifies fisherman briefing generation, character length, and non-directive advice."""
    res = await briefing_service.generate_personalized_briefing(
        override_role="fisherman",
        override_location="Chennai",
        override_language="en",
        override_phone="+919840112233"
    )
    assert isinstance(res, PersonalizedBriefingResponse)
    assert res.role == "fisherman"
    assert res.character_count <= 320
    assert "Skizen" in res.risk_status_label
    assert "(Skizen)" in res.message_text

    # Safety: Non-directive guidance check
    lower = res.message_text.lower()
    assert "you can go" not in lower
    assert "you cannot go" not in lower
    assert "don't go" not in lower
    assert "official" in lower or "advisory" in lower or "imd" in lower

    # Reasoning bullets
    assert len(res.reasoning_bullets) >= 2
    assert any("Fisherman" in b for b in res.reasoning_bullets)


@pytest.mark.asyncio
async def test_farmer_briefing(briefing_service):
    """Verifies farmer briefing generation, Agromet reference, and character limit."""
    res = await briefing_service.generate_personalized_briefing(
        override_role="farmer",
        override_location="Coimbatore",
        override_language="en",
        override_phone="+919840223344"
    )
    assert res.role == "farmer"
    assert res.character_count <= 320
    assert "Agromet" in res.message_text
    assert len(res.reasoning_bullets) >= 2


@pytest.mark.asyncio
async def test_commuter_briefing(briefing_service):
    """Verifies commuter briefing generation and traffic police reference."""
    res = await briefing_service.generate_personalized_briefing(
        override_role="commuter",
        override_location="Madurai",
        override_language="en",
        override_phone="+919840334455"
    )
    assert res.role == "commuter"
    assert res.character_count <= 320
    assert "traffic" in res.message_text.lower() or "imd" in res.message_text.lower()


@pytest.mark.asyncio
async def test_last_known_location_flag(briefing_service):
    """Verifies explicit (Last known) tagging when GPS coordinates are unavailable."""
    res = await briefing_service.generate_personalized_briefing(
        override_role="commuter",
        override_location="Tirunelveli",
        override_language="en",
        is_last_known_override=True
    )
    assert res.is_last_known_location is True
    assert "(Last known)" in res.message_text


@pytest.mark.asyncio
async def test_multilingual_tamil_hindi(briefing_service):
    """Verifies Tamil and Hindi briefing generation adheres to character limit."""
    res_ta = await briefing_service.generate_personalized_briefing(
        override_role="farmer",
        override_location="Coimbatore",
        override_language="ta"
    )
    assert res_ta.language == "ta"
    assert res_ta.character_count <= 320
    assert "Skizen" in res_ta.risk_status_label

    res_hi = await briefing_service.generate_personalized_briefing(
        override_role="farmer",
        override_location="Coimbatore",
        override_language="hi"
    )
    assert res_hi.language == "hi"
    assert res_hi.character_count <= 320
    assert "Skizen" in res_hi.risk_status_label


def test_briefing_api_post_test(client):
    """Verifies debug endpoint POST /api/v1/briefing/test."""
    payload = {
        "role": "fisherman",
        "location_name": "Chennai",
        "language": "en",
        "phone_number": "+919876543210"
    }
    resp = client.post("/api/v1/briefing/test", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "fisherman"
    assert data["character_count"] <= 320
    assert "message_text" in data
    assert "reasoning_bullets" in data
    assert "raw_weather" in data
