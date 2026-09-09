"""Phase 19: AI Explainability, Evidence & Decision Trace Tests.

Validates WeatherGPT's auditable decision trace architecture:
1. Normal trace completeness (all fields present and populated)
2. Official warning trace (ACTIVE_WARNING, details, alert evidence link)
3. Severe hazard trace (high/severe risk, hazard rule evidence link)
4. Multi-hazard trace (multiple concurrent hazards and rules)
5. Multilingual trace (Hindi / Tamil localization in trace)
6. Stale data trace (STALE / EXPIRED freshness state)
7. Missing data trace (data_completeness False and missing fields)
8. Source conflict trace (CONFLICT / LOW agreement and consistency score)
9. Memory resolved trace (contextual antecedent entity / location resolution)
10. LLM fallback trace (fallback_used True and DEGRADED_LLM state)
11. Validator rejection trace (FALLBACK_SUBSTITUTED and violation category)
12. Degraded subsystem trace (degraded_subsystems and degradation_reason)
13. Privacy and secret audit (zero leaked prompts, CoT, or credentials)
14. Deterministic trace invariance (identical inputs produce identical traces)
15. Backend API passthrough (AIService returns complete trace to API callers)
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from ai.models import (
    DecisionTrace,
    EvidenceLink,
    ForecastItem,
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
        title="Heatwave Warning",
        description="Severe heat conditions expected in interior Tamil Nadu. Stay indoors during afternoon.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12),
        affected_locations=["Madurai"]
    )


def test_01_normal_trace(sample_weather):
    """1. Verify that standard query produces a complete, valid, structured DecisionTrace."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="What is the weather in Madurai today?",
        weather=sample_weather,
        persona=PersonaEnum.GENERAL,
        request_id="trace_01_norm"
    )

    assert "decision_trace" in res
    assert "decision_trace_model" in res
    trace = res["decision_trace"]
    model: DecisionTrace = res["decision_trace_model"]

    assert isinstance(model, DecisionTrace)
    assert trace["trace_id"].startswith("dt_")
    assert trace["location"] == "Madurai"
    assert trace["resolved_location"] == "Madurai"
    assert trace["persona"] == "general"
    assert trace["language"] == "en"
    assert trace["data_freshness"].lower() == "fresh"
    assert trace["data_completeness"] is True
    assert trace["source_agreement"].lower() in ("consistent", "single_source")
    assert trace["consistency_score"] >= 80
    assert trace["warning_status"].upper() == "NONE"
    assert trace["warning_count"] == 0
    assert trace["fallback_used"] is False
    assert trace["degraded_state"].upper() == "NORMAL"
    assert trace["final_status"].upper() == "VALIDATED"
    assert isinstance(trace["stage_latencies_ms"], dict)
    assert trace["evidence_links_count"] >= 3

    # Check evidence links schema
    for link in trace["evidence_links"]:
        assert "field_or_entity" in link
        assert "observed_or_rule_value" in link
        assert "source" in link
        assert "temporal_scope" in link
        assert "decision_impact" in link
        assert "reason_code" in link
        assert "reference_type" in link


