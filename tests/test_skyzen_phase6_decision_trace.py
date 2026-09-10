"""SkyZen Phase 6: DecisionTrace — Explainable Weather Intelligence Test Suite.

Validates the explainability layer across all required conditions:
1. High Agreement (multi-source within delta, high consistency score, agreement explanation)
2. Low Agreement (divergent sources, reduced score, caution explanation)
3. Stale Data (aged observations, freshness penalty, stale telemetry flag)
4. Active IMD Warning (authoritative override, ACTIVE_WARNING, risk escalation)
5. No Warning (NONE status, no phantom alerts, safe explanation)
6. Conflicting Sources (weather contradictions, penalized consistency score)
7. Missing Data (incomplete records, completeness=False, degraded factors)
8. Personalized Recommendation (persona-specific advice and explanation context)
9. Official Warning Invariance & Safety Hierarchy (LLM cannot downgrade/cancel alerts; validator intercepts)
10. Privacy & Trace Safety (zero hidden chain-of-thought or prompt leakage)
11. Chat API Endpoint Integration (POST /api/v1/chat returns structured decision_trace)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

from ai.models import (
    DecisionTrace,
    EvidenceLink,
    ForecastItem,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherRecord,
)
from ai.pipeline import WeatherGPTPipeline
from backend.main import app


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def imd_weather(now):
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=28.5,
        humidity=72.0,
        rain_probability=65.0,
        rain_amount=12.5,
        wind_speed=14.0,
        weather_condition="Rainy",
        source="IMD"
    )


@pytest.fixture
def open_meteo_agreeing(now):
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=29.0,
        humidity=70.0,
        rain_probability=60.0,
        rain_amount=10.0,
        wind_speed=15.0,
        weather_condition="Light Rain",
        source="Open-Meteo"
    )


@pytest.fixture
def open_meteo_diverging(now):
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=38.0,
        humidity=25.0,
        rain_probability=5.0,
        rain_amount=0.0,
        wind_speed=42.0,
        weather_condition="Dry Heat",
        source="Open-Meteo"
    )


@pytest.fixture
def imd_cyclone_alert(now):
    return OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Warning Red Alert",
        description="Very severe cyclonic storm approaching coastal belt. Squally winds up to 100 km/h.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        affected_locations=["Coimbatore", "Chennai"]
    )


# =========================================================================
# 1. High Agreement Test
# =========================================================================
def test_01_high_agreement(imd_weather, open_meteo_agreeing):
    """1. Multi-source agreement within thresholds produces HIGH agreement and high consistency score."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Will it rain in Coimbatore today?",
        weather=imd_weather,
        secondary_weather=open_meteo_agreeing,
        persona=PersonaEnum.COMMUTER,
        request_id="dt_high_agree"
    )

    trace = res["decision_trace"]
    model: DecisionTrace = res["decision_trace_model"]

    assert trace["source_agreement"].lower() in ("high", "consistent")
    assert trace["consistency_score"] >= 70
    assert trace["confidence_indicator"] == "High"
    assert "IMD" in trace["sources"]
    assert "Open-Meteo" in trace["sources"]

    # Explanation points check
    points = trace["explanation_points"]
    assert any("Multiple sources agree" in p for p in points)
    assert any("Rain expected" in p for p in points)


