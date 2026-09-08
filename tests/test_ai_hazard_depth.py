"""Unit and Regression Tests for Phase 4 Hazard Detection & Calibration.

Validates:
1. Normal weather -> false-positive control (no spurious hazards)
2. Heavy rain, extreme rainfall, very heavy rainfall thresholds
3. High winds and gale/cyclonic wind thresholds
4. Extreme temperature (heatwave, severe heatwave, coldwave)
5. Low visibility / dense fog
6. Thunderstorm and lightning hazards
7. Flash flood / waterlogging risk
8. Official warning preservation & absolute priority over calm observations
9. Temporal scoping: current vs forecast vs both
10. Machine-readable evidence modeling
11. Numeric validation safety (NaN, Inf, negative wind, impossible percentages)
12. Separation of AI-detected hazards from official alerts
"""

import math
from datetime import datetime, timedelta, timezone
import pytest
from ai.models import (
    ForecastItem,
    LocationInfo,
    OfficialAlert,
    RiskLevelEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.reasoner.hazard import detect_hazards
from ai.reasoner.reasoner import WeatherReasoner


@pytest.fixture
def base_location():
    return LocationInfo(
        name="Nagapattinam",
        latitude=10.7672,
        longitude=79.8449,
        district="Nagapattinam",
        state="Tamil Nadu"
    )


@pytest.fixture
def calm_weather(base_location):
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=base_location,
        observed_at=now - timedelta(minutes=15),
        retrieved_at=now - timedelta(minutes=10),
        temperature=28.0,
        humidity=65.0,
        rain_probability=15.0,
        wind_speed=12.0,
        weather_condition="Partly Cloudy",
        source="IMD",
        rainfall_amount_mm=0.0
    )


# =====================================================================
# 1. False-Positive Control & Normal Weather
# =====================================================================

def test_normal_weather_no_hazards(calm_weather):
    """Ordinary calm conditions must not trigger false alarms."""
    hazards = detect_hazards(calm_weather)
    assert len(hazards) == 0


def test_ordinary_light_rain_no_hazard(calm_weather):
    """Gentle showers below moderate thresholds must not trigger severe hazard."""
    light_rain = calm_weather.model_copy(update={
        "rain_probability": 35.0,
        "rainfall_amount_mm": 5.0,
        "weather_condition": "Light Drizzle"
    })
    hazards = detect_hazards(light_rain)
    assert len(hazards) == 0


# =====================================================================
# 2. Precipitation Hazards (Moderate, Heavy, Very Heavy, Extreme)
# =====================================================================

def test_moderate_rainfall_threshold(calm_weather):
    # Triggered by rain probability >= 60%
    mod_rain = calm_weather.model_copy(update={"rain_probability": 65.0})
    hazards = detect_hazards(mod_rain)
    assert any(h.hazard_type == "MODERATE_RAINFALL" and h.severity == RiskLevelEnum.MEDIUM for h in hazards)

    # Or triggered by mm amount >= 15.6 mm
    mod_rain_mm = calm_weather.model_copy(update={"rain_probability": 30.0, "rainfall_amount_mm": 25.0})
    hazards_mm = detect_hazards(mod_rain_mm)
    assert any(h.hazard_type == "MODERATE_RAINFALL" and h.severity == RiskLevelEnum.MEDIUM for h in hazards_mm)


def test_heavy_rainfall_threshold(calm_weather):
    # Rain prob >= 80%
    heavy_rain = calm_weather.model_copy(update={"rain_probability": 85.0})
    hazards = detect_hazards(heavy_rain)
    assert any(h.hazard_type == "HEAVY_RAINFALL" and h.severity == RiskLevelEnum.HIGH for h in hazards)

    # Or rainfall amount >= 64.5 mm (IMD Heavy Rain criterion)
    heavy_mm = calm_weather.model_copy(update={"rainfall_amount_mm": 75.0, "rain_probability": 40.0})
    hazards_mm = detect_hazards(heavy_mm)
    assert any(h.hazard_type == "HEAVY_RAINFALL" and h.severity == RiskLevelEnum.HIGH for h in hazards_mm)


def test_very_heavy_and_extreme_rainfall_threshold(calm_weather):
    # Very Heavy Rain: 115.6 - 204.4 mm
    very_heavy = calm_weather.model_copy(update={"rainfall_amount_mm": 140.0})
    hazards_vh = detect_hazards(very_heavy)
    assert any(h.hazard_type == "VERY_HEAVY_RAINFALL" and h.severity == RiskLevelEnum.HIGH for h in hazards_vh)
    # Also triggers flood risk
    assert any(h.hazard_type == "FLOOD_RISK" for h in hazards_vh)

    # Extremely Heavy Rain: >= 204.5 mm
    extreme = calm_weather.model_copy(update={"rainfall_amount_mm": 220.0})
    hazards_ext = detect_hazards(extreme)
    assert any(h.hazard_type == "EXTREME_RAINFALL" and h.severity == RiskLevelEnum.EXTREME for h in hazards_ext)
    assert any(h.hazard_type == "FLOOD_RISK" and h.severity == RiskLevelEnum.EXTREME for h in hazards_ext)