def test_02_official_warning_trace(sample_weather, heatwave_alert):
    """2. Verify that active official warning populates warning status and alert evidence links."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Is there any heat warning for Madurai?",
        weather=sample_weather,
        active_alerts=[heatwave_alert],
        persona=PersonaEnum.COMMUTER,
        request_id="trace_02_warn"
    )

    trace = res["decision_trace"]
    assert trace["warning_status"].upper() == "ACTIVE_WARNING"
    assert trace["official_warning_status"].upper() == "ACTIVE_WARNING"
    assert trace["warning_count"] == 1
    assert trace["warning_details"] is not None
    assert trace["warning_details"]["warning_type"] == "heatwave"
    assert trace["warning_details"]["severity"].lower() == "high"
    assert trace["warning_details"]["source"] == "IMD"

    # Evidence links must contain alert reference
    alert_links = [l for l in trace["evidence_links"] if l.get("reference_type") == "alert"]
    assert len(alert_links) >= 1
    assert alert_links[0]["reason_code"] == "OFFICIAL_WARNING"
    assert "warning.heatwave" in alert_links[0]["field_or_entity"]


def test_03_severe_hazard_trace(now):
    """3. Verify severe meteorological hazard triggers high risk and hazard rule evidence link."""
    pipeline = WeatherGPTPipeline()
    severe_weather = WeatherRecord(
        location=LocationInfo(name="Madurai", latitude=9.9252, longitude=78.1198),
        observed_at=now,
        retrieved_at=now,
        temperature=44.5,
        humidity=40.0,
        rain_probability=0.0,
        wind_speed=15.0,
        weather_condition="Severe Heatwave",
        source="IMD"
    )

    res = pipeline.process_query(
        message="Is it dangerous outside in Madurai?",
        weather=severe_weather,
        persona=PersonaEnum.FARMER,
        request_id="trace_03_sev"
    )

    trace = res["decision_trace"]
    assert trace["overall_risk"] in ("high", "severe")
    assert trace["hazards_count"] >= 1

    hazard_links = [l for l in trace["evidence_links"] if l.get("reference_type") == "hazard_rule"]
    assert len(hazard_links) >= 1
    assert any("HAZARD_" in l.get("reason_code", "") for l in hazard_links)
    assert any(l.get("source") == "WeatherReasoner.HazardEngine" for l in hazard_links)


def test_04_multi_hazard_trace(now):
    """4. Verify multi-hazard condition tracks all active hazards and rules in trace."""
    pipeline = WeatherGPTPipeline()
    multi_hazard_weather = WeatherRecord(
        location=LocationInfo(name="Chennai", latitude=13.0827, longitude=80.2707),
        observed_at=now,
        retrieved_at=now,
        temperature=42.0,
        humidity=85.0,
        rain_probability=90.0,
        wind_speed=65.0,
        weather_condition="Severe Squall and Storm",
        source="IMD"
    )

    res = pipeline.process_query(
        message="Can I go outside in Chennai right now?",
        weather=multi_hazard_weather,
        persona=PersonaEnum.COMMUTER,
        request_id="trace_04_multi"
    )

    trace = res["decision_trace"]
    assert trace["hazards_count"] >= 2
    hazard_names = [h.get("hazard_type") for h in trace["hazards"]]
    assert len(hazard_names) >= 2

    # Multiple hazard rule evidence links
    hazard_links = [l for l in trace["evidence_links"] if l.get("reference_type") == "hazard_rule"]
    assert len(hazard_links) >= 2


def test_05_multilingual_trace(sample_weather):
    """5. Verify multilingual queries in Hindi and Tamil preserve language metadata in trace."""
    pipeline = WeatherGPTPipeline()

    # Hindi query
    res_hi = pipeline.process_query(
        message="मदुरै में आज मौसम कैसा है?",
        weather=sample_weather,
        request_id="trace_05_hi"
    )
    assert res_hi["decision_trace"]["language"] == "hi"
    assert res_hi["language"] == "hi"

    # Tamil query
    res_ta = pipeline.process_query(
        message="மதுரையில் இன்று வானிலை எப்படி இருக்கிறது?",
        weather=sample_weather,
        request_id="trace_05_ta"
    )
    assert res_ta["decision_trace"]["language"] == "ta"
    assert res_ta["language"] == "ta"


def test_06_stale_data_trace(now):
    """6. Verify stale weather data reflects in trace freshness and timestamps."""
    pipeline = WeatherGPTPipeline()
    old_time = now - timedelta(hours=6)
    stale_weather = WeatherRecord(
        location=LocationInfo(name="Trichy", latitude=10.7905, longitude=78.7047),
        observed_at=old_time,
        retrieved_at=old_time,
        temperature=32.0,
        humidity=60.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Cloudy",
        source="IMD"
    )

    res = pipeline.process_query(
        message="Current weather in Trichy",
        weather=stale_weather,
        request_id="trace_06_stale"
    )

    trace = res["decision_trace"]
    assert trace["data_freshness"].lower() in ("stale", "expired")
    obs_links = [l for l in trace["evidence_links"] if l.get("reference_type") == "observation"]
    assert len(obs_links) > 0
    assert old_time.isoformat() in obs_links[0]["timestamp"]


def test_07_missing_data_trace():
    """7. Verify missing weather data triggers data_completeness False in decision trace."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="What is the weather in Salem?",
        weather=None,
        request_id="trace_07_incomplete"
    )

    trace = res["decision_trace"]
    assert trace["data_completeness"] is False
    assert res["data_quality"]["data_complete"] is False
    assert len(res["data_quality"]["missing_fields"]) > 0


