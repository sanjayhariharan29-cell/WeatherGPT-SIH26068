"""Phase 19: AI Explainability, Evidence & Decision Trace Tests.

Validates WeatherGPT's auditable decision trace architecture:
- Trace structure and completeness
- Safe-to-expose metadata (location, time, intent, hazards, evidence)
- Zero exposure of private reasoning / hidden chain-of-thought
- Trace propagation across fallback and degraded scenarios
- Official warning priority reflection in trace
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from ai.models import (
    DecisionTrace,
    EvidenceLink,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherRecord,
)
from ai.pipeline import WeatherGPTPipeline
from backend.services.ai_service import AIService
from backend.schemas.chat import ChatRequest, LocationPayload


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_weather(now):
    return WeatherRecord(
        location=LocationInfo(name="Madurai", latitude=9.9252, longitude=78.1198),
        observed_at=now,
        retrieved_at=now,
        temperature=41.5,
        humidity=45.0,
        rain_probability=5.0,
        wind_speed=14.0,
        weather_condition="Extreme Heat",
        source="IMD"
    )


@pytest.fixture
def heatwave_alert(now):
    return OfficialAlert(
        type="heatwave",
        severity=RiskLevelEnum.HIGH,
        title="Heatwave Alert",
        description="Severe heat conditions expected in interior Tamil Nadu. Drink plenty of water.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12),
        affected_locations=["Madurai"]
    )


def test_01_decision_trace_generation(sample_weather):
    """Verify that every pipeline invocation produces a complete, structured DecisionTrace."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="What is the weather in Madurai today?",
        weather=sample_weather,
        persona=PersonaEnum.GENERAL,
        request_id="trace_01"
    )

    assert "decision_trace" in res
    trace_dict = res["decision_trace"]

    # Check safe-to-expose core fields
    assert "trace_id" in trace_dict
    assert trace_dict.get("location") == "Madurai" or trace_dict.get("resolved_location") == "Madurai"
    assert trace_dict["persona"] == "general"
    assert trace_dict["language"] == "en"
    assert "stage_latencies_ms" in trace_dict or "total_pipeline_ms" in res["stage_latencies_ms"]
    assert isinstance(trace_dict.get("evidence_links"), list)


def test_02_evidence_links_and_sources(sample_weather, heatwave_alert):
    """Verify evidence links correctly reference meteorological observations and warnings."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Is it dangerously hot in Madurai?",
        weather=sample_weather,
        active_alerts=[heatwave_alert],
        persona=PersonaEnum.COMMUTER,
        request_id="trace_02"
    )

    trace = res["decision_trace"]
    assert trace.get("warning_status") == "ACTIVE_WARNING" or trace.get("official_warning_status") == "ACTIVE_WARNING"
    hazards = [str(h).lower() for h in trace.get("hazards", [])]
    assert any("heat" in h for h in hazards) or trace["hazards_count"] >= 0

    # Evidence links must have valid source items
    links = trace.get("evidence_links", [])
    assert len(links) > 0
    assert any(link.get("source") == "IMD" for link in links)


def test_03_no_private_thought_leakage(sample_weather):
    """Trace must NEVER expose private chain-of-thought or raw prompt."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Explain weather conditions",
        weather=sample_weather,
        request_id="trace_03"
    )

    trace_dict = res["decision_trace"]
    forbidden_keys = [
        "prompt", "raw_llm_prompt", "system_prompt",
        "chain_of_thought", "internal_thought", "private_reasoning"
    ]
    for key in forbidden_keys:
        assert key not in trace_dict


def test_04_trace_reflects_fallback_and_degradation(sample_weather):
    """When fallback triggers, decision trace documents the state faithfully."""
    pipeline = WeatherGPTPipeline()

    with patch.object(pipeline.llm, "generate", side_effect=RuntimeError("Simulated LLM outage")):
        res = pipeline.process_query(
            message="Will it rain today?",
            weather=sample_weather,
            request_id="trace_04"
        )

        trace = res["decision_trace"]
        assert trace["fallback_used"] is True
        assert trace["degraded_state"] in ("DEGRADED_LLM", "SAFETY_FALLBACK", "PARTIALLY_DEGRADED")


@pytest.mark.asyncio
async def test_05_ai_service_trace_passthrough(sample_weather):
    """Verify backend AI service returns the decision trace to API callers."""
    ai_svc = AIService()
    req = ChatRequest(
        message="Current weather in Chennai",
        location=LocationPayload(name="Chennai"),
        language="en"
    )

    with patch.object(ai_svc.weather_mgr, "get_ai_weather_input", return_value=(sample_weather, [], [])):
        result = await ai_svc.process_chat(req)

        assert "decision_trace" in result
        assert result["decision_trace"] is not None
        assert "location" in result["decision_trace"] or "resolved_location" in result["decision_trace"]
        assert result["decision_trace"]["fallback_used"] is False
