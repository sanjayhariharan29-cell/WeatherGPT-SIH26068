"""Unit Tests for WeatherGPT AI Intelligence Core.

Tests NLU (English, Tamil, Tanglish), Weather Reasoner,
Decision Engine, and Response Validator.
"""

from datetime import datetime, timedelta, timezone
import pytest
from ai import (
    DecisionEngine,
    ForecastItem,
    IntentEnum,
    LanguageEnum,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    ResponseValidator,
    RiskLevelEnum,
    WeatherReasoner,
    WeatherRecord,
    calculate_consistency_score,
    check_data_freshness,
    classify_intent,
    detect_hazards,
    detect_language,
    evaluate_source_agreement,
    extract_entities,
    parse_query,
)


# ==========================================
# 1. NLU Tests (Language, Intent, Entities)
# ==========================================

def test_language_detection():
    # Tamil script
    assert detect_language("நாளைக்கு மழை வருமா?") == LanguageEnum.TA
    assert detect_language("இன்று வானிலை எப்படி?") == LanguageEnum.TA

    # Tanglish
    assert detect_language("Naalaiku morning Coimbatore la mazhai varuma?") == LanguageEnum.TANGLISH
    assert detect_language("Naalaiku college pogalama?") == LanguageEnum.TANGLISH
    assert detect_language("Chennai la rain iruka?") == LanguageEnum.TANGLISH

    # English
    assert detect_language("Will it rain tomorrow in Coimbatore?") == LanguageEnum.EN
    assert detect_language("What is the current temperature?") == LanguageEnum.EN


def test_intent_classification():
    # Hero query 1: Student outdoor decision
    intent, conf = classify_intent("Naalaiku college pogalama?")
    assert intent == IntentEnum.OUTDOOR_DECISION
    assert conf >= 0.85

    # Rain forecast
    intent, conf = classify_intent("Will it rain tomorrow morning?")
    assert intent == IntentEnum.RAIN_FORECAST

    # Cyclone alert
    intent, conf = classify_intent("Is there any cyclone warning for Nagapattinam?")
    assert intent == IntentEnum.CYCLONE_INQUIRY

    # Tamil fisherman marine query
    intent, conf = classify_intent("நாளைக்கு கடலுக்கு போகலாமா?")
    assert intent == IntentEnum.OUTDOOR_DECISION


def test_entity_extraction():
    entities = extract_entities("Tomorrow morning Coimbatore la mazhai varuma?")
    assert entities.location == "Coimbatore"
    assert entities.date == "tomorrow"
    assert entities.time == "morning"
    assert entities.weather_variable == "rainfall"

    student_query = extract_entities("Naalaiku college pogalama?")
    assert student_query.persona == PersonaEnum.STUDENT
    assert student_query.date == "tomorrow"

    marine_query = extract_entities("Tomorrow fishing trip Nagapattinam la safe ah?")
    assert marine_query.location == "Nagapattinam"
    assert marine_query.persona == PersonaEnum.FISHERMAN


def test_unified_parse_query():
    res = parse_query("Naalaiku morning Coimbatore la mazhai varuma?")
    assert res.detected_language == LanguageEnum.TANGLISH
    assert res.intent == IntentEnum.RAIN_FORECAST
    assert res.entities.location == "Coimbatore"
    assert res.entities.date == "tomorrow"


# ==========================================
# 2. Weather Reasoner Tests
# ==========================================

@pytest.fixture
def sample_weather():
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now - timedelta(minutes=15),
        retrieved_at=now - timedelta(minutes=10),
        temperature=29.0,
        humidity=72.0,
        rain_probability=70.0,
        wind_speed=18.0,
        weather_condition="Rain",
        source="IMD"
    )


def test_freshness_check():
    now = datetime.now(timezone.utc)
    # 20 minutes old -> Fresh
    status, age = check_data_freshness(now - timedelta(minutes=20), current_time=now)
    assert status.value == "fresh"
    assert age == 20

    # 120 minutes old -> Acceptable
    status, age = check_data_freshness(now - timedelta(minutes=120), current_time=now)
    assert status.value == "acceptable"

    # 250 minutes old -> Stale
    status, age = check_data_freshness(now - timedelta(minutes=250), current_time=now)
    assert status.value == "stale"