def test_08_source_conflict_trace(now):
    """8. Verify conflicting multi-source readings degrade source agreement and consistency score."""
    pipeline = WeatherGPTPipeline()
    primary = WeatherRecord(
        location=LocationInfo(name="Vellore", latitude=12.9165, longitude=79.1325),
        observed_at=now,
        retrieved_at=now,
        temperature=25.0,
        humidity=80.0,
        rain_probability=80.0,
        wind_speed=10.0,
        weather_condition="Heavy Rain",
        source="IMD"
    )
    secondary = WeatherRecord(
        location=LocationInfo(name="Vellore", latitude=12.9165, longitude=79.1325),
        observed_at=now,
        retrieved_at=now,
        temperature=39.0,
        humidity=30.0,
        rain_probability=0.0,
        wind_speed=12.0,
        weather_condition="Dry Heat",
        source="OpenMeteo"
    )

    res = pipeline.process_query(
        message="Weather in Vellore?",
        weather=primary,
        secondary_weather=secondary,
        request_id="trace_08_conflict"
    )

    trace = res["decision_trace"]
    assert trace["source_agreement"].lower() in ("low", "conflict", "divergent")
    assert trace["consistency_score"] < 80


def test_09_memory_resolved_trace(now, sample_weather):
    """9. Verify contextual antecedent entity resolution from conversation memory appears in trace."""
    pipeline = WeatherGPTPipeline()
    from ai.memory import memory_manager

    conv_id = "trace_conv_test_09"
    memory_manager.update_context(conversation_id=conv_id, location="Coimbatore")

    res = pipeline.process_query(
        message="Will it rain there today?",
        weather=sample_weather,
        conversation_id=conv_id,
        request_id="trace_09_mem"
    )

    trace = res["decision_trace"]
    assert trace["trace_id"].startswith("dt_")
    mem_links = [l for l in trace["evidence_links"] if l.get("source") == "ConversationMemory"]
    assert len(mem_links) >= 1
    assert mem_links[0]["reason_code"] == "CONVERSATION_MEMORY_RESOLVED"


def test_10_llm_fallback_trace(sample_weather):
    """10. Verify LLM outage records fallback_used True and DEGRADED_LLM state in trace."""
    pipeline = WeatherGPTPipeline()

    with patch.object(pipeline.llm, "generate", side_effect=RuntimeError("Simulated LLM network timeout")):
        res = pipeline.process_query(
            message="Will it rain in Madurai today?",
            weather=sample_weather,
            request_id="trace_10_fb"
        )

        trace = res["decision_trace"]
        assert trace["fallback_used"] is True
        assert trace["degraded_state"] == "DEGRADED_LLM"
        assert trace["final_status"] in ("VALIDATED", "FALLBACK_SUBSTITUTED")
        assert len(res["answer"]) > 0


def test_11_validator_rejection_trace(sample_weather):
    """11. Verify validator rejection flags violation category and FALLBACK_SUBSTITUTED status."""
    pipeline = WeatherGPTPipeline()

    # Hallucinated answer with unsupported numbers and fabricated weather
    hallucinated_text = (
        "The current temperature in Madurai is 95°C with boiling acid rain and hurricane wind speeds of 300 km/h. "
        "NASA has issued an evacuation order."
    )

    with patch.object(pipeline.llm, "generate", return_value=hallucinated_text):
        res = pipeline.process_query(
            message="What is the weather in Madurai?",
            weather=sample_weather,
            request_id="trace_11_rej"
        )

        trace = res["decision_trace"]
        assert trace["fallback_used"] is True
        assert trace["final_status"] == "FALLBACK_SUBSTITUTED"
        assert trace["violation_category"] is not None
        assert len(trace["violation_category"]) > 0
        assert res["validation"]["passed"] is False


