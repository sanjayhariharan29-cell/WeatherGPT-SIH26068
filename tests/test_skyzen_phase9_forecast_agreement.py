"""SkyZen Phase 9: Forecast Agreement & NWP Intelligence Test Suite.

Validates the complete forecast agreement, multi-model NWP consistency, and safety layer:
1. All sources agree (HIGH confidence, score >= 75, broad agreement across metrics)
2. Minor disagreement (MEDIUM confidence, score 45-74, moderate variance)
3. Major disagreement (LOW confidence, score < 45, e.g. 80% vs 20% rain probability)
4. Stale source (freshness penalized, lower confidence)
5. Missing source / incomplete data (graceful handling, LOW/SINGLE_SOURCE, no fabricated metrics)
6. Active IMD warning preserved (authoritative override; high model consistency cannot suppress official warning)
7. Contradictory forecast (contradiction penalty, explicit contradiction explanation)
8. LLM only explains deterministic result (structured consistency factors faithfully reflected)
9. Confidence terminology correct (application-level indicator, NOT certified meteorological probability)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from ai.models import (
    ConfidenceLevelEnum,
    ForecastConsistencyFactors,
    ForecastItem,
    FreshnessStatusEnum,
    LocationInfo,
    OfficialAlert,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherDataType,
    WeatherRecord,
)
from ai.pipeline import WeatherGPTPipeline
from ai.reasoner import (
    WeatherReasoner,
    calculate_consistency_score,
    determine_confidence_level,
    evaluate_source_agreement,
)
from ai.validator.response_validator import ResponseValidator


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_location():
    return LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558, state="Tamil Nadu")


@pytest.fixture
def base_primary_weather(now, sample_location):
    return WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=70.0,
        rain_probability=20.0,
        wind_speed=12.0,
        weather_condition="Partly Cloudy",
        source="IMD (Primary)",
        data_type=WeatherDataType.CURRENT
    )


# =========================================================================
# 1. ALL SOURCES AGREE
# =========================================================================
def test_01_all_sources_agree(now, sample_location, base_primary_weather):
    """Test 1: When all sources broadly agree within thresholds, confidence is HIGH and score is >= 75."""
    secondary_weather = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=29.0,         # Δ 1.0°C <= 3.0°C
        humidity=72.0,
        rain_probability=25.0,    # Δ 5.0% <= 20.0%
        wind_speed=14.0,          # Δ 2.0 km/h <= 15.0 km/h
        weather_condition="Partly Cloudy",
        source="Open-Meteo (Secondary)",
        data_type=WeatherDataType.CURRENT
    )

    reasoning = WeatherReasoner.evaluate(
        primary_weather=base_primary_weather,
        secondary_weather=secondary_weather,
        current_time=now
    )

    assert reasoning.source_agreement == SourceAgreementEnum.HIGH
    assert reasoning.confidence_level == ConfidenceLevelEnum.HIGH
    assert reasoning.confidence_indicator == "High"
    assert reasoning.consistency_score >= 75
    assert reasoning.consistency_factors is not None
    assert "broadly agree" in reasoning.consistency_factors["summary"].lower()


# =========================================================================
# 2. MINOR DISAGREEMENT
# =========================================================================
def test_02_minor_disagreement(now, sample_location, base_primary_weather):
    """Test 2: Moderate variance in rain or temperature produces MEDIUM confidence (Score 45-74)."""
    secondary_weather = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=32.5,         # Δ 4.5°C (moderate variance)
        humidity=65.0,
        rain_probability=55.0,    # Δ 35.0% (moderate variance)
        wind_speed=25.0,          # Δ 13.0 km/h
        weather_condition="Cloudy",
        source="Open-Meteo (Secondary)",
        data_type=WeatherDataType.CURRENT
    )

    reasoning = WeatherReasoner.evaluate(
        primary_weather=base_primary_weather,
        secondary_weather=secondary_weather,
        current_time=now
    )

    assert reasoning.source_agreement in (SourceAgreementEnum.MODERATE, SourceAgreementEnum.MEDIUM)
    assert reasoning.confidence_level == ConfidenceLevelEnum.MEDIUM
    assert reasoning.confidence_indicator == "Medium"
    assert 45 <= reasoning.consistency_score <= 74
    assert "moderate" in reasoning.consistency_factors["summary"].lower() or "medium" in reasoning.consistency_factors["summary"].lower()


# =========================================================================
# 3. MAJOR DISAGREEMENT
# =========================================================================
def test_03_major_disagreement(now, sample_location):
    """Test 3: Significant divergence (e.g. 80% vs 20% rain) produces LOW confidence and clear explanation."""
    source_a_primary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=27.0,
        humidity=85.0,
        rain_probability=80.0,    # Source A predicts 80% rain
        wind_speed=22.0,
        weather_condition="Heavy Rain",
        source="Source A (IMD)",
        data_type=WeatherDataType.CURRENT
    )

    source_b_secondary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=34.0,         # Δ 7.0°C divergence
        humidity=45.0,
        rain_probability=20.0,    # Source B predicts 20% rain (Δ 60%)
        wind_speed=8.0,
        weather_condition="Sunny",
        source="Source B (NWP Model)",
        data_type=WeatherDataType.CURRENT
    )

    reasoning = WeatherReasoner.evaluate(
        primary_weather=source_a_primary,
        secondary_weather=source_b_secondary,
        current_time=now
    )

    assert reasoning.source_agreement == SourceAgreementEnum.LOW
    assert reasoning.confidence_level == ConfidenceLevelEnum.LOW
    assert reasoning.confidence_indicator == "Low"
    assert reasoning.consistency_score < 45
    # Must explain the exact disagreement: "Forecast consistency is low because available sources disagree"
    summary = reasoning.consistency_factors["summary"]
    assert "Forecast consistency is low because available sources disagree" in summary
    assert "80%" in summary and "20%" in summary

    # Verify end-to-end pipeline reflects this deterministic explanation
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="What is the rain forecast consistency today?",
        weather=source_a_primary,
        secondary_weather=source_b_secondary
    )
    assert "Forecast consistency is low because available sources disagree" in result["answer"]
    assert result["risk"]["confidence_level"] == "LOW"


# =========================================================================
# 4. STALE SOURCE PENALTY
# =========================================================================
def test_04_stale_source(now, sample_location, base_primary_weather):
    """Test 4: Stale telemetry heavily penalizes consistency score and reduces confidence."""
    stale_time = now - timedelta(hours=4)  # 240 mins old (> 180 min stale threshold)
    stale_primary = WeatherRecord(
        location=sample_location,
        observed_at=stale_time,
        retrieved_at=stale_time,
        temperature=28.0,
        humidity=70.0,
        rain_probability=20.0,
        wind_speed=12.0,
        weather_condition="Partly Cloudy",
        source="IMD (Stale)",
        data_type=WeatherDataType.CURRENT
    )

    reasoning = WeatherReasoner.evaluate(
        primary_weather=stale_primary,
        current_time=now
    )

    assert reasoning.freshness == FreshnessStatusEnum.STALE
    assert reasoning.confidence_level == ConfidenceLevelEnum.LOW
    assert "STALE" in reasoning.consistency_factors["source_freshness"]


# =========================================================================
# 5. MISSING SOURCE & INCOMPLETE DATA
# =========================================================================
def test_05_missing_source_or_incomplete_data(now, sample_location, base_primary_weather):
    """Test 5: Missing secondary source or missing primary data is handled gracefully."""
    # Sub-case A: Single source (no secondary NWP model)
    reasoning_single = WeatherReasoner.evaluate(
        primary_weather=base_primary_weather,
        secondary_weather=None,
        current_time=now
    )
    assert reasoning_single.source_agreement == SourceAgreementEnum.SINGLE_SOURCE
    assert "Single source" in reasoning_single.consistency_factors["rainfall_agreement"]
    assert reasoning_single.consistency_score > 0

    # Sub-case B: Null/missing primary data
    reasoning_null = WeatherReasoner.evaluate(
        primary_weather=None,
        current_time=now
    )
    assert reasoning_null.data_complete is False
    assert reasoning_null.consistency_score == 0
    assert reasoning_null.confidence_level == ConfidenceLevelEnum.LOW
    assert reasoning_null.confidence_indicator == "Low"


# =========================================================================
# 6. ACTIVE IMD WARNING PRESERVED (AUTHORITATIVE OVERRIDE)
# =========================================================================
def test_06_active_imd_warning_preserved(now, sample_location):
    """Test 6: High generic forecast consistency must NEVER suppress an official IMD warning."""
    # Both generic models agree on low rainfall and clear skies
    primary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=26.0,
        humidity=50.0,
        rain_probability=10.0,
        wind_speed=10.0,
        weather_condition="Clear",
        source="Generic Model A",
        data_type=WeatherDataType.CURRENT
    )
    secondary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=26.5,
        humidity=52.0,
        rain_probability=12.0,
        wind_speed=11.0,
        weather_condition="Clear",
        source="Generic Model B",
        data_type=WeatherDataType.CURRENT
    )

    # But authoritative IMD has issued a RED ALERT
    imd_red_warning = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Red Alert",
        description="Extremely severe cyclonic storm approaching coastal zones. Mandatory evacuation.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12),
        data_type=WeatherDataType.OFFICIAL_WARNING
    )

    reasoning = WeatherReasoner.evaluate(
        primary_weather=primary,
        secondary_weather=secondary,
        active_alerts=[imd_red_warning],
        current_time=now
    )

    # Crucial invariant: overall_risk must be EXTREME despite mild generic model predictions
    assert reasoning.overall_risk == RiskLevelEnum.EXTREME
    assert len(reasoning.active_warnings) == 1
    assert reasoning.active_warnings[0].severity == RiskLevelEnum.EXTREME

    # Test Validator: Intercepts attempt to suppress warning using model consistency
    validator = ResponseValidator()
    suppressed_response = (
        "Both Generic Model A and Model B agree that the forecast consistency is high and skies are clear, "
        "so there is no need to worry about the warning. Conditions are safe."
    )
    val_bad = validator.validate_response(
        response_text=suppressed_response,
        reasoning=reasoning,
        weather=primary
    )
    assert val_bad.is_valid is False
    assert any("warning suppression" in err.lower() or "warning" in err.lower() for err in val_bad.violations)

    # Safe response acknowledging official warning
    safe_response = (
        "⚠️ [OFFICIAL IMD WARNING] Cyclone Red Alert: Extremely severe cyclonic storm approaching coastal zones. "
        "Mandatory evacuation in effect. Although local observations currently indicate 26°C with clear skies, "
        "the official IMD warning takes unconditional priority."
    )
    val_good = validator.validate_response(
        response_text=safe_response,
        reasoning=reasoning,
        weather=primary
    )
    assert val_good.is_valid is True


# =========================================================================
# 7. CONTRADICTORY FORECAST
# =========================================================================
def test_07_contradictory_forecast(now, sample_location):
    """Test 7: Contradictory weather predictions are penalized and documented in consistency factors."""
    primary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=70.0,
        rain_probability=90.0,
        wind_speed=40.0,
        weather_condition="Thunderstorm",
        source="IMD",
        data_type=WeatherDataType.CURRENT
    )
    secondary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=70.0,
        rain_probability=10.0,    # Severe precipitation contradiction (Δ 80%)
        wind_speed=5.0,           # Wind speed contradiction (Δ 35 km/h)
        weather_condition="Sunny",
        source="Open-Meteo",
        data_type=WeatherDataType.CURRENT
    )

    reasoning = WeatherReasoner.evaluate(
        primary_weather=primary,
        secondary_weather=secondary,
        current_time=now
    )

    assert len(reasoning.contradictions) > 0
    assert any("precipitation conflict" in c.lower() for c in reasoning.contradictions)
    assert reasoning.confidence_level == ConfidenceLevelEnum.LOW
    assert len(reasoning.consistency_factors["contradictions"]) > 0


# =========================================================================
# 8. LLM ONLY EXPLAINS STRUCTURED RESULT
# =========================================================================
def test_08_llm_explains_deterministic_result(now, sample_location):
    """Test 8: Deterministic consistency system calculates structured result; LLM strictly explains it."""
    primary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=30.0,
        humidity=60.0,
        rain_probability=80.0,
        wind_speed=15.0,
        weather_condition="Rainy",
        source="Source A",
        data_type=WeatherDataType.CURRENT
    )
    secondary = WeatherRecord(
        location=sample_location,
        observed_at=now,
        retrieved_at=now,
        temperature=31.0,
        humidity=58.0,
        rain_probability=20.0,
        wind_speed=14.0,
        weather_condition="Partly Cloudy",
        source="Source B",
        data_type=WeatherDataType.CURRENT
    )

    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="Should I expect rain today given source disagreement?",
        weather=primary,
        secondary_weather=secondary
    )

    # Verify structured factors are in decision trace
    trace = result["decision_trace_model"]
    assert trace.confidence_level == "LOW"
    assert trace.confidence_indicator == "Low"
    assert trace.consistency_factors is not None
    assert "rainfall_agreement" in trace.consistency_factors
    assert "summary" in trace.consistency_factors

    # Verify LLM explanation faithfully incorporates the deterministic low consistency summary
    answer = result["answer"]
    assert "Forecast consistency is low" in answer
    assert "disagree" in answer.lower()


# =========================================================================
# 9. CONFIDENCE TERMINOLOGY & OVERCLAIM CHECK
# =========================================================================
def test_09_confidence_terminology_and_overclaim_check(now, sample_location, base_primary_weather):
    """Test 9: Score is termed application-level indicator; certified scientific claims are rejected."""
    validator = ResponseValidator()
    reasoning = WeatherReasoner.evaluate(primary_weather=base_primary_weather)

    # Invalid: Claims certified meteorological probability
    overclaim_response = (
        "In Coimbatore, current temperature is 28°C. Our model provides a certified meteorological probability "
        "and guaranteed scientific certainty of 95%."
    )
    val_bad = validator.validate_response(
        response_text=overclaim_response,
        reasoning=reasoning,
        weather=base_primary_weather
    )
    assert val_bad.is_valid is False
    assert any("overclaim" in err.lower() or "scientific" in err.lower() for err in val_bad.violations)

    # Valid: Accurately references application-level Forecast Consistency Score
    valid_response = (
        "In Coimbatore, current temperature is 28°C with a 20% chance of precipitation. "
        "Forecast Consistency (High): Forecast consistency is high as available forecast sources broadly agree.\n"
        "(Source: IMD (Primary) | Updated 0m ago | Forecast Consistency Score: 95/100 [Data Confidence Indicator: High])"
    )
    val_good = validator.validate_response(
        response_text=valid_response,
        reasoning=reasoning,
        weather=base_primary_weather
    )
    assert val_good.is_valid is True