# =====================================================================
# 3. Wind Hazards (Strong Winds, Gale / Cyclonic Winds)
# =====================================================================

def test_strong_winds_threshold(calm_weather):
    # 40 km/h <= wind < 62 km/h -> STRONG_WINDS (HIGH)
    strong = calm_weather.model_copy(update={"wind_speed": 48.0})
    hazards = detect_hazards(strong)
    assert any(h.hazard_type == "STRONG_WINDS" and h.severity == RiskLevelEnum.HIGH for h in hazards)


def test_gale_and_cyclonic_winds_threshold(calm_weather):
    # Wind >= 62 km/h -> GALE_CYCLONIC_WINDS (EXTREME)
    gale = calm_weather.model_copy(update={"wind_speed": 68.0})
    hazards_gale = detect_hazards(gale)
    assert any(h.hazard_type == "GALE_CYCLONIC_WINDS" and h.severity == RiskLevelEnum.EXTREME for h in hazards_gale)

    # Severe gale >= 88 km/h
    cyclone_gale = calm_weather.model_copy(update={"wind_speed": 92.0})
    hazards_cg = detect_hazards(cyclone_gale)
    assert any(h.hazard_type == "GALE_CYCLONIC_WINDS" and h.severity == RiskLevelEnum.EXTREME for h in hazards_cg)
    assert any(">= 88 km/h" in h.details for h in hazards_cg)


# =====================================================================
# 4. Temperature Hazards (Heatwave & Coldwave)
# =====================================================================

def test_heatwave_thresholds(calm_weather):
    # >= 40.0°C -> HEATWAVE (HIGH)
    heat = calm_weather.model_copy(update={"temperature": 41.5})
    hazards_heat = detect_hazards(heat)
    assert any(h.hazard_type == "HEATWAVE" and h.severity == RiskLevelEnum.HIGH for h in hazards_heat)

    # >= 45.0°C -> Severe HEATWAVE (EXTREME)
    severe_heat = calm_weather.model_copy(update={"temperature": 46.0})
    hazards_sh = detect_hazards(severe_heat)
    assert any(h.hazard_type == "HEATWAVE" and h.severity == RiskLevelEnum.EXTREME for h in hazards_sh)


def test_coldwave_thresholds(calm_weather):
    # <= 10.0°C -> COLDWAVE (MEDIUM)
    cold = calm_weather.model_copy(update={"temperature": 8.0})
    hazards_cold = detect_hazards(cold)
    assert any(h.hazard_type == "COLDWAVE" and h.severity == RiskLevelEnum.MEDIUM for h in hazards_cold)

    # <= 4.0°C -> Severe COLDWAVE (HIGH)
    severe_cold = calm_weather.model_copy(update={"temperature": 3.0})
    hazards_sc = detect_hazards(severe_cold)
    assert any(h.hazard_type == "COLDWAVE" and h.severity == RiskLevelEnum.HIGH for h in hazards_sc)


# =====================================================================
# 5. Thunderstorm, Lightning, and Low Visibility
# =====================================================================

def test_thunderstorm_hazard(calm_weather):
    thunder = calm_weather.model_copy(update={"weather_condition": "Severe Thunderstorm with Lightning"})
    hazards = detect_hazards(thunder)
    assert any(h.hazard_type == "THUNDERSTORM_LIGHTNING" and h.severity == RiskLevelEnum.HIGH for h in hazards)


def test_low_visibility_fog(calm_weather):
    # Moderate Fog -> MEDIUM
    fog = calm_weather.model_copy(update={"weather_condition": "Moderate Fog"})
    hazards_fog = detect_hazards(fog)
    assert any(h.hazard_type == "LOW_VISIBILITY" and h.severity == RiskLevelEnum.MEDIUM for h in hazards_fog)

    # Dense Fog -> HIGH
    dense_fog = calm_weather.model_copy(update={"weather_condition": "Dense Fog"})
    hazards_df = detect_hazards(dense_fog)
    assert any(h.hazard_type == "LOW_VISIBILITY" and h.severity == RiskLevelEnum.HIGH for h in hazards_df)


# =====================================================================
# 6. Temporal Scoping: Current vs Forecast Hazards
# =====================================================================

