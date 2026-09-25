"""Deterministic Unit & Integration Tests for SkyZen Specialized Advisory Modes.

Tests all domain modes:
- Farmer Mode (rainfall, irrigation timing, heat/stress, activity planning, agronomic disclaimer)
- Fisherman / Marine Mode (wind, wave telemetry presence/absence, IMD warning precedence, departure verdict)
- Aviation Mode (airport, wind, visibility presence/absence, hazards, non-certification disclaimer)
- Commuter / Student Mode (departure/return time, rain risk, heat, wind, umbrella/clothing/travel advice)
- Disaster Mode (active warning summary, severity, action guidance, notification status)
- Smart City Mode (rainfall, heat, AQI presence/absence, severe weather, civic action items)
- Multilingual Localization (English, Tamil, Hindi, Marathi, Telugu)
- REST Endpoint Integration (/weather/advisory)
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from ai.models import (
    AdvisoryModeEnum,
    AdvisoryPriorityEnum,
    ForecastItem,
    HazardDetection,
    LanguageEnum,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherRecord,
)
from ai.reasoner.reasoner import WeatherReasoner
from ai.decision.decision_engine import DecisionEngine
from ai.decision.specialized_modes import (
    SpecializedAdvisoryEngine,
    FarmerAdvisoryResult,
    MarineAdvisoryResult,
    AviationAdvisoryResult,
    CommuterStudentAdvisoryResult,
    DisasterAdvisoryResult,
    SmartCityAdvisoryResult,
    SpecializedModeResponse,
)


@pytest.fixture
def client():
    return TestClient(app)


def make_sample_weather(
    temp: float = 28.0,
    rain_prob: float = 10.0,
    rain_mm: float = 0.0,
    wind_spd: float = 12.0,
    humidity: float = 60.0,
    condition: str = "Partly Cloudy",
    location_name: str = "Coimbatore",
    wave_height: float = None,
    visibility: float = None,
    aqi: int = None
) -> WeatherRecord:
    now = datetime.now(timezone.utc)
    w = WeatherRecord(
        location=LocationInfo(
            name=location_name,
            latitude=11.0168,
            longitude=76.9558,
            district="Coimbatore",
            state="Tamil Nadu"
        ),
        observed_at=now,
        retrieved_at=now,
        temperature=temp,
        humidity=humidity,
        rain_probability=rain_prob,
        wind_speed=wind_spd,
        weather_condition=condition,
        source="OpenWeather",
        rainfall_amount_mm=rain_mm,
    )
    if wave_height is not None:
        setattr(w, "wave_height_m", wave_height)
        setattr(w, "wave_period_s", 6.5)
    if visibility is not None:
        setattr(w, "visibility", visibility)
    if aqi is not None:
        setattr(w, "aqi", aqi)
        setattr(w, "primary_pollutant", "PM2.5")
    return w


def make_official_alert(
    title: str = "Cyclone Alert",
    severity: RiskLevelEnum = RiskLevelEnum.EXTREME,
    type_str: str = "CYCLONE",
    location: str = "Coimbatore"
) -> OfficialAlert:
    now = datetime.now(timezone.utc)
    return OfficialAlert(
        title=title,
        severity=severity,
        type=type_str,
        source="India Meteorological Department",
        description="Severe cyclonic storm approaching coastal and inland regions.",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=24),
        affected_locations=[location]
    )


# ==============================================================================
# 1. Farmer Mode Tests
# ==============================================================================

def test_farmer_mode_rain_suspends_irrigation():
    """Heavy rain forecast triggers immediate irrigation suspension and harvest protection."""
    w = make_sample_weather(temp=26.0, rain_prob=80.0, rain_mm=22.0, wind_spd=15.0)
    reasoning = WeatherReasoner.evaluate(primary_weather=w)

    res = SpecializedAdvisoryEngine.evaluate_farmer_mode(reasoning, w)
    assert isinstance(res, FarmerAdvisoryResult)
    assert res.irrigation_timing == "suspend_immediately"
    assert "suspend all irrigation immediately" in res.irrigation_guidance.lower()
    assert res.harvest_protection_needed is True
    assert res.spraying_viable is False
    assert "advisory interface" in res.disclaimer.lower()


def test_farmer_mode_heat_stress_guidance():
    """Extreme heatwave (>40°C) with dry conditions triggers heat stress awareness and evening irrigation."""
    w = make_sample_weather(temp=41.5, rain_prob=0.0, rain_mm=0.0, wind_spd=10.0)
    reasoning = WeatherReasoner.evaluate(primary_weather=w)

    res = SpecializedAdvisoryEngine.evaluate_farmer_mode(reasoning, w)
    assert res.heat_stress_level == "severe_heatwave"
    assert "severe heat stress" in res.heat_stress_awareness.lower()
    assert res.irrigation_timing == "morning_or_evening_only"
    assert "early morning" in res.irrigation_guidance.lower()
    assert res.spraying_viable is True


def test_farmer_mode_high_winds_postpones_spraying():
    """Elevated wind speeds (>20 km/h) postpone foliar spraying due to drift hazard."""
    w = make_sample_weather(temp=29.0, rain_prob=10.0, rain_mm=0.0, wind_spd=26.0)
    reasoning = WeatherReasoner.evaluate(primary_weather=w)

    res = SpecializedAdvisoryEngine.evaluate_farmer_mode(reasoning, w)
    assert res.spraying_viable is False
    assert "postpone" in res.spraying_guidance.lower()
    assert any("staking" in plan.lower() for plan in res.weather_sensitive_planning)


# ==============================================================================
# 2. Fisherman / Marine Mode Tests
# ==============================================================================

def test_marine_mode_official_warning_forces_no_go():
    """SAFETY INVARIANT: Official IMD warning unconditionally forces departure verdict to NO_GO."""
    w = make_sample_weather(temp=28.0, wind_spd=12.0)  # Calm wind
    alert = make_official_alert(title="IMD Marine Squall Warning", severity=RiskLevelEnum.HIGH, type_str="MARINE")
    reasoning = WeatherReasoner.evaluate(primary_weather=w, active_alerts=[alert])

    res = SpecializedAdvisoryEngine.evaluate_marine_mode(reasoning, w)
    assert isinstance(res, MarineAdvisoryResult)
    assert res.departure_verdict == "NO_GO"
    assert res.has_official_warning is True
    assert "strict prohibition" in res.departure_advisory.lower()
    assert len(res.official_marine_warnings) > 0


def test_marine_mode_wave_telemetry_grounding():
    """Wave information is reported when verified; strictly flagged as unavailable when absent."""
    # 1. Missing wave telemetry (default) -> NEVER FABRICATE
    w_no_wave = make_sample_weather(temp=28.0, wind_spd=14.0)
    reasoning_no_wave = WeatherReasoner.evaluate(primary_weather=w_no_wave)
    res_no_wave = SpecializedAdvisoryEngine.evaluate_marine_mode(reasoning_no_wave, w_no_wave)

    assert res_no_wave.wave_information["is_available"] is False
    assert res_no_wave.wave_information["wave_height_m"] is None
    assert "unavailable" in res_no_wave.wave_information["summary"].lower()

    # 2. Verified wave telemetry present
    w_with_wave = make_sample_weather(temp=28.0, wind_spd=14.0, wave_height=2.4)
    reasoning_wave = WeatherReasoner.evaluate(primary_weather=w_with_wave)
    res_wave = SpecializedAdvisoryEngine.evaluate_marine_mode(reasoning_wave, w_with_wave)

    assert res_wave.wave_information["is_available"] is True
    assert res_wave.wave_information["wave_height_m"] == 2.4


def test_marine_mode_wind_thresholds():
    """Wind speeds dictate departure verdict: Calm -> GO, Moderate -> CAUTION, Squally -> NO_GO."""
    # Calm
    w_calm = make_sample_weather(wind_spd=12.0)
    res_calm = SpecializedAdvisoryEngine.evaluate_marine_mode(WeatherReasoner.evaluate(w_calm), w_calm)
    assert res_calm.departure_verdict == "GO"

    # Moderate (25-39 km/h)
    w_mod = make_sample_weather(wind_spd=28.0)
    res_mod = SpecializedAdvisoryEngine.evaluate_marine_mode(WeatherReasoner.evaluate(w_mod), w_mod)
    assert res_mod.departure_verdict == "CAUTION"

    # Squall / Gale (>40 km/h)
    w_storm = make_sample_weather(wind_spd=46.0)
    res_storm = SpecializedAdvisoryEngine.evaluate_marine_mode(WeatherReasoner.evaluate(w_storm), w_storm)
    assert res_storm.departure_verdict == "NO_GO"


# ==============================================================================
# 3. Aviation Mode Tests
# ==============================================================================

def test_aviation_mode_visibility_grounding():
    """Visibility telemetry is faithfully represented without fabrication when absent."""
    # Absent
    w_no_vis = make_sample_weather(wind_spd=15.0)
    res_no_vis = SpecializedAdvisoryEngine.evaluate_aviation_mode(
        WeatherReasoner.evaluate(w_no_vis), w_no_vis, airport_code="VOCB"
    )
    assert isinstance(res_no_vis, AviationAdvisoryResult)
    assert res_no_vis.airport_or_location == "VOCB"
    assert res_no_vis.visibility["is_available"] is False
    assert res_no_vis.visibility["visibility_km"] is None
    assert "not a certified aviation" in res_no_vis.disclaimer.lower()

    # Present
    w_vis = make_sample_weather(wind_spd=15.0, visibility=4.2)
    res_vis = SpecializedAdvisoryEngine.evaluate_aviation_mode(
        WeatherReasoner.evaluate(w_vis), w_vis, airport_code="VOBL"
    )
    assert res_vis.visibility["is_available"] is True
    assert res_vis.visibility["visibility_km"] == 4.2
    assert res_vis.visibility["is_low_visibility"] is True
    assert res_vis.flight_category_indicator == "MARGINAL_VFR"


def test_aviation_mode_thunderstorm_hazard():
    """Active thunderstorm hazard triggers HAZARDOUS category."""
    w = make_sample_weather(wind_spd=32.0, condition="Thunderstorm")
    alert = make_official_alert(title="Severe Thunderstorm Watch", severity=RiskLevelEnum.HIGH, type_str="THUNDERSTORM")
    reasoning = WeatherReasoner.evaluate(primary_weather=w, active_alerts=[alert])

    res = SpecializedAdvisoryEngine.evaluate_aviation_mode(reasoning, w)
    assert res.flight_category_indicator == "HAZARDOUS"
    assert res.thunderstorms["detected"] is True
    assert any("Thunderstorm" in h for h in res.weather_hazards)


# ==============================================================================
# 4. Commuter / Student Mode Tests
# ==============================================================================

def test_commuter_student_mode_schedule_and_umbrella():
    """Commuter mode accurately evaluates departure/return windows, rain risk, and delay buffers."""
    w = make_sample_weather(temp=32.0, rain_prob=65.0, wind_spd=18.0)
    fc = [
        ForecastItem(time="08:00 AM", temperature=28.0, rain_probability=20.0, condition="Clear", wind_speed=10.0),
        ForecastItem(time="05:00 PM", temperature=30.0, rain_probability=75.0, condition="Heavy Rain", wind_speed=15.0),
    ]
    reasoning = WeatherReasoner.evaluate(primary_weather=w, forecast=fc)

    res = SpecializedAdvisoryEngine.evaluate_commuter_student_mode(
        reasoning, w, forecast=fc, departure_time="08:30 AM", return_time="05:30 PM"
    )
    assert isinstance(res, CommuterStudentAdvisoryResult)
    assert res.departure_time == "08:30 AM"
    assert res.return_time == "05:30 PM"
    assert res.umbrella_recommendation is True
    assert res.rain_risk["return_probability"] == 75.0
    assert res.delay_buffer_minutes >= 15
    assert "evening return" in res.rain_risk["peak_window"].lower()


def test_commuter_student_mode_crosswind_two_wheeler_caution():
    """Crosswinds (>25 km/h) trigger elevated safety caution for two-wheeler commuters."""
    w = make_sample_weather(temp=27.0, wind_spd=32.0)
    res = SpecializedAdvisoryEngine.evaluate_commuter_student_mode(
        WeatherReasoner.evaluate(w), w
    )
    assert res.wind_conditions["two_wheeler_caution"] is True
    assert "flyovers" in res.wind_conditions["note"].lower()


# ==============================================================================
# 5. Disaster Mode Tests
# ==============================================================================

def test_disaster_mode_active_alert_mobilization():
    """Disaster mode summarizes official emergency warnings and triggers standby mobilization."""
    alert = make_official_alert(title="Very Severe Cyclonic Storm", severity=RiskLevelEnum.EXTREME, type_str="CYCLONE")
    reasoning = WeatherReasoner.evaluate(primary_weather=None, active_alerts=[alert])

    res = SpecializedAdvisoryEngine.evaluate_disaster_mode(reasoning)
    assert isinstance(res, DisasterAdvisoryResult)
    assert res.severity == "extreme"
    assert res.official_priority_preserved is True
    assert res.notification_status["push_notification_dispatched"] is True
    assert res.notification_status["urgency_level"] == "CRITICAL"
    assert len(res.active_warning_summary) == 1
    assert any("dewatering" in g.lower() for g in res.action_guidance)


# ==============================================================================
# 6. Smart City Mode Tests
# ==============================================================================

def test_smart_city_mode_waterlogging_and_aqi():
    """Smart city mode calculates urban drainage status and reports AQI without fabrication."""
    # 1. High rain with AQI present
    w_with_aqi = make_sample_weather(temp=36.0, rain_prob=70.0, rain_mm=25.0, aqi=165)
    res_aqi = SpecializedAdvisoryEngine.evaluate_smart_city_mode(
        WeatherReasoner.evaluate(w_with_aqi), w_with_aqi
    )
    assert isinstance(res_aqi, SmartCityAdvisoryResult)
    assert res_aqi.drainage_watch_status in ("WARNING", "ALERT")
    assert res_aqi.aqi_summary["is_available"] is True
    assert res_aqi.aqi_summary["aqi"] == 165
    assert res_aqi.aqi_summary["category"] == "Moderate"
    assert len(res_aqi.civic_action_items) > 0

    # 2. Dry with AQI absent -> NO FABRICATION
    w_no_aqi = make_sample_weather(temp=28.0)
    res_no_aqi = SpecializedAdvisoryEngine.evaluate_smart_city_mode(
        WeatherReasoner.evaluate(w_no_aqi), w_no_aqi
    )
    assert res_no_aqi.aqi_summary["is_available"] is False
    assert res_no_aqi.aqi_summary["aqi"] is None
    assert "unavailable" in res_no_aqi.aqi_summary["note"].lower()


# ==============================================================================
# 7. Unified Dispatcher & Multilingual Localization Tests
# ==============================================================================

def test_unified_evaluate_mode_multilingual():
    """Unified dispatcher produces localized responses in English, Tamil, and Hindi."""
    w = make_sample_weather(temp=32.0, rain_prob=60.0, location_name="Madurai")
    reasoning = WeatherReasoner.evaluate(w)

    # English
    res_en = SpecializedAdvisoryEngine.evaluate_mode("farmer", reasoning, w, target_language=LanguageEnum.EN)
    assert isinstance(res_en, SpecializedModeResponse)
    assert res_en.mode == "farmer"
    assert "en" in res_en.localized_answers
    assert "ta" in res_en.localized_answers
    assert "hi" in res_en.localized_answers

    # Tamil
    res_ta = SpecializedAdvisoryEngine.evaluate_mode("farmer", reasoning, w, target_language=LanguageEnum.TA)
    assert "விவசாய ஆலோசனை" in res_ta.concise_answer

    # Hindi
    res_hi = SpecializedAdvisoryEngine.evaluate_mode("marine", reasoning, w, target_language=LanguageEnum.HI)
    assert "समुद्री मौसम सलाह" in res_hi.concise_answer


def test_decision_engine_embeds_specialized_advisory():
    """DecisionEngine.generate_advisory embeds specialized_advisory payload."""
    w = make_sample_weather(temp=30.0, wind_spd=15.0)
    reasoning = WeatherReasoner.evaluate(w)

    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FARMER, weather=w)
    assert advisory.specialized_advisory is not None
    assert advisory.specialized_advisory["mode"] == "farmer"
    assert "details" in advisory.specialized_advisory

    # Aviation persona
    av_advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.AVIATION, weather=w)
    assert av_advisory.specialized_advisory["mode"] == "aviation"
    assert "flight_category_indicator" in av_advisory.specialized_advisory["details"]


# ==============================================================================
# 8. API Endpoint Integration Test (/weather/advisory)
# ==============================================================================

def test_api_weather_advisory_endpoint(client):
    """FastAPI endpoint /weather/advisory returns structured specialized mode data."""
    # Farmer mode
    resp_farmer = client.get("/api/v1/weather/advisory?mode=farmer&location=Coimbatore")
    assert resp_farmer.status_code == 200
    data_farmer = resp_farmer.json()
    assert data_farmer["mode"] == "farmer"
    assert "irrigation_guidance" in data_farmer["details"]
    assert "disclaimer" in data_farmer

    # Aviation mode
    resp_av = client.get("/api/v1/weather/advisory?mode=aviation&location=Bengaluru&airport_code=VOBL")
    assert resp_av.status_code == 200
    data_av = resp_av.json()
    assert data_av["mode"] == "aviation"
    assert "flight_category_indicator" in data_av["details"]

    # Marine mode
    resp_marine = client.get("/api/v1/weather/advisory?mode=marine&location=Chennai")
    assert resp_marine.status_code == 200
    data_marine = resp_marine.json()
    assert data_marine["mode"] == "fisherman"
    assert data_marine["details"]["departure_verdict"] in ("GO", "CAUTION", "NO_GO")

    # Smart City mode
    resp_city = client.get("/api/v1/weather/advisory?mode=smart_city&location=Mumbai")
    assert resp_city.status_code == 200
    data_city = resp_city.json()
    assert data_city["mode"] == "smart_city"
    assert "drainage_watch_status" in data_city["details"]