def test_12_degraded_subsystem_trace(sample_weather):
    """12. Verify subsystem failures record degraded_subsystems and degradation_reason."""
    pipeline = WeatherGPTPipeline()

    with patch("ai.pipeline.retrieve_safety_guidance", side_effect=Exception("RAG database unavailable")):
        res = pipeline.process_query(
            message="Is it safe to walk outside in Madurai?",
            weather=sample_weather,
            request_id="trace_12_subsys"
        )

        trace = res["decision_trace"]
        assert "rag" in trace["degraded_subsystems"]
        assert trace["degradation_reason"] is not None
        assert "rag" in trace["degradation_reason"].lower()


def test_13_privacy_no_secret_leakage(sample_weather):
    """13. Comprehensive privacy audit: verify trace NEVER leaks hidden CoT, prompts, or secrets."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="Provide a complete analysis of weather in Madurai",
        weather=sample_weather,
        request_id="trace_13_priv"
    )

    trace = res["decision_trace"]
    trace_json = json.dumps(trace).lower()

    forbidden_patterns = [
        "prompt",
        "raw_llm_prompt",
        "system_prompt",
        "chain_of_thought",
        "internal_thought",
        "private_reasoning",
        "api_key",
        "secret",
        "bearer ",
        "authorization",
    ]

    for pattern in forbidden_patterns:
        # Check dictionary keys
        assert pattern not in trace, f"Forbidden key '{pattern}' leaked in trace keys!"
        # Check stringified JSON (key names or text)
        assert f'"{pattern}"' not in trace_json, f"Forbidden pattern '{pattern}' leaked in trace JSON!"

    # Ensure evidence links only contain public telemetry or official rule identifiers
    for link in trace["evidence_links"]:
        assert link["source"] in ("IMD", "OpenMeteo", "WeatherReasoner.HazardEngine", "AdvisoryEngine", "ConversationMemory")


def test_14_deterministic_trace_invariance(sample_weather, heatwave_alert):
    """14. Invariance check: identical meteorological inputs yield identical deterministic trace metadata."""
    pipeline = WeatherGPTPipeline()

    res1 = pipeline.process_query(
        message="What is the forecast in Madurai?",
        weather=sample_weather,
        active_alerts=[heatwave_alert],
        persona=PersonaEnum.FARMER,
        request_id="trace_14_inv_1"
    )

    res2 = pipeline.process_query(
        message="What is the forecast in Madurai?",
        weather=sample_weather,
        active_alerts=[heatwave_alert],
        persona=PersonaEnum.FARMER,
        request_id="trace_14_inv_2"
    )

    t1 = res1["decision_trace"]
    t2 = res2["decision_trace"]

    # Deterministic invariants must match 100%
    deterministic_fields = [
        "resolved_location",
        "detected_intent",
        "persona",
        "language",
        "data_freshness",
        "data_completeness",
        "source_agreement",
        "consistency_score",
        "warning_status",
        "warning_count",
        "overall_risk",
        "advisory_category",
        "advisory_priority",
        "action_class",
        "validation_status",
        "fallback_used",
        "degraded_state",
        "evidence_links_count",
    ]

    for field in deterministic_fields:
        assert t1[field] == t2[field], f"Deterministic field mismatch for '{field}': {t1[field]} vs {t2[field]}"


@pytest.mark.asyncio
async def test_15_backend_api_passthrough(sample_weather):
    """15. Verify AIService passes the complete decision trace to callers in the API payload."""
    ai_svc = AIService()
    req = ChatRequest(
        message="Current weather in Madurai",
        location=LocationPayload(name="Madurai"),
        language="en"
    )

    with patch.object(ai_svc.weather_mgr, "get_ai_weather_input", return_value=(sample_weather, [], [])):
        result = await ai_svc.process_chat(req)

        assert "decision_trace" in result
        trace = result["decision_trace"]
        assert trace is not None
        assert "trace_id" in trace
        assert trace["resolved_location"] == "Madurai"
        assert "evidence_links" in trace
        assert isinstance(trace["evidence_links"], list)
        assert trace["fallback_used"] is False
        assert trace["final_status"] == "VALIDATED"
