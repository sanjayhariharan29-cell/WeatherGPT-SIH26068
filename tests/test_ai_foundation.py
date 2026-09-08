"""Unit Tests for Phase 1 AI Foundation.

Tests AIConfig, Provider Abstraction, and Fallback Resilience.
"""

from datetime import datetime, timezone
import pytest
from ai.config import AIConfig, LLMConfig, MeteorologicalThresholds, get_ai_config
from ai.llm import (
    BaseLLMProvider,
    GroundedLLMGenerator,
    MockLLMProvider,
    get_llm_provider,
)
from ai.models import (
    DecisionAdvisory,
    LanguageEnum,
    LocationInfo,
    NLUResult,
    PersonaEnum,
    RiskLevelEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.reasoner import WeatherReasoner


def test_ai_config_defaults():
    config = get_ai_config()
    assert config.llm.provider in ("gemini", "mock", "fallback")
    assert config.thresholds.fresh_limit_mins == 60
    assert config.thresholds.heavy_rain_prob_threshold == 80.0
    assert config.thresholds.gale_wind_threshold == 62.0


def test_custom_ai_config():
    custom_llm = LLMConfig(provider="mock", model_name="test-model", temperature=0.0)
    custom_thresholds = MeteorologicalThresholds(fresh_limit_mins=45)
    cfg = AIConfig(llm=custom_llm, thresholds=custom_thresholds)

    assert cfg.llm.model_name == "test-model"
    assert cfg.thresholds.fresh_limit_mins == 45


def test_mock_llm_provider():
    provider = MockLLMProvider(canned_response="Mocked weather response.")
    response = provider.generate_text("System", "User")
    assert response == "Mocked weather response."


def test_generator_with_mock_provider():
    now = datetime.now(timezone.utc)
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=30.0,
        humidity=65.0,
        rain_probability=20.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="IMD"
    )
    nlu = parse_query("How is the weather in Coimbatore?")
    reasoning = WeatherReasoner.evaluate(weather, current_time=now)
    advisory = DecisionAdvisory(
        persona=PersonaEnum.GENERAL,
        risk_level=RiskLevelEnum.LOW,
        headline="Clear skies",
        advisory_text="Weather is good for outdoor activities.",
        key_precautions=["No precautions required"],
        official_warning_present=False,
        source_attribution="Source: IMD",
        timestamp_info="Updated 0m ago"
    )

    mock_provider = MockLLMProvider(canned_response="Coimbatore has clear skies and 30°C.")
    generator = GroundedLLMGenerator(provider=mock_provider)

    result = generator.generate(nlu, weather, reasoning, advisory)
    assert result == "Coimbatore has clear skies and 30°C."


def test_generator_fallback_when_provider_returns_none():
    now = datetime.now(timezone.utc)
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=29.0,
        humidity=70.0,
        rain_probability=65.0,
        wind_speed=15.0,
        weather_condition="Rain",
        source="IMD"
    )
    nlu = parse_query("Naalaiku mazhai varuma?")
    reasoning = WeatherReasoner.evaluate(weather, current_time=now)
    advisory = DecisionAdvisory(
        persona=PersonaEnum.STUDENT,
        risk_level=RiskLevelEnum.MEDIUM,
        headline="Moderate rain",
        advisory_text="Carry an umbrella.",
        key_precautions=["Carry umbrella"],
        official_warning_present=False,
        source_attribution="Source: IMD",
        timestamp_info="Updated 0m ago"
    )

    # Provider that returns None (simulating API failure)
    failing_provider = MockLLMProvider(canned_response=None)
    generator = GroundedLLMGenerator(provider=failing_provider)

    fallback_result = generator.generate(nlu, weather, reasoning, advisory)
    # Fallback should kick in and produce valid, non-empty grounded text
    assert len(fallback_result) > 0
    assert "Coimbatore" in fallback_result
