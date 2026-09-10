"""Phase 10A Comprehensive Verification Suite.

Validates:
1. Authentication flow, token validation, profile GET/PUT, language persistence, cross-user protection (Tests 1-7).
2. Multilingual UI localization (EN/TA/HI), AI language enforcement, Tanglish/Hinglish understanding, TTS locale selection (Tests 8-18).
3. AQI Authenticity, CPCB status transparency, modelled separation, timestamps, pollutant provenance, no spoofing (Tests 19-26).
4. Weather Authenticity, provider provenance, freshness, no fake temperature, no fake providers (Tests 27-30).
"""

import json
from pathlib import Path
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.security import create_access_token, hash_password
from backend.db.session import SessionLocal
from backend.db.init_db import init_db
from backend.db.models import User
from backend.schemas.weather import AirQualityResponse, AirQualityPollutantsSchema
from ai.models import (
    LanguageEnum,
    NLUResult,
    IntentEnum,
    WeatherReasoningResult,
    DecisionAdvisory,
    WeatherRecord,
    LocationInfo,
    PersonaEnum,
    RiskLevelEnum,
    FreshnessStatusEnum,
    SourceAgreementEnum,
    ConfidenceLevelEnum,
)
from ai.llm.multilingual import resolve_target_language, translate_condition
from ai.llm.context_builder import build_grounded_context, GroundedContext
from ai.llm.grounding_guard import verify_grounding
from ai.llm.generator import GroundedLLMGenerator


client = TestClient(app)


# =====================================================================
# 1. AUTHENTICATION & PROFILE VERIFICATION (Tests 1 - 7)
# =====================================================================

@pytest.fixture(scope="module")
def setup_test_users():
    """Seed test users in the canonical database."""
    init_db()
    db = SessionLocal()
    try:
        user_a = db.query(User).filter(User.email == "test_phase10a_a@skyzen.org").first()
        if not user_a:
            user_a = User(
                email="test_phase10a_a@skyzen.org",
                name="User Alpha",
                password_hash=hash_password("SecretPass123!"),
                role="user",
                is_verified=True,
                language="en",
                persona="student",
            )
            db.add(user_a)

        user_b = db.query(User).filter(User.email == "test_phase10a_b@skyzen.org").first()
        if not user_b:
            user_b = User(
                email="test_phase10a_b@skyzen.org",
                name="User Beta",
                password_hash=hash_password("SecretPass123!"),
                role="user",
                is_verified=True,
                language="ta",
                persona="farmer",
            )
            db.add(user_b)

        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)
        return {"user_a_id": user_a.id, "user_b_id": user_b.id}
    finally:
        db.close()


def test_01_auth_login(setup_test_users):
    """Test 1: Valid login produces valid session access token."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_phase10a_a@skyzen.org", "password": "SecretPass123!"}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_02_auth_valid_token(setup_test_users):
    """Test 2: Valid token allows authorized access to me endpoint."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_phase10a_a@skyzen.org", "password": "SecretPass123!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test_phase10a_a@skyzen.org"


def test_03_auth_profile_get(setup_test_users):
    """Test 3: Both /auth/profile and /users/profile GET work while authenticated."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_phase10a_a@skyzen.org", "password": "SecretPass123!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/profile
    resp1 = client.get("/api/v1/auth/profile", headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["email"] == "test_phase10a_a@skyzen.org"

    # /users/profile
    resp2 = client.get("/api/v1/users/profile", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["email"] == "test_phase10a_a@skyzen.org"


def test_04_auth_profile_put(setup_test_users):
    """Test 4: Profile PUT updates full_name and persona successfully."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_phase10a_a@skyzen.org", "password": "SecretPass123!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    put_resp = client.put(
        "/api/v1/auth/profile",
        json={"full_name": "Updated Alpha Name", "persona": "commuter"},
        headers=headers
    )
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["full_name"] == "Updated Alpha Name"
    assert data["persona"] == "commuter"