def test_current_vs_forecast_scoping(calm_weather):
    # Current is calm, but forecast has heavy rain later tonight
    forecast = [
        ForecastItem(time="18:00", temperature=27.0, rain_probability=20.0, wind_speed=12.0, condition="Clear"),
        ForecastItem(time="21:00", temperature=25.0, rain_probability=90.0, wind_speed=20.0, condition="Heavy Rain", rainfall_amount_mm=40.0),
    ]
    hazards = detect_hazards(calm_weather, forecast=forecast)

    rain_hazards = [h for h in hazards if h.hazard_type == "HEAVY_RAINFALL"]
    assert len(rain_hazards) == 1
    assert rain_hazards[0].current_or_forecast == "forecast"
    assert any("21:00" in ev for ev in rain_hazards[0].evidence)


def test_both_current_and_forecast_hazard(calm_weather):
    # Current has strong winds, and forecast continues to have strong winds
    curr_windy = calm_weather.model_copy(update={"wind_speed": 45.0})
    forecast = [
        ForecastItem(time="15:00", temperature=28.0, rain_probability=10.0, wind_speed=52.0, condition="Windy")
    ]
    hazards = detect_hazards(curr_windy, forecast=forecast)
    wind_hazards = [h for h in hazards if h.hazard_type == "STRONG_WINDS"]
    assert len(wind_hazards) == 1
    assert wind_hazards[0].current_or_forecast == "both"
    assert len(wind_hazards[0].evidence) >= 2


# =====================================================================
# 7. Official Warnings Priority & Safety Preservation
# =====================================================================

def test_official_warning_preservation_and_metadata(calm_weather):
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Warning - Deep Depression",
        description="Landfall expected near coast with gale winds.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        affected_locations=["Nagapattinam", "Cuddalore"]
    )
    hazards = detect_hazards(calm_weather, active_alerts=[alert])
    official_h = [h for h in hazards if h.is_official_warning]
    assert len(official_h) == 1
    assert official_h[0].hazard_type == "OFFICIAL_WARNING_CYCLONE"
    assert official_h[0].severity == RiskLevelEnum.EXTREME
    assert official_h[0].source == "IMD"
    assert any("Nagapattinam" in ev for ev in official_h[0].evidence)


def test_official_warning_priority_over_calm_observation(calm_weather):
    """Authoritative warning must never be downgraded by calm local observation."""
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="heavy_rain",
        severity=RiskLevelEnum.HIGH,
        title="IMD Red Alert - Heavy Rain",
        description="Torrential rainfall anticipated.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12)
    )
    result = WeatherReasoner.evaluate(calm_weather, active_alerts=[alert], current_time=now)
    assert result.overall_risk == RiskLevelEnum.HIGH
    assert len(result.active_warnings) == 1
    # Check that AI detected hazards does NOT steal official warning
    assert len(result.ai_detected_hazards) == 0
    assert any(h.is_official_warning for h in result.detected_hazards)


# =====================================================================
# 8. Missing Data & Numeric Sanitization Safety
# =====================================================================

def test_missing_weather_record_safety():
    """Missing observation should not crash or hallucinate false hazards."""
    hazards = detect_hazards(None, forecast=[], active_alerts=[])
    assert len(hazards) == 0


def test_malformed_numeric_inputs_filtered(calm_weather):
    """NaN, Inf, and impossible values must be discarded safely."""
    malformed = calm_weather.model_copy(update={
        "rain_probability": float("nan"),
        "wind_speed": float("inf"),
        "rainfall_amount_mm": -50.0,
        "temperature": 999.0
    })
    hazards = detect_hazards(malformed)
    # None of these invalid numbers should trigger hazards!
    assert len(hazards) == 0


def test_impossible_percentages_rejected(calm_weather):
    # Rain prob of 300% or -20% is impossible
    invalid_p = calm_weather.model_copy(update={"rain_probability": 300.0})
    hazards = detect_hazards(invalid_p)
    assert len(hazards) == 0

    invalid_neg = calm_weather.model_copy(update={"rain_probability": -25.0})
    hazards_neg = detect_hazards(invalid_neg)
    assert len(hazards_neg) == 0


# =====================================================================
# 9. Evidence Model & Explainability
# =====================================================================

def test_machine_readable_evidence_generation(calm_weather):
    heavy_rain = calm_weather.model_copy(update={
        "rain_probability": 90.0,
        "rainfall_amount_mm": 80.0
    })
    hazards = detect_hazards(heavy_rain)
    rain_h = next(h for h in hazards if h.hazard_type == "HEAVY_RAINFALL")
    assert len(rain_h.evidence) > 0
    assert any("80.0 mm" in ev or "90%" in ev for ev in rain_h.evidence)