def test_hazard_detection(sample_weather):
    # Standard rain
    hazards = detect_hazards(sample_weather)
    assert any(h.hazard_type == "MODERATE_RAINFALL" for h in hazards)

    # Active official alert takes priority
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Warning",
        description="Severe cyclonic storm crossing coast",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12)
    )
    hazards_with_alert = detect_hazards(sample_weather, active_alerts=[alert])
    assert any("OFFICIAL_WARNING_CYCLONE" in h.hazard_type for h in hazards_with_alert)


def test_source_agreement(sample_weather):
    # High agreement secondary source
    secondary = sample_weather.model_copy(update={
        "source": "Open-Meteo",
        "rain_probability": 75.0,
        "temperature": 28.5
    })
    agreement, note = evaluate_source_agreement(sample_weather, secondary)
    assert agreement.value == "high"

    # Low agreement secondary source
    conflicting = sample_weather.model_copy(update={
        "source": "Open-Meteo",
        "rain_probability": 10.0,
        "temperature": 36.0
    })
    agreement_low, note_low = evaluate_source_agreement(sample_weather, conflicting)
    assert agreement_low.value == "low"
    assert "Disagreement" in note_low


def test_weather_reasoner_pipeline(sample_weather):
    now = datetime.now(timezone.utc)
    result = WeatherReasoner.evaluate(primary_weather=sample_weather, current_time=now)
    assert result.location == "Coimbatore"
    assert result.freshness.value == "fresh"
    assert result.consistency_score > 70
    assert result.overall_risk in (RiskLevelEnum.LOW, RiskLevelEnum.MEDIUM)


# ==========================================
# 3. Decision Engine Tests
# ==========================================

def test_student_advisory(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)

    advisory_en = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.STUDENT, target_language=LanguageEnum.EN)
    assert advisory_en.persona == PersonaEnum.STUDENT
    assert len(advisory_en.key_precautions) > 0
    assert "umbrella" in advisory_en.key_precautions[0].lower() or "rain" in advisory_en.headline.lower()

    advisory_ta = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.STUDENT, target_language=LanguageEnum.TA)
    assert "மழை" in advisory_ta.headline or "மழை" in advisory_ta.advisory_text


def test_fisherman_advisory_under_cyclone_alert(sample_weather):
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Red Alert",
        description="Gale winds expected over coastal waters",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=24)
    )
    reasoning = WeatherReasoner.evaluate(sample_weather, active_alerts=[alert], current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FISHERMAN, target_language=LanguageEnum.EN)

    assert advisory.risk_level == RiskLevelEnum.EXTREME
    assert advisory.official_warning_present is True
    assert "Avoid Venturing into Sea" in advisory.headline or "Marine" in advisory.headline
    assert any("not venture into open sea" in p.lower() for p in advisory.key_precautions)


# ==========================================
# 4. Response Validator Tests
# ==========================================

def test_response_validator_contradiction_detection(sample_weather):
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="heavy_rain",
        severity=RiskLevelEnum.HIGH,
        title="Heavy Rain Warning",
        description="Very heavy downpours expected",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=6)
    )
    reasoning = WeatherReasoner.evaluate(sample_weather, active_alerts=[alert], current_time=now)

    # Hallucinated / contradicting response:
    unsafe_response = "The weather is completely safe with no warnings active. You can go out without worries."
    validation = ResponseValidator.validate_response(unsafe_response, reasoning=reasoning, weather=sample_weather)

    assert validation.is_valid is False
    assert validation.warning_consistency_passed is False
    assert any("Warning Contradiction" in issue for issue in validation.issues)


def test_response_validator_unauthorized_holiday_declaration(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)

    bad_response = "Due to rain, your college will be closed tomorrow."
    validation = ResponseValidator.validate_response(bad_response, reasoning=reasoning, weather=sample_weather)

    assert validation.is_valid is False
    assert any("Unauthorized Institutional Declaration" in issue for issue in validation.issues)


def test_response_validator_clean_grounded_response(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)

    good_response = "In Coimbatore, the temperature is 29°C with a 70% chance of rain. Carry an umbrella."
    validation = ResponseValidator.validate_response(good_response, reasoning=reasoning, weather=sample_weather)

    assert validation.is_valid is True
    assert len(validation.verified_claims) >= 1