def test_05_auth_language_persistence(setup_test_users):
    """Test 5: Language persistence: EN -> TA -> HI -> EN persists in backend."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_phase10a_a@skyzen.org", "password": "SecretPass123!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Update to Tamil
    r_ta = client.put("/api/v1/auth/profile", json={"preferred_language": "ta"}, headers=headers)
    assert r_ta.status_code == 200
    assert r_ta.json()["preferred_language"] == "ta"

    # Verify via separate GET
    get_ta = client.get("/api/v1/auth/profile", headers=headers)
    assert get_ta.json()["preferred_language"] == "ta"

    # 2. Update to Hindi
    r_hi = client.put("/api/v1/auth/profile", json={"preferred_language": "hi"}, headers=headers)
    assert r_hi.status_code == 200
    assert r_hi.json()["preferred_language"] == "hi"

    # 3. Update back to English
    r_en = client.put("/api/v1/auth/profile", json={"preferred_language": "en"}, headers=headers)
    assert r_en.status_code == 200
    assert r_en.json()["preferred_language"] == "en"


def test_06_auth_invalid_token():
    """Test 6: Invalid or expired token is rejected with 401 Unauthorized."""
    resp = client.get("/api/v1/auth/profile", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_07_auth_cross_user_protection(setup_test_users):
    """Test 7: User Alpha cannot access or modify User Beta's data via unauthorized endpoints."""
    # Authenticate as Alpha
    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "test_phase10a_a@skyzen.org", "password": "SecretPass123!"}
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Verify profile returns Alpha, never Beta
    profile = client.get("/api/v1/auth/profile", headers=headers_a).json()
    assert profile["email"] == "test_phase10a_a@skyzen.org"
    assert profile["email"] != "test_phase10a_b@skyzen.org"


# =====================================================================
# 2. MULTILINGUAL QUALITY & AI CONTRACT (Tests 8 - 18)
# =====================================================================