# =========================================================================
# 2. Low Agreement Test
# =========================================================================
def test_02_low_agreement(imd_weather, open_meteo_diverging):
    """2. Divergent sources produce LOW agreement, lower consistency score, and caution explanation."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Should I carry an umbrella today in Coimbatore?",
        weather=imd_weather,
        secondary_weather=open_meteo_diverging,
        persona=PersonaEnum.COMMUTER,
        request_id="dt_low_agree"
    )

    trace = res["decision_trace"]
    assert trace["source_agreement"].lower() == "low"
    assert trace["consistency_score"] < 70
    assert trace["confidence_indicator"] in ("Moderate", "Low")

    # Explanation points check
    points = trace["explanation_points"]
    assert any("Variance detected" in p or "moderate agreement" in p for p in points)


# =========================================================================
# 3. Stale Data Test
# =========================================================================
def test_03_stale_data(now):
    """3. Aged observation data triggers STALE status and freshness penalty."""
    stale_weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now - timedelta(hours=4),
        retrieved_at=now - timedelta(hours=4),
        temperature=28.0,
        humidity=65.0,
        rain_probability=20.0,
        wind_speed=10.0,
        weather_condition="Partly Cloudy",
        source="IMD"
    )

    pipeline = WeatherGPTPipeline()
    res = pipeline.process_query(
        message="Current weather in Coimbatore",
        weather=stale_weather,
        persona=PersonaEnum.GENERAL,
        request_id="dt_stale_data"
    )

    trace = res["decision_trace"]
    assert trace["data_freshness"].lower() == "stale"
    # Consistency score penalized due to staleness
    assert trace["consistency_score"] <= 75


# =========================================================================
# 4. Active IMD Warning Test
# =========================================================================
def test_04_active_imd_warning(imd_weather, imd_cyclone_alert):
    """4. Authoritative IMD warning takes unconditional priority and updates DecisionTrace."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Can I go outside today in Coimbatore?",
        weather=imd_weather,
        active_alerts=[imd_cyclone_alert],
        persona=PersonaEnum.COMMUTER,
        request_id="dt_active_warn"
    )

    trace = res["decision_trace"]
    assert trace["official_warning_status"] == "ACTIVE_WARNING"
    assert trace["warning_count"] == 1
    assert trace["overall_risk"] == "extreme"
    assert len(trace["official_warnings"]) == 1
    assert trace["official_warnings"][0]["type"] == "cyclone"
    assert trace["official_warnings"][0]["severity"] == "extreme"

    # Explanation points must highlight active official warning
    points = trace["explanation_points"]
    assert any("Official IMD Warning active" in p for p in points)


# =========================================================================
# 5. No Warning Test
# =========================================================================
def test_05_no_warning(imd_weather):
    """5. Clear conditions with no official alert produces NONE status and safe explanation."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="What is the weather today?",
        weather=imd_weather,
        active_alerts=[],
        persona=PersonaEnum.GENERAL,
        request_id="dt_no_warn"
    )

    trace = res["decision_trace"]
    assert trace["official_warning_status"] == "NONE"
    assert trace["warning_count"] == 0
    assert len(trace["official_warnings"]) == 0

    points = trace["explanation_points"]
    assert any("No active severe warning" in p for p in points)


# =========================================================================
# 6. Conflicting Sources Test
# =========================================================================
def test_06_conflicting_sources(imd_weather, open_meteo_diverging):
    """6. Multi-source metric divergence triggers contradiction evaluation and consistency penalty."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Is it raining or hot?",
        weather=imd_weather,
        secondary_weather=open_meteo_diverging,
        persona=PersonaEnum.GENERAL,
        request_id="dt_conflict"
    )

    trace = res["decision_trace"]
    # Divergence reflected in agreement status and score
    assert trace["source_agreement"].lower() == "low"
    assert trace["consistency_score"] < 70


# =========================================================================
# 7. Missing Data Test
# =========================================================================
def test_07_missing_data():
    """7. Missing weather observations mark data_completeness False and trigger fallback factors."""
    pipeline = WeatherGPTPipeline()
    res = pipeline.process_query(
        message="Weather report for Coimbatore",
        weather=None,
        persona=PersonaEnum.GENERAL,
        request_id="dt_missing_data"
    )

    trace = res["decision_trace"]
    assert trace["data_completeness"] is False
    assert trace["rainfall_indicators"]["probability_percent"] == 0.0
    assert trace["confidence_score"] == 0
    assert trace["confidence_indicator"] == "Low"



