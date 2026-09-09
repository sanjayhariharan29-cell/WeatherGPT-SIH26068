"""Phase 16: AI Performance, Reliability & Graceful Degradation Tests.

Tests circuit breakers, timeout enforcement, fallback preservation,
and graceful degradation under external dependency failures.
"""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ai.models import (
    AdvisoryPriorityEnum,
    AdvisoryTypeEnum,
    DegradedStateEnum,
    ForecastItem,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherRecord,
)
from ai.pipeline import WeatherGPTPipeline
from ai.resilience import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    get_circuit_breaker,
    run_with_timeout,
)
from ai.voice.service import VoiceAIService
from ai.voice.tts import MockTTSProvider


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_weather(now):
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=65.0,
        rain_probability=20.0,
        wind_speed=14.0,
        weather_condition="Partly Cloudy",
        source="IMD",
        rainfall_amount_mm=0.0
    )


def test_01_circuit_breaker_state_transitions():
    """Circuit breaker should transition CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    breaker = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=0.2)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.is_open is False

    # First failure
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.consecutive_failures == 1

    # Second failure triggers trip
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.is_open is True

    # Calling should raise CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        breaker.execute(lambda: "should not run")

    # Wait for cooldown to half-open
    time.sleep(0.25)
    assert breaker.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN should reset to CLOSED
    result = breaker.execute(lambda: "recovered")
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.consecutive_failures == 0


def test_02_run_with_timeout():
    """run_with_timeout should return result on time and raise TimeoutError on slow call."""
    def fast_fn():
        return "fast"

    def slow_fn():
        time.sleep(0.3)
        return "slow"

    assert run_with_timeout(fast_fn, timeout_seconds=1.0) == "fast"

    with pytest.raises(TimeoutError):
        run_with_timeout(slow_fn, timeout_seconds=0.1)


def test_03_pipeline_degrades_gracefully_on_llm_failure(sample_weather):
    """When LLM generation fails or times out, pipeline must fall back to deterministic advisory."""
    pipeline = WeatherGPTPipeline()

    # Mock LLM to fail
    with patch.object(pipeline.llm, "generate_response", side_effect=RuntimeError("LLM API connection timed out")):
        res = pipeline.process_query(
            message="Will it rain heavily in Coimbatore?",
            weather=sample_weather,
            persona=PersonaEnum.STUDENT,
            request_id="req_llm_fail_test"
        )

        assert res["answer"] is not None
        assert len(res["answer"]) > 10
        assert res["fallback_used"] is True
        assert res["degraded_state"] == DegradedStateEnum.DEGRADED_LLM.value
        assert "LLM generation failed" in res["degradation"]["reasons"][0]
        assert "llm" in res["degradation"]["subsystems_degraded"]
        # Safety & structure must remain intact
        assert res["location"] == "Coimbatore"
        assert res["risk"]["level"] is not None


def test_04_pipeline_degrades_gracefully_on_rag_failure(sample_weather):
    """When RAG retrieval fails, pipeline continues with empty guidance and tracks degradation."""
    pipeline = WeatherGPTPipeline()

    with patch("ai.pipeline.retrieve_safety_guidance", side_effect=Exception("Vector database unreachable")):
        res = pipeline.process_query(
            message="Coimbatore weather today?",
            weather=sample_weather,
            persona=PersonaEnum.GENERAL,
            request_id="req_rag_fail_test"
        )

        assert res["answer"] is not None
        assert "rag" in res["degradation"]["subsystems_degraded"]
        assert any("RAG" in r for r in res["degradation"]["reasons"])


@pytest.mark.asyncio
async def test_05_voice_service_graceful_degradation_on_tts_failure():
    """Voice synthesis failure must return clean degradation without crashing."""
    failing_tts = MockTTSProvider(simulate_error=True)
    service = VoiceAIService(tts_provider=failing_tts)

    res = await service.process_voice_query(
        transcript_override="What is the weather in Coimbatore?",
        location_name="Coimbatore",
        language="en"
    )

    assert res.audio_available is False
    assert res.audio_url is None
    assert res.answer is not None
    assert len(res.answer) > 0


def test_06_memory_failure_isolation(sample_weather):
    """Pipeline isolates memory exceptions and proceeds statelessly."""
    pipeline = WeatherGPTPipeline()

    with patch("ai.memory.memory_manager.get_context", side_effect=Exception("Redis memory corrupted")):
        # Should not raise exception
        res = pipeline.process_query(
            message="Coimbatore weather today",
            weather=sample_weather,
            conversation_id="corrupt_session_123",
            request_id="req_mem_iso"
        )

        assert res["answer"] is not None
        assert "memory" in res["degradation"]["subsystems_degraded"]


def test_07_validator_rejection_substitutes_deterministic_fallback(sample_weather):
    """When the validator rejects an ungrounded or contradictory response, deterministic fallback is returned."""
    pipeline = WeatherGPTPipeline()

    # LLM hallucinates an unsupported extreme temperature
    with patch.object(pipeline.llm, "generate", return_value="Severe heatwave warning! Temperatures will reach 48.0°C in Coimbatore today."):
        res = pipeline.process_query(
            message="Coimbatore weather?",
            weather=sample_weather,
            request_id="req_val_reject"
        )

        assert res["validation"]["passed"] is False
        assert res["fallback_used"] is True
        assert res["degraded_state"] == DegradedStateEnum.SAFETY_FALLBACK.value
        # Hallucinated 59.9C must not be in the final answer
        assert "48.0" not in res["answer"]


def test_08_stage_latencies_tracking(sample_weather):
    """Pipeline accurately records latencies across all discrete execution stages."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="What is the weather in Coimbatore?",
        weather=sample_weather,
        request_id="req_latencies_test"
    )

    latencies = res["stage_latencies_ms"]
    assert "total_pipeline_ms" in latencies
    assert "input_normalization_ms" in latencies
    assert "weather_reasoning_ms" in latencies
    assert "hazard_detection_ms" in latencies
    assert "advisory_engine_ms" in latencies
    assert "validation_ms" in latencies
    assert latencies["total_pipeline_ms"] >= 0.0