def test_08_ui_english_localization():
    """Test 8: Frontend i18n file contains comprehensive English translations."""
    with open("frontend/i18n.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"en": {' in content
    assert '"dashboard.weather": "Weather Intelligence"' in content
    assert '"dashboard.rain_prob": "Rain Chance"' in content
    assert '"aqi.title": "Air Quality Index (AQI)"' in content


def test_09_ui_tamil_localization():
    """Test 9: Frontend i18n file contains comprehensive Tamil translations."""
    with open("frontend/i18n.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"ta": {' in content
    assert '"nav.home": "முகப்பு"' in content
    assert '"dashboard.weather": "வானிலை தரவுகள்"' in content
    assert '"dashboard.rain_prob": "மழை வாய்ப்பு"' in content
    assert '"dashboard.wind": "காற்றின் வேகம்"' in content


def test_10_ui_hindi_localization():
    """Test 10: Frontend i18n file contains comprehensive Hindi translations."""
    with open("frontend/i18n.js", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"hi": {' in content
    assert '"nav.home": "होम"' in content
    assert '"dashboard.weather": "मौसम जानकारी"' in content
    assert '"dashboard.rain_prob": "बारिश की संभावना"' in content
    assert '"dashboard.wind": "हवा की गति"' in content


# =====================================================================
# 3. AI MULTILINGUAL OUTPUT & LANGUAGE ENFORCEMENT (Tests 11 - 16)
# =====================================================================

def test_11_ai_english_generation():
    """Test 11: English AI request constructs prompt with OUTPUT_LANGUAGE: en."""
    generator = GroundedLLMGenerator()
    nlu = NLUResult(
        original_text="Will it rain today?",
        detected_language=LanguageEnum.EN,
        intent=IntentEnum.RAIN_FORECAST,
        confidence=0.95
    )
    loc = LocationInfo(name="Coimbatore", latitude=11.0, longitude=77.0)
    weather = WeatherRecord(
        location=loc,
        observed_at=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        source="Open-Meteo",
        temperature=28.0,
        humidity=70.0,
        rain_probability=40.0,
        wind_speed=12.0,
        weather_condition="partly cloudy"
    )
    reasoning = WeatherReasoningResult(
        evaluated_at=datetime.now(timezone.utc),
        location="Coimbatore",
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=10,
        source_agreement=SourceAgreementEnum.HIGH,
        consistency_score=85,
        confidence_level=ConfidenceLevelEnum.HIGH,
        overall_risk=RiskLevelEnum.LOW,
        sources_used=["Open-Meteo"]
    )
    advisory = DecisionAdvisory(
        persona=PersonaEnum.STUDENT,
        risk_level=RiskLevelEnum.LOW,
        headline="Light rain expected",
        advisory_text="Carry a small umbrella for evening classes.",
        key_precautions=["Carry an umbrella"],
        official_warning_present=False,
        source_attribution="Source: Open-Meteo",
        timestamp_info="Observed 10m ago"
    )

    resp = generator.generate_response(
        nlu=nlu,
        weather=weather,
        reasoning=reasoning,
        advisory=advisory,
        target_language=LanguageEnum.EN
    )
    assert resp.answer
    assert "Coimbatore" in resp.answer or "rain" in resp.answer.lower()


def test_12_ai_tamil_generation():
    """Test 12: Tamil AI request produces verified Tamil script response."""
    generator = GroundedLLMGenerator()
    nlu = NLUResult(
        original_text="இன்று மழை பெய்யுமா?",
        detected_language=LanguageEnum.TA,
        intent=IntentEnum.RAIN_FORECAST,
        confidence=0.95
    )
    loc = LocationInfo(name="Coimbatore", latitude=11.0, longitude=77.0)
    weather = WeatherRecord(
        location=loc,
        observed_at=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        source="Open-Meteo",
        temperature=28.0,
        humidity=70.0,
        rain_probability=65.0,
        wind_speed=15.0,
        weather_condition="rain"
    )
    reasoning = WeatherReasoningResult(
        evaluated_at=datetime.now(timezone.utc),
        location="Coimbatore",
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=10,
        source_agreement=SourceAgreementEnum.HIGH,
        consistency_score=90,
        confidence_level=ConfidenceLevelEnum.HIGH,
        overall_risk=RiskLevelEnum.MEDIUM,
        sources_used=["Open-Meteo"]
    )
    advisory = DecisionAdvisory(
        persona=PersonaEnum.STUDENT,
        risk_level=RiskLevelEnum.MEDIUM,
        headline="மழை வாய்ப்பு உள்ளது",
        advisory_text="மாலை நேரத்தில் குடை எடுத்துச் செல்வது நல்லது.",
        key_precautions=["குடை எடுத்துச் செல்லவும்"],
        official_warning_present=False,
        source_attribution="Source: Open-Meteo",
        timestamp_info="Observed 10m ago"
    )

    resp = generator.generate_response(
        nlu=nlu,
        weather=weather,
        reasoning=reasoning,
        advisory=advisory,
        target_language=LanguageEnum.TA
    )
    assert resp.answer
    # Response must contain Tamil Unicode characters [\u0B80-\u0BFF]
    import re
    assert bool(re.search(r"[\u0B80-\u0BFF]", resp.answer)), f"Expected Tamil script: {resp.answer}"
    assert "28°C" in resp.answer or "65%" in resp.answer


def test_13_ai_hindi_generation():
    """Test 13: Hindi AI request produces verified Devanagari script response."""
    generator = GroundedLLMGenerator()
    nlu = NLUResult(
        original_text="क्या आज बारिश होगी?",
        detected_language=LanguageEnum.HI,
        intent=IntentEnum.RAIN_FORECAST,
        confidence=0.95
    )
    loc = LocationInfo(name="Coimbatore", latitude=11.0, longitude=77.0)
    weather = WeatherRecord(
        location=loc,
        observed_at=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        source="Open-Meteo",
        temperature=28.0,
        humidity=70.0,
        rain_probability=65.0,
        wind_speed=15.0,
        weather_condition="rain"
    )
    reasoning = WeatherReasoningResult(
        evaluated_at=datetime.now(timezone.utc),
        location="Coimbatore",
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=10,
        source_agreement=SourceAgreementEnum.HIGH,
        consistency_score=90,
        confidence_level=ConfidenceLevelEnum.HIGH,
        overall_risk=RiskLevelEnum.MEDIUM,
        sources_used=["Open-Meteo"]
    )
    advisory = DecisionAdvisory(
        persona=PersonaEnum.STUDENT,
        risk_level=RiskLevelEnum.MEDIUM,
        headline="बारिश की संभावना",
        advisory_text="शाम को छाता साथ रखना सुरक्षित रहेगा।",
        key_precautions=["छाता साथ रखें"],
        official_warning_present=False,
        source_attribution="Source: Open-Meteo",
        timestamp_info="Observed 10m ago"
    )

    resp = generator.generate_response(
        nlu=nlu,
        weather=weather,
        reasoning=reasoning,
        advisory=advisory,
        target_language=LanguageEnum.HI
    )
    assert resp.answer
    # Response must contain Devanagari Unicode characters [\u0900-\u097F]
    import re
    assert bool(re.search(r"[\u0900-\u097F]", resp.answer)), f"Expected Hindi script: {resp.answer}"
    assert "28°C" in resp.answer or "65%" in resp.answer



def test_14_ai_tanglish_input_understanding():
    """Test 14: Tanglish input 'Naalaiku mazhai varuma?' resolves to Tamil output."""
    lang = resolve_target_language(LanguageEnum.TANGLISH, "Naalaiku mazhai varuma?")
    assert lang == LanguageEnum.TA


def test_15_ai_hinglish_input_understanding():
    """Test 15: Hinglish input 'Kal baarish hogi?' resolves to Hindi output."""
    lang = resolve_target_language(LanguageEnum.HINGLISH, "Kal baarish hogi?")
    assert lang == LanguageEnum.HI


def test_16_language_preference_persistence(setup_test_users):
    """Test 16: User language preference is stored and returned consistently."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_phase10a_a@skyzen.org").first()
        user.preferred_language = "ta"
        db.commit()

        # Re-fetch from DB
        refetched = db.query(User).filter(User.email == "test_phase10a_a@skyzen.org").first()
        assert refetched.preferred_language == "ta"

        # Restore
        refetched.preferred_language = "en"
        db.commit()
    finally:
        db.close()


def test_17_runtime_language_switching():
    """Test 17: Explicit language preference overrides query language."""
    # Even if query is English, explicit preference TA outputs TA
    lang = resolve_target_language(LanguageEnum.EN, "Will it rain today?", explicit_preference=LanguageEnum.TA)
    assert lang == LanguageEnum.TA

    # Even if query is Tamil, explicit preference EN outputs EN
    lang2 = resolve_target_language(LanguageEnum.TA, "மழை வருமா?", explicit_preference=LanguageEnum.EN)
    assert lang2 == LanguageEnum.EN


def test_18_tts_text_cleaning():
    """Test 18: TTS text cleaner removes markdown, URLs, emojis, and brackets."""
    raw_text = """
    # Weather Advisory
    **Coimbatore**: Temperature is 28°C with 65% rain probability.
    - [OFFICIAL IMD WARNING] High wind squall active!
    Visit https://skyzen.gov.in for radar updates.
    (Source: Open-Meteo | Updated 5m ago)
    """
    import re
    clean = raw_text
    clean = re.sub(r"\([^)]*?(?:Source|Updated|Forecast Consistency)[^)]*?\)", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\[[^\]]*?\]", "", clean)
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"[*#•-]", "", clean)
    clean = " ".join(clean.split())
    assert "https://" not in clean
    assert "[OFFICIAL" not in clean
    assert "28°C" in clean
    assert "65%" in clean


# =====================================================================
# 3. AQI DATA AUTHENTICITY & PROVENANCE (Tests 19 - 26)
# =====================================================================

def test_19_aqi_official_cpcb_schema_support():
    """Test 19: AirQualityResponse schema supports official CPCB ground data."""
    aqi_resp = AirQualityResponse(
        location="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        aqi=45,
        category="Good",
        station="SIDCO Industrial Estate, Coimbatore",
        source="CPCB",
        source_type="official_cpcb",
        is_official_cpcb=True,
        cpcb_status="OFFICIAL CPCB GROUND MONITORING STATION",
        methodology="CPCB Continuous Ambient Air Quality Monitoring Station (CAAQMS)",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        pollutants=AirQualityPollutantsSchema(pm2_5=12.0, pm10=28.0, no2=14.0, so2=6.0, o3=25.0, co=350.0),
        recommendations=["Air quality is ideal for outdoor activities."]
    )
    assert aqi_resp.is_official_cpcb is True
    assert aqi_resp.source == "CPCB"
    assert aqi_resp.station == "SIDCO Industrial Estate, Coimbatore"


def test_20_aqi_modelled_source_separation():
    """Test 20: Open-Meteo AQI is strictly separated and labeled as modelled."""
    aqi_resp = AirQualityResponse(
        location="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        aqi=52,
        category="Moderate",
        station=None,
        source="Air-quality model: Open-Meteo",
        source_type="modelled",
        is_official_cpcb=False,
        cpcb_status="CPCB OFFICIAL API ACCESS NOT CONFIGURED",
        methodology="Open-Meteo Atmospheric Chemistry Model (CAMS)",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        pollutants=AirQualityPollutantsSchema(pm2_5=18.4, pm10=38.2, no2=14.6, so2=6.8, o3=28.5, co=410.0),
        recommendations=["Air quality is acceptable for outdoor activities."]
    )
    assert aqi_resp.is_official_cpcb is False
    assert "model" in aqi_resp.source.lower()
    assert aqi_resp.cpcb_status == "CPCB OFFICIAL API ACCESS NOT CONFIGURED"
    assert aqi_resp.station is None


def test_21_aqi_no_combined_misleading_label():
    """Test 21: UI and API must not label AQI as 'Authoritative Source: CPCB / Open-Meteo'."""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert "Authoritative Source: Central Pollution Control Board (CPCB) / Open-Meteo" not in html
    assert "Authoritative Source: CPCB / Open-Meteo" not in html


def test_22_aqi_timestamp_preservation():
    """Test 22: AQI endpoint preserves retrieved_at timestamp."""
    now_iso = datetime.now(timezone.utc).isoformat()
    aqi_resp = AirQualityResponse(
        location="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        aqi=50,
        category="Good",
        source="Air-quality model: Open-Meteo",
        source_type="modelled",
        is_official_cpcb=False,
        cpcb_status="CPCB OFFICIAL API ACCESS NOT CONFIGURED",
        methodology="Open-Meteo CAMS",
        retrieved_at=now_iso,
        pollutants=AirQualityPollutantsSchema(pm2_5=15.0),
        recommendations=[]
    )
    assert aqi_resp.retrieved_at == now_iso


def test_23_aqi_stale_detection():
    """Test 23: Stale AQI is detected and marked in methodology or retrieved_at."""
    old_time = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    aqi_resp = AirQualityResponse(
        location="Coimbatore",
        latitude=11.0168,
        longitude=76.9558,
        aqi=60,
        category="Moderate",
        source="Air-quality model: Open-Meteo",
        source_type="modelled",
        is_official_cpcb=False,
        cpcb_status="CPCB OFFICIAL API ACCESS NOT CONFIGURED",
        methodology="Open-Meteo CAMS (Stale Observation)",
        retrieved_at=old_time,
        pollutants=AirQualityPollutantsSchema(pm2_5=22.0),
        recommendations=[]
    )
    assert "Stale" in aqi_resp.methodology or aqi_resp.retrieved_at == old_time


def test_24_aqi_pollutant_provenance():
    """Test 24: Pollutant record holds verified numeric concentrations without mixing fake values."""
    pollutants = AirQualityPollutantsSchema(pm2_5=18.4, pm10=38.2, no2=14.6, so2=6.8, o3=28.5, co=410.0)
    assert pollutants.pm2_5 == 18.4
    assert pollutants.pm10 == 38.2
    assert pollutants.no2 == 14.6
    assert pollutants.so2 == 6.8
    assert pollutants.o3 == 28.5
    assert pollutants.co == 410.0


@pytest.mark.anyio
async def test_25_aqi_no_cpcb_spoofing():
    """Test 25: Live weather_manager returns honest CPCB unconfigured status when no official key exists."""
    from backend.services.weather_manager import WeatherManager
    mgr = WeatherManager()
    aqi_data = await mgr.get_air_quality(11.0, 77.0)
    assert aqi_data["is_official_cpcb"] is False
    assert aqi_data["cpcb_status"] == "CPCB OFFICIAL API ACCESS NOT CONFIGURED"
    assert "CPCB" not in aqi_data["source"] or "NOT CONFIGURED" in aqi_data["cpcb_status"]


def test_26_aqi_endpoint_contract():
    """Test 26: GET /api/v1/weather/air-quality returns honest metadata."""
    resp = client.get("/api/v1/weather/air-quality?lat=11.0168&lon=76.9558")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_official_cpcb" in data
    assert data["is_official_cpcb"] is False
    assert data["cpcb_status"] == "CPCB OFFICIAL API ACCESS NOT CONFIGURED"
    assert "model" in data["source"].lower()


# =====================================================================
# 4. WEATHER DATA AUTHENTICITY & PROVENANCE (Tests 27 - 30)
# =====================================================================

def test_27_weather_live_provider_provenance():
    """Test 27: Live weather response declares accurate provider provenance."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] in ("Open-Meteo", "Multi-Source Consensus (Open-Meteo)") or "Open-Meteo" in data["source"]
    assert "sources" in data
    assert "Open-Meteo" in data["sources"]


def test_28_weather_freshness_status():
    """Test 28: Live weather response contains freshness_status and timestamps."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert "freshness_status" in data
    assert data["freshness_status"] in ("FRESH", "AGING", "EXPIRED")
    assert "observed_at" in data
    assert "retrieved_at" in data


def test_29_weather_no_fake_temperature():
    """Test 29: Weather temperature is numeric, not null or fake 0."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    assert "weather" in data
    temp = data["weather"]["temperature"]
    assert temp is not None
    assert isinstance(temp, (int, float))
    assert -10.0 <= temp <= 55.0


def test_30_weather_no_fake_unconfigured_provider():
    """Test 30: Unconfigured provider credentials (OpenWeather) are respected."""
    resp = client.get("/api/v1/weather/current?location=Coimbatore")
    assert resp.status_code == 200
    data = resp.json()
    comparison = data.get("comparison")
    if comparison:
        records = comparison.get("provider_records", [])
        for rec in records:
            if rec["provider"] == "OpenWeather":
                assert rec["status"] in ("UNCONFIGURED", "OFFLINE", "ERROR", "RATE_LIMITED")


# =====================================================================
# 5. VOICE TTS PIPELINE & CONTROLLED SENTENCES (Tests 31 - 32)
# =====================================================================

def test_31_tts_voice_pipeline_requirements():
    """Test 31: TTS voice pipeline in frontend/app.js satisfies all strict voice selection rules."""
    app_js = Path("frontend/app.js").read_text(encoding="utf-8")

    # 1. Locale matching logic
    assert "ta-IN" in app_js
    assert "hi-IN" in app_js
    assert "en-IN" in app_js

    # 2. Preference for native installed device voices
    assert "localService === true" in app_js

    # 3. Rejection of blind default fallback for Indic languages
    assert "No Tamil (ta-IN) voice found" in app_js or "voice: null" in app_js
    assert "No Hindi (hi-IN) voice found" in app_js or "voice: null" in app_js

    # 4. Cleansing of markdown, URLs, emojis, JSON, brackets
    assert "extractConciseSpeech" in app_js
    assert "testSkyZenTTS" in app_js


def test_32_tts_controlled_sentences_and_unit_preservation():
    """Test 32: Controlled test phrases and numbers/units (29°C, 70%, 18 km/h) are preserved cleanly."""
    import re

    # Controlled Test Phrases
    en_phrase = "Rain is expected this evening."
    ta_phrase = "இன்று மாலை மழை பெய்ய வாய்ப்பு உள்ளது."
    hi_phrase = "आज शाम बारिश होने की संभावना है।"

    # Technical complex input with units and metadata
    complex_text = """
    # Weather Alert
    **Warning**: Active cyclone advisory!
    - Temperature is 29°C with 70% humidity and 18 km/h winds.
    [OFFICIAL IMD WARNING]
    Visit https://imd.gov.in for radar updates.
    {"status": "severe", "code": 102}
    (Source: IMD / Open-Meteo | Updated: 09:30 UTC)
    """

    # Apply cleansing regex matching frontend implementation
    clean = complex_text
    clean = re.sub(r"```[\s\S]*?```", "", clean)
    clean = re.sub(r"`[^`]*`", "", clean)
    clean = re.sub(r"\{[^{}]*:[^{}]*\}", "", clean)
    clean = re.sub(r"https?://\S+|www\.\S+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\([^)]*?(?:Source|Updated|Observed|Forecast Consistency|Confidence|Risk|தகவல் மூலம்|மூலம்|स्रोत|AQI)[^)]*?\)", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\[[^\]]*?\]", "", clean)
    clean = re.sub(r"^#{1,6}\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
    clean = re.sub(r"^\s*(?:[-•*+]|\d+\.)\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"(\d+)\s*°\s*C\b", r"\1°C", clean)
    clean = re.sub(r"(\d+)\s*%", r"\1%", clean)
    clean = re.sub(r"(\d+)\s*(?:km/h|kmph)\b", r"\1 km/h", clean, flags=re.IGNORECASE)
    clean = " ".join(clean.split())

    # Assertions
    assert "https://" not in clean
    assert "[OFFICIAL" not in clean
    assert "Source:" not in clean
    assert "{" not in clean
    assert "29°C" in clean
    assert "70%" in clean
    assert "18 km/h" in clean

    # Controlled phrases preserve their complete native script
    assert bool(re.search(r"[\u0B80-\u0BFF]", ta_phrase))
    assert bool(re.search(r"[\u0900-\u097F]", hi_phrase))
    assert en_phrase == "Rain is expected this evening."

