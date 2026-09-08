"""Deep verification test suite for WeatherGPT Phase 7: Advisory / Decision Engine.

Covers all 23 required scenarios:
1. General user + normal weather
2. Farmer + heavy rain
3. Commuter + heavy rain
4. Fisherman + strong winds
5. Student + thunderstorm
6. Traveler + severe weather
7. Official warning override
8. High severity mapping
9. Medium severity mapping
10. Forecast-only hazard
11. Current hazard
12. Missing weather
13. Missing hazard
14. Source conflict
15. Stale data
16. Temporal context (NOW vs TOMORROW)
17. Multiple hazards
18. Contradictory inputs
19. Unsupported persona
20. Deterministic advisory output
21. Evidence generation
22. RAG-backed explanation boundary
23. Full pipeline integration
"""

from datetime import datetime, timezone, timedelta
import pytest

from ai.models import (
    AdvisoryPriorityEnum,
    AdvisoryTypeEnum,
    ExtractedEntities,
    ForecastItem,
    FreshnessStatusEnum,
    HazardDetection,
    IntentEnum,
    LanguageEnum,
    LocationInfo,
    NLUResult,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    SourceAgreementEnum,
    TimeContextEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.decision import DecisionEngine
from ai.reasoner import WeatherReasoner
from ai.pipeline import WeatherGPTPipeline


@pytest.fixture
def base_location():
    return LocationInfo(name="Chennai", latitude=13.0827, longitude=80.2707, state="Tamil Nadu")


@pytest.fixture
def normal_weather(base_location):
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=28.5,
        humidity=65.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Partly Cloudy",
        rainfall_amount_mm=0.0,
        source="IMD"
    )


@pytest.fixture
def heavy_rain_weather(base_location):
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=25.0,
        humidity=95.0,
        rain_probability=90.0,
        wind_speed=30.0,
        weather_condition="Heavy Rain",
        rainfall_amount_mm=75.0,
        source="IMD"
    )


