"""Weather Reasoner Depth & Consistency Intelligence Test Suite for WeatherGPT (Phase 3).

Tests freshness, completeness, multi-source agreement, contradiction detection,
official warning prioritization, and consistency scoring per Phase 3 Roadmap.
"""

from datetime import datetime, timedelta, timezone
import pytest
from ai.models import (
    ForecastItem,
    FreshnessStatusEnum,
    LocationInfo,
    OfficialAlert,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherRecord,
)
from ai.reasoner import (
    WeatherReasoner,
    calculate_consistency_score,
    check_data_freshness,
    detect_contradictions,
    evaluate_completeness,
    evaluate_source_agreement,
)


@pytest.fixture
def base_weather():
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now - timedelta(minutes=15),
        retrieved_at=now - timedelta(minutes=5),
        temperature=29.0,
        humidity=72.0,
        rain_probability=65.0,
        wind_speed=18.0,
        weather_condition="Rain",
        source="IMD"
    )


# ==========================================
# 1. Freshness & Missing Data Tests
# ==========================================

def test_freshness_edge_cases():
    now = datetime.now(timezone.utc)

    # 5 minutes -> Fresh
    status, age = check_data_freshness(now - timedelta(minutes=5), current_time=now)
    assert status == FreshnessStatusEnum.FRESH
    assert age == 5

    # 90 minutes -> Acceptable
    status, age = check_data_freshness(now - timedelta(minutes=90), current_time=now)
    assert status == FreshnessStatusEnum.ACCEPTABLE
    assert age == 90

    # 300 minutes -> Stale
    status, age = check_data_freshness(now - timedelta(minutes=300), current_time=now)
    assert status == FreshnessStatusEnum.STALE
    assert age == 300


def test_missing_weather_record_safety():
    now = datetime.now(timezone.utc)
    # Reasoner called with None primary weather
    result = WeatherReasoner.evaluate(primary_weather=None, current_time=now)
    assert result.data_complete is False
    assert "primary_weather_record" in result.missing_fields
    assert result.consistency_score == 0
    assert result.location == "Unknown"


# ==========================================
# 2. Data Completeness Tests
# ==========================================

def test_data_completeness(base_weather):
    is_complete, missing = evaluate_completeness(base_weather)
    assert is_complete is True
    assert len(missing) == 0

    # Incomplete record
    incomplete = base_weather.model_copy(update={"temperature": None, "wind_speed": None})
    is_complete_inc, missing_inc = evaluate_completeness(incomplete)
    assert is_complete_inc is False
    assert "temperature" in missing_inc
    assert "wind_speed" in missing_inc


# ==========================================
# 3. Source Agreement & Disagreement Tests
# ==========================================

def test_source_agreement_and_disagreement(base_weather):
    # Secondary source agreeing
    secondary_agree = base_weather.model_copy(update={
        "source": "Open-Meteo",
        "temperature": 29.5,
        "rain_probability": 70.0,
        "wind_speed": 16.0
    })
    agreement, note = evaluate_source_agreement(base_weather, secondary_agree)
    assert agreement == SourceAgreementEnum.HIGH

    # Secondary source strongly disagreeing
    secondary_disagree = base_weather.model_copy(update={
        "source": "Open-Meteo",
        "temperature": 38.0,       # 9 deg difference
        "rain_probability": 10.0,   # 55% difference
        "wind_speed": 60.0         # 42 km/h difference
    })
    agreement_low, note_low = evaluate_source_agreement(base_weather, secondary_disagree)
    assert agreement_low == SourceAgreementEnum.LOW
    assert "Disagreement" in note_low


# ==========================================
# 4. Contradiction Detection Tests
# ==========================================

def test_contradiction_multi_source_conflict(base_weather):
    secondary_conflict = base_weather.model_copy(update={
        "source": "Open-Meteo",
        "rain_probability": 5.0,     # Primary is 65% -> 60% diff
        "temperature": 37.0,         # 8 deg diff
        "wind_speed": 55.0           # 37 km/h diff
    })
    contradictions = detect_contradictions(primary=base_weather, secondary=secondary_conflict)
    assert len(contradictions) >= 2
    assert any("precipitation conflict" in c.lower() for c in contradictions)
    assert any("temperature divergence" in c.lower() for c in contradictions)


def test_contradiction_warning_vs_sunny_condition(base_weather):
    # Primary says Sunny, but IMD issued a Cyclone / Severe warning
    sunny_weather = base_weather.model_copy(update={"weather_condition": "Sunny and Clear"})
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Alert",
        description="Gale winds and surge expected",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12)
    )

    contradictions = detect_contradictions(primary=sunny_weather, active_alerts=[alert])
    assert len(contradictions) > 0
    assert any("Authoritative Warning Override" in c for c in contradictions)


def test_contradiction_forecast_unphysical_swing(base_weather):
    forecast_swing = [
        ForecastItem(time="10:00", temperature=25.0, rain_probability=20.0, wind_speed=10.0, condition="Clear"),
        ForecastItem(time="11:00", temperature=42.0, rain_probability=20.0, wind_speed=10.0, condition="Clear"), # 17 deg jump in 1 hr
    ]
    contradictions = detect_contradictions(primary=base_weather, forecast=forecast_swing)
    assert any("Unphysical forecast swing" in c for c in contradictions)


# ==========================================
# 5. Authoritative Warning Priority & Separation
# ==========================================

def test_official_warning_priority_over_normal_data(base_weather):
    # Weather is calm, but IMD issued an official high severity warning
    calm_weather = base_weather.model_copy(update={
        "temperature": 27.0,
        "rain_probability": 10.0,
        "wind_speed": 8.0,
        "weather_condition": "Clear"
    })
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="heavy_rain",
        severity=RiskLevelEnum.HIGH,
        title="Heavy Rain Red Alert",
        description="Inundation expected later tonight",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=8)
    )

    result = WeatherReasoner.evaluate(calm_weather, active_alerts=[alert], current_time=now)

    # Risk must reflect the official alert, not the calm current observation!
    assert result.overall_risk == RiskLevelEnum.HIGH
    assert len(result.active_warnings) == 1
    assert result.active_warnings[0].title == "Heavy Rain Red Alert"


def test_ai_hazard_separation_from_official_warnings(base_weather):
    # Heavy rain detected purely from observation, no official warning
    heavy_rain = base_weather.model_copy(update={"rain_probability": 85.0})
    result = WeatherReasoner.evaluate(heavy_rain, active_alerts=[])

    assert len(result.active_warnings) == 0
    assert len(result.ai_detected_hazards) >= 1
    assert any(h.hazard_type == "HEAVY_RAINFALL" for h in result.ai_detected_hazards)


# ==========================================
# 6. Consistency Score Behavior Tests
# ==========================================

def test_consistency_score_computation():
    # Ideal: High agreement, fresh, complete, warning clarity
    score_ideal = calculate_consistency_score(
        agreement=SourceAgreementEnum.HIGH,
        freshness=FreshnessStatusEnum.FRESH,
        has_active_warning=True,
        data_complete=True,
        contradiction_count=0
    )
    assert score_ideal >= 85

    # Poor: Low agreement, stale, incomplete, 2 contradictions
    score_poor = calculate_consistency_score(
        agreement=SourceAgreementEnum.LOW,
        freshness=FreshnessStatusEnum.STALE,
        has_active_warning=False,
        data_complete=False,
        contradiction_count=2
    )
    assert score_poor < 40