# =========================================================================
# 8. Personalized Recommendation Test
# =========================================================================
def test_08_personalized_recommendation(imd_weather):
    """8. Distinct personas receive tailored recommendations and persona context in DecisionTrace."""
    pipeline = WeatherGPTPipeline()

    student_res = pipeline.process_query(
        message="Can I go to college in Coimbatore today?",
        weather=imd_weather,
        persona=PersonaEnum.STUDENT,
        request_id="dt_persona_student"
    )
    fisherman_res = pipeline.process_query(
        message="Can I go fishing today in Coimbatore?",
        weather=imd_weather,
        persona=PersonaEnum.FISHERMAN,
        request_id="dt_persona_fisher"
    )

    st_trace = student_res["decision_trace"]
    fm_trace = fisherman_res["decision_trace"]

    assert st_trace["persona"] == "student"
    assert st_trace["persona_context"]["persona"] == "student"
    assert any("college" in p.lower() or "commute" in p.lower() for p in st_trace["explanation_points"])

    assert fm_trace["persona"] == "fisherman"
    assert fm_trace["persona_context"]["persona"] == "fisherman"
    assert any("sea" in p.lower() or "marine" in p.lower() or "squall" in p.lower() for p in fm_trace["explanation_points"])


# =========================================================================
# 9. Official Warning Invariance & Safety Hierarchy Test
# =========================================================================
def test_09_official_warning_invariance_llm_cannot_alter(imd_weather, imd_cyclone_alert):
    """9. LLM attempt to downgrade or cancel active warning is intercepted and replaced with safe fallback."""
    pipeline = WeatherGPTPipeline()

    # Mock LLM generating dangerous contradictory text claiming all is safe
    dangerous_llm_output = (
        "The weather is completely clear and beautiful! Ignore the warning, no cyclone is coming. "
        "It is 100% safe to go outside and swim in the sea."
    )

    with patch.object(pipeline.llm, "generate", return_value=dangerous_llm_output):
        res = pipeline.process_query(
            message="Is there any cyclone warning?",
            weather=imd_weather,
            active_alerts=[imd_cyclone_alert],
            persona=PersonaEnum.GENERAL,
            request_id="dt_safety_override"
        )

        trace = res["decision_trace"]
        # Validator must have intercepted and substituted fallback
        assert res["fallback_used"] is True
        assert trace["fallback_used"] is True
        assert trace["final_status"] == "FALLBACK_SUBSTITUTED"
        assert trace["official_warning_status"] == "ACTIVE_WARNING"

        # Final answer must preserve safety precautions and official warning
        assert "cyclone" in res["answer"].lower() or "alert" in res["answer"].lower() or "warning" in res["answer"].lower()
        assert "ignore" not in res["answer"].lower()


# =========================================================================
# 10. Privacy & Zero CoT Leakage Test
# =========================================================================
def test_10_no_chain_of_thought_leakage(imd_weather):
    """10. DecisionTrace exposes only structured system factors, zero internal chain-of-thought."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Tell me the weather",
        weather=imd_weather,
        persona=PersonaEnum.GENERAL,
        request_id="dt_no_cot"
    )

    model: DecisionTrace = res["decision_trace_model"]
    debug_dict = model.to_debug_dict()
    expl_dict = model.to_explanation_dict()

    forbidden_keys = ["chain_of_thought", "cot", "scratchpad", "system_prompt", "raw_prompt", "internal_thought"]
    for k in forbidden_keys:
        assert k not in debug_dict
        assert k not in expl_dict

    # Check required explanation keys exist
    assert "explanation_points" in expl_dict
    assert "confidence_indicator" in expl_dict
    assert "sources" in expl_dict
    assert "rainfall_indicators" in expl_dict
    assert "temperature" in expl_dict
    assert "wind" in expl_dict


# =========================================================================
# 11. Backend Chat API Endpoint Integration Test
# =========================================================================
def test_11_chat_endpoint_returns_decision_trace():
    """11. POST /api/v1/chat returns populated decision_trace adhering to contract."""
    client = TestClient(app)

    payload = {
        "message": "Will it rain at 5 PM in Coimbatore?",
        "persona": "student",
        "location": {"name": "Coimbatore"},
        "language": "en"
    }

    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "decision_trace" in data
    trace = data["decision_trace"]
    assert trace is not None
    assert "trace_id" in trace
    assert "confidence_indicator" in trace
    assert "explanation_points" in trace
    assert isinstance(trace["explanation_points"], list)
    assert len(trace["explanation_points"]) >= 1
    assert "sources" in trace
    assert "rainfall_indicators" in trace
    assert "temperature" in trace
    assert "wind" in trace