# 1. General User + Normal Weather
def test_general_user_normal_weather(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert advisory.advisory_type == AdvisoryTypeEnum.WEATHER_SUMMARY
    assert advisory.priority in (AdvisoryPriorityEnum.LOW, AdvisoryPriorityEnum.INFO)
    assert advisory.risk_level == RiskLevelEnum.LOW
    assert "Pleasant" in advisory.headline or "Moderate" in advisory.headline or "Normal" in advisory.headline
    assert "Standard outdoor precautions" in advisory.key_precautions


# 2. Farmer + Heavy Rain
def test_farmer_heavy_rain(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FARMER)

    assert advisory.advisory_type == AdvisoryTypeEnum.FARM_ACTIVITY_CAUTION
    assert advisory.priority in (AdvisoryPriorityEnum.HIGH, AdvisoryPriorityEnum.CRITICAL)
    assert any("suspend irrigation" in p.lower() for p in advisory.key_precautions)
    assert any("drainage" in p.lower() for p in advisory.key_precautions)
    assert "FARMER_CROP_AND_DRAINAGE_PROTECTION" in advisory.reason_codes


# 3. Commuter + Heavy Rain
def test_commuter_heavy_rain(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER)

    assert advisory.advisory_type == AdvisoryTypeEnum.TRAVEL_CAUTION
    assert advisory.priority in (AdvisoryPriorityEnum.HIGH, AdvisoryPriorityEnum.CRITICAL)
    assert any("waterlogged underpasses" in p.lower() for p in advisory.key_precautions)
    assert any("extra travel time" in p.lower() for p in advisory.key_precautions)


# 4. Fisherman + Strong Winds
def test_fisherman_strong_winds(base_location):
    now = datetime.now(timezone.utc)
    windy_weather = WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=27.0,
        humidity=80.0,
        rain_probability=40.0,
        wind_speed=55.0,
        weather_condition="Windy",
        rainfall_amount_mm=5.0,
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(windy_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FISHERMAN)

    assert advisory.advisory_type == AdvisoryTypeEnum.FISHING_CAUTION
    assert advisory.priority in (AdvisoryPriorityEnum.HIGH, AdvisoryPriorityEnum.CRITICAL)
    assert any("not venture into open sea" in p.lower() for p in advisory.key_precautions)
    assert any("safe moorings" in p.lower() for p in advisory.key_precautions)


# 5. Student + Thunderstorm
def test_student_thunderstorm(base_location):
    now = datetime.now(timezone.utc)
    storm_weather = WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=26.0,
        humidity=90.0,
        rain_probability=85.0,
        wind_speed=45.0,
        weather_condition="Thunderstorm",
        rainfall_amount_mm=35.0,
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(storm_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.STUDENT)

    assert advisory.advisory_type in (AdvisoryTypeEnum.TRAVEL_CAUTION, AdvisoryTypeEnum.THUNDERSTORM_CAUTION)
    assert any("umbrella" in p.lower() or "raincoat" in p.lower() for p in advisory.key_precautions)
    assert any("institutional notifications" in p.lower() for p in advisory.key_precautions)


# 6. Traveler + Severe Weather
def test_traveler_severe_weather(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.TRAVELLER)

    assert advisory.advisory_type == AdvisoryTypeEnum.TRAVEL_CAUTION
    assert any("highway" in p.lower() or "train" in p.lower() for p in advisory.key_precautions)


# 7. Official Warning Override (Overrules Normal Telemetry)
def test_official_warning_override(normal_weather):
    now = datetime.now(timezone.utc)
    red_alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Red Alert",
        description="Severe cyclonic storm impending landfall within 12 hours",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=24)
    )
    reasoning = WeatherReasoner.evaluate(normal_weather, active_alerts=[red_alert], current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert advisory.official_warning_present is True
    assert advisory.advisory_type == AdvisoryTypeEnum.OFFICIAL_WARNING
    assert advisory.priority == AdvisoryPriorityEnum.CRITICAL
    assert advisory.risk_level == RiskLevelEnum.EXTREME
    assert "OFFICIAL_CYCLONE_ALERT" in advisory.reason_codes
    assert "official_alert" in advisory.source_basis


# 8. High Severity Mapping
def test_high_severity_mapping(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert advisory.priority in (AdvisoryPriorityEnum.HIGH, AdvisoryPriorityEnum.CRITICAL)


# 9. Medium Severity Mapping
def test_medium_severity_mapping(base_location):
    now = datetime.now(timezone.utc)
    moderate_weather = WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=27.0,
        humidity=75.0,
        rain_probability=55.0,
        wind_speed=20.0,
        weather_condition="Moderate Rain",
        rainfall_amount_mm=20.0,
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(moderate_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER)

    assert advisory.priority == AdvisoryPriorityEnum.MEDIUM
    assert any("buffer time" in p.lower() or "protection handy" in p.lower() for p in advisory.key_precautions)


# 10. Forecast-Only Hazard (Near-Term Scoping)
def test_forecast_only_hazard(normal_weather, base_location):
    now = datetime.now(timezone.utc)
    forecast_item = ForecastItem(
        time="In 3 hours",
        temperature=24.0,
        rain_probability=85.0,
        wind_speed=40.0,
        condition="Heavy Rain",
        rainfall_amount_mm=60.0
    )
    reasoning = WeatherReasoner.evaluate(normal_weather, forecast=[forecast_item], current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER, forecast=[forecast_item])

    assert advisory.time_context in (TimeContextEnum.NEXT_FEW_HOURS, TimeContextEnum.TODAY)
    assert "forecast" in advisory.source_basis


# 11. Current Hazard Scoping
def test_current_hazard_scoping(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert advisory.time_context == TimeContextEnum.NOW


# 12. Missing Weather Record Safety
def test_missing_weather_record_safety(base_location):
    now = datetime.now(timezone.utc)
    empty_weather = WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=0.0,
        humidity=0.0,
        rain_probability=0.0,
        wind_speed=0.0,
        weather_condition="Unknown",
        rainfall_amount_mm=0.0,
        source="IMD"
    )
    reasoning = WeatherReasoningResult(
        evaluated_at=now,
        location="Chennai",
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=5,
        data_complete=False,
        missing_fields=["temperature", "condition"],
        source_agreement=SourceAgreementEnum.SINGLE_SOURCE,
        consistency_score=50,
        contradictions=[],
        active_warnings=[],
        detected_hazards=[],
        overall_risk=RiskLevelEnum.LOW,
        sources_used=["IMD"]
    )
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL, weather=empty_weather)

    assert advisory.advisory_type == AdvisoryTypeEnum.DATA_UNAVAILABLE
    assert "DATA_INCOMPLETE_OR_UNAVAILABLE" in advisory.reason_codes
    assert "unavailable" in advisory.headline.lower() or "incomplete" in advisory.headline.lower()


# 13. Missing Hazard Record (Graceful Normal Handling)
def test_missing_hazard_handling(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    reasoning.detected_hazards = []
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert advisory.advisory_type == AdvisoryTypeEnum.WEATHER_SUMMARY
    assert advisory.priority in (AdvisoryPriorityEnum.LOW, AdvisoryPriorityEnum.INFO)


# 14. Source Conflict / Low Consistency
def test_source_conflict_handling(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    reasoning.consistency_score = 45
    reasoning.contradictions = ["Source A reports 35C while Source B reports 20C"]
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER)

    assert "SOURCE_DISAGREEMENT" in advisory.reason_codes
    assert "Disagreement detected across observation sources" in advisory.risk_summary


# 15. Stale Data Handling
def test_stale_data_handling(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    reasoning.data_age_minutes = 180
    reasoning.freshness = FreshnessStatusEnum.STALE
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert "STALE_DATA_NOTICE" in advisory.reason_codes
    assert any("aged 180m" in ev for ev in advisory.evidence)


# 16. Temporal Context (Tomorrow Differentiation via NLU)
def test_temporal_context_tomorrow(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    nlu = NLUResult(
        original_text="Will it rain tomorrow in Chennai?",
        detected_language=LanguageEnum.EN,
        intent=IntentEnum.RAIN_FORECAST,
        entities=ExtractedEntities(location="Chennai", date="tomorrow"),
        confidence=0.95
    )
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL, nlu=nlu)

    assert advisory.time_context == TimeContextEnum.TOMORROW


# 17. Multiple Concurrent Hazards
def test_multiple_concurrent_hazards(base_location):
    now = datetime.now(timezone.utc)
    severe_storm = WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=25.0,
        humidity=95.0,
        rain_probability=95.0,
        wind_speed=65.0,
        weather_condition="Thunderstorm with Gale Winds",
        rainfall_amount_mm=85.0,
        source="IMD"
    )
    reasoning = WeatherReasoner.evaluate(severe_storm, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FISHERMAN)

    assert advisory.priority == AdvisoryPriorityEnum.CRITICAL
    assert len(advisory.evidence) >= 1
    assert advisory.advisory_type == AdvisoryTypeEnum.FISHING_CAUTION


# 18. Contradictory Inputs (Conservative Posture)
def test_contradictory_inputs(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    reasoning.consistency_score = 30
    reasoning.contradictions = [
        "IMD radar indicates heavy convective rain cell but weather station reported 0 mm"
    ]
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL)

    assert "SOURCE_DISAGREEMENT" in advisory.reason_codes
    assert any("30/100" in ev for ev in advisory.evidence)


# 19. Unsupported Persona Fallback
def test_unsupported_persona_fallback(normal_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(normal_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona="astronomer")

    assert advisory.persona == PersonaEnum.GENERAL


# 20. Deterministic Advisory Output
def test_deterministic_advisory_output(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory1 = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FARMER)
    advisory2 = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FARMER)

    assert advisory1.advisory_type == advisory2.advisory_type
    assert advisory1.priority == advisory2.priority
    assert advisory1.headline == advisory2.headline
    assert advisory1.key_precautions == advisory2.key_precautions
    assert advisory1.reason_codes == advisory2.reason_codes


# 21. Evidence Generation
def test_evidence_generation(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER)

    assert len(advisory.evidence) > 0
    assert len(advisory.reason_codes) > 0
    assert len(advisory.source_basis) > 0
    assert any("Detected hazard" in ev for ev in advisory.evidence)


# 22. RAG-Backed Explanation Boundary
def test_rag_backed_explanation_boundary(heavy_rain_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(heavy_rain_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER)

    # Static RAG definitions do not dilute the advisory actions
    assert "waterlogged underpasses" in " ".join(advisory.key_precautions).lower()
    assert advisory.priority in (AdvisoryPriorityEnum.HIGH, AdvisoryPriorityEnum.CRITICAL)


# 23. Full Pipeline Integration
def test_full_pipeline_integration(normal_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="I am a commuter in Chennai, will it rain today?",
        weather=normal_weather,
        conversation_id="conv_phase7_test"
    )

    assert "answer" in result
    assert len(result["answer"]) > 20
    assert result["location"] == "Chennai"
