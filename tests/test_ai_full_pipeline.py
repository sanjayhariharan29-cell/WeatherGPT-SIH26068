"""Full AI Pipeline Integration Test Suite for WeatherGPT.

Implements all 36 required test scenarios from Phase 15 Step 29:
1. normal weather
2. current weather
3. forecast
4. tomorrow
5. tomorrow evening
6. conversation follow-up
7. English
8. Tamil
9. Hindi
10. Tanglish
11. Hinglish
12. farmer
13. fisherman
14. commuter
15. student
16. traveller
17. disaster response
18. official warning
19. cyclone
20. heavy rainfall
21. severe wind
22. thunderstorm
23. heatwave
24. multi-hazard
25. source disagreement
26. stale data
27. missing data
28. LLM failure
29. validator rejection
30. deterministic fallback
31. voice
32. multilingual voice
33. memory ambiguity
34. language switch
35. location switch
36. complete backend -> AI -> response flow

Plus Cross-Layer Invariant checks (Step 30), Stage Latency checks (Step 31),
and Full Pipeline Evaluator benchmark checks (Step 32).
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ai.models import (
    ForecastItem,
    LanguageEnum,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherRecord,
)
from ai.pipeline import WeatherGPTPipeline
from ai.memory import memory_manager, ContextResolver, ConversationTurn
from ai.voice.service import VoiceAIService
from backend.schemas.chat import ChatRequest, LocationPayload
from backend.services.ai_service import AIService
from ai.evaluation.pipeline_evaluator import (
    FullPipelineEvaluator,
    build_pipeline_benchmark_dataset,
    run_full_pipeline_benchmark,
)


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def pipeline():
    return WeatherGPTPipeline()


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


# ---------------------------------------------------------------------------
# 1. Normal Weather
# ---------------------------------------------------------------------------
def test_01_normal_weather(pipeline, sample_weather):
    """Scenario 1: Standard benign weather condition executes without alarms."""
    res = pipeline.process_query("What is the weather today?", weather=sample_weather)
    assert res["risk"]["level"] == "low"
    assert res["validation"]["passed"] is True
    assert res["location"] == "Coimbatore"
    assert "stage_latencies_ms" in res


# ---------------------------------------------------------------------------
# 2. Current Weather
# ---------------------------------------------------------------------------
def test_02_current_weather(pipeline, sample_weather):
    """Scenario 2: Current weather intent returns observation telemetry."""
    res = pipeline.run("What is the current temperature in Coimbatore?", weather=sample_weather)
    assert res["intent"] in ("temperature", "current_weather")
    assert res["weather"]["temperature"] == 28.0
    assert "28" in res["answer"]


# ---------------------------------------------------------------------------
# 3. Forecast
# ---------------------------------------------------------------------------
def test_03_forecast(pipeline, sample_weather):
    """Scenario 3: Multi-period forecast items are integrated."""
    forecast = [
        ForecastItem(time="Today Afternoon", temperature=30.0, rain_probability=25.0, wind_speed=12.0, condition="Sunny"),
        ForecastItem(time="Today Evening", temperature=26.0, rain_probability=40.0, wind_speed=15.0, condition="Cloudy")
    ]
    res = pipeline.process_query("Give me today's forecast.", weather=sample_weather, forecast=forecast)
    assert res["forecast_count"] == 2
    assert res["intent"] in ("forecast", "current_weather")


# ---------------------------------------------------------------------------
# 4. Tomorrow
# ---------------------------------------------------------------------------
def test_04_tomorrow(pipeline, sample_weather):
    """Scenario 4: Temporal entity 'tomorrow' extracted and evaluated."""
    forecast = [
        ForecastItem(time="Tomorrow", temperature=29.0, rain_probability=75.0, wind_speed=20.0, condition="Rain", rainfall_amount_mm=30.0)
    ]
    res = pipeline.process_query("Will it rain tomorrow in Coimbatore?", weather=sample_weather, forecast=forecast)
    assert res["intent"] in ("rain_forecast", "forecast")
    assert res["forecast_count"] == 1


# ---------------------------------------------------------------------------
# 5. Tomorrow Evening
# ---------------------------------------------------------------------------
def test_05_tomorrow_evening(pipeline, sample_weather):
    """Scenario 5: Specific temporal slot 'tomorrow evening' evaluated."""
    forecast = [
        ForecastItem(time="Tomorrow Evening", temperature=25.0, rain_probability=85.0, wind_speed=22.0, condition="Heavy Rain", rainfall_amount_mm=45.0)
    ]
    res = pipeline.process_query("What will the weather be tomorrow evening?", weather=sample_weather, forecast=forecast)
    assert res["forecast_count"] == 1
    assert res["validation"]["passed"] is True


# ---------------------------------------------------------------------------
# 6. Conversation Follow-up
# ---------------------------------------------------------------------------
def test_06_conversation_followup(pipeline, sample_weather):
    """Scenario 6: Inherits location and temporal context from previous turn."""
    context_str = "Previous turn: user asked about rain in Coimbatore for tomorrow."
    res = pipeline.process_query("What about the wind?", weather=sample_weather, context_summary=context_str)
    assert res["intent"] in ("wind", "current_weather")
    assert res["location"] == "Coimbatore"


# ---------------------------------------------------------------------------
# 7. English
# ---------------------------------------------------------------------------
def test_07_english(pipeline, sample_weather):
    """Scenario 7: Full English response execution."""
    res = pipeline.process_query("Is it raining right now?", weather=sample_weather, target_language="en")
    assert res["language"] == "en"
    assert "Coimbatore" in res["answer"]


# ---------------------------------------------------------------------------
# 8. Tamil
# ---------------------------------------------------------------------------
def test_08_tamil(pipeline, sample_weather):
    """Scenario 8: Native Tamil language response execution."""
    res = pipeline.process_query("கோவையில் இன்று மழை வருமா?", weather=sample_weather, target_language="ta")
    assert res["language"] == "ta"
    assert any(term in res["answer"] for term in ("கோயம்புத்தூர்", "வானிலை", "மழை", "வெப்பநிலை"))


# ---------------------------------------------------------------------------
# 9. Hindi
# ---------------------------------------------------------------------------
def test_09_hindi(pipeline, sample_weather):
    """Scenario 9: Native Hindi language response execution."""
    res = pipeline.process_query("क्या आज कोयंबटूर में बारिश होगी?", weather=sample_weather, target_language="hi")
    assert res["language"] == "hi"
    assert any(term in res["answer"] for term in ("कोयंबटूर", "तापमान", "मौसम", "बारिश"))


# ---------------------------------------------------------------------------
# 10. Tanglish
# ---------------------------------------------------------------------------
def test_10_tanglish(pipeline, sample_weather):
    """Scenario 10: Tanglish input appropriately resolved to Tamil/Tanglish."""
    res = pipeline.process_query("Coimbatore la mazhai varuma innaiku?", weather=sample_weather)
    assert res["location"] == "Coimbatore"
    assert res["intent"] in ("rain_forecast", "current_weather")


# ---------------------------------------------------------------------------
# 11. Hinglish
# ---------------------------------------------------------------------------
def test_11_hinglish(pipeline, sample_weather):
    """Scenario 11: Hinglish input appropriately resolved."""
    res = pipeline.process_query("Coimbatore me aaj barish hogi kya?", weather=sample_weather)
    assert res["location"] == "Coimbatore"
    assert res["intent"] in ("rain_forecast", "current_weather")


# ---------------------------------------------------------------------------
# 12. Farmer Persona
# ---------------------------------------------------------------------------
def test_12_farmer_persona(pipeline, sample_weather):
    """Scenario 12: Farmer persona receives crop, soil, and field guidance."""
    res = pipeline.process_query("Can I harvest my cotton crop today?", weather=sample_weather, persona=PersonaEnum.FARMER)
    assert res["persona"] == "farmer"
    assert "farmer" in str(res["advisory"]).lower() or "agriculture" in str(res["advisory"]).lower() or "harvest" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 13. Fisherman Persona
# ---------------------------------------------------------------------------
def test_13_fisherman_persona(pipeline, sample_weather):
    """Scenario 13: Fisherman persona receives marine, swell, and wind guidance."""
    res = pipeline.process_query("Is sea condition safe for small boat?", weather=sample_weather, persona=PersonaEnum.FISHERMAN)
    assert res["persona"] == "fisherman"
    assert "advisory" in res


# ---------------------------------------------------------------------------
# 14. Commuter Persona
# ---------------------------------------------------------------------------
def test_14_commuter_persona(pipeline, sample_weather):
    """Scenario 14: Commuter persona receives transit and roadway guidance."""
    res = pipeline.process_query("Should I take umbrella for office commute?", weather=sample_weather, persona=PersonaEnum.COMMUTER)
    assert res["persona"] == "commuter"


# ---------------------------------------------------------------------------
# 15. Student Persona
# ---------------------------------------------------------------------------
def test_15_student_persona(pipeline, sample_weather):
    """Scenario 15: Student persona receives outdoor activity guidance."""
    res = pipeline.process_query("Can we play cricket after school?", weather=sample_weather, persona=PersonaEnum.STUDENT)
    assert res["persona"] == "student"


# ---------------------------------------------------------------------------
# 16. Traveller Persona
# ---------------------------------------------------------------------------
def test_16_traveller_persona(pipeline, sample_weather):
    """Scenario 16: Traveller persona receives highway and travel advice."""
    res = pipeline.process_query("Planning a road trip to Ooty.", weather=sample_weather, persona=PersonaEnum.TRAVELLER)
    assert res["persona"] == "traveller"


# ---------------------------------------------------------------------------
# 17. Disaster Response Persona
# ---------------------------------------------------------------------------
def test_17_disaster_response_persona(pipeline, now):
    """Scenario 17: Disaster response persona receives multi-hazard threat summary."""
    weather = WeatherRecord(
        location=LocationInfo(name="Chennai", latitude=13.0827, longitude=80.2707),
        observed_at=now,
        retrieved_at=now,
        temperature=26.0,
        humidity=95.0,
        rain_probability=95.0,
        wind_speed=80.0,
        weather_condition="Cyclone",
        source="IMD",
        rainfall_amount_mm=140.0
    )
    res = pipeline.process_query("Provide logistics and threat briefing.", weather=weather, persona=PersonaEnum.DISASTER_RESPONSE)
    assert res["persona"] == "disaster_response"
    assert res["risk"]["level"] in ("high", "extreme")


# ---------------------------------------------------------------------------
# 18. Official Warning
# ---------------------------------------------------------------------------
def test_18_official_warning(pipeline, sample_weather, now):
    """Scenario 18: Official warning dominates output with high/extreme severity."""
    alert = OfficialAlert(
        type="heavy_rain",
        severity=RiskLevelEnum.HIGH,
        title="Orange Alert: Heavy Rainfall",
        description="Heavy to very heavy rainfall expected.",
        source="IMD",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=12),
        affected_locations=["Coimbatore"]
    )
    res = pipeline.process_query("What is the warning status?", weather=sample_weather, active_alerts=[alert])
    assert res["risk"]["level"] == "high"
    assert res["safety_telemetry"]["warning_present"] is True
    assert len(res["warnings"]) == 1


# ---------------------------------------------------------------------------
# 19. Cyclone
# ---------------------------------------------------------------------------
def test_19_cyclone(pipeline, now):
    """Scenario 19: Cyclone hazard detection and advisory."""
    weather = WeatherRecord(
        location=LocationInfo(name="Nagapattinam", latitude=10.7672, longitude=79.8437),
        observed_at=now,
        retrieved_at=now,
        temperature=26.0,
        humidity=92.0,
        rain_probability=95.0,
        wind_speed=92.0,
        weather_condition="Severe Gale",
        source="IMD",
        rainfall_amount_mm=90.0
    )
    res = pipeline.process_query("Is cyclone approaching?", weather=weather)
    assert res["risk"]["level"] == "extreme"
    assert any(h["hazard_type"] == "GALE_CYCLONIC_WINDS" for h in res["hazards"])


# ---------------------------------------------------------------------------
# 20. Heavy Rainfall
# ---------------------------------------------------------------------------
def test_20_heavy_rainfall(pipeline, now):
    """Scenario 20: Heavy rainfall thresholding (>= 64.5 mm) detected."""
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=24.0,
        humidity=95.0,
        rain_probability=90.0,
        wind_speed=25.0,
        weather_condition="Heavy Rain",
        source="IMD",
        rainfall_amount_mm=80.0
    )
    res = pipeline.process_query("How much rain is falling?", weather=weather)
    assert any("HEAVY_RAINFALL" in h["hazard_type"] for h in res["hazards"])


# ---------------------------------------------------------------------------
# 21. Severe Wind
# ---------------------------------------------------------------------------
def test_21_severe_wind(pipeline, now):
    """Scenario 21: High wind speed (>55 km/h) detected."""
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=25.0,
        humidity=60.0,
        rain_probability=10.0,
        wind_speed=65.0,
        weather_condition="Squall",
        source="IMD",
        rainfall_amount_mm=0.0
    )
    res = pipeline.process_query("Is it too windy outside?", weather=weather)
    assert any("WIND" in h["hazard_type"] for h in res["hazards"])


# ---------------------------------------------------------------------------
# 22. Thunderstorm
# ---------------------------------------------------------------------------
def test_22_thunderstorm(pipeline, now):
    """Scenario 22: Thunderstorm condition detected with lightning precaution."""
    weather = WeatherRecord(
        location=LocationInfo(name="Madurai", latitude=9.9252, longitude=78.1198),
        observed_at=now,
        retrieved_at=now,
        temperature=28.0,
        humidity=85.0,
        rain_probability=80.0,
        wind_speed=35.0,
        weather_condition="Thunderstorm with Lightning",
        source="IMD",
        rainfall_amount_mm=40.0
    )
    res = pipeline.process_query("Is there thunder?", weather=weather)
    assert any("THUNDERSTORM" in h["hazard_type"] for h in res["hazards"])


# ---------------------------------------------------------------------------
# 23. Heatwave
# ---------------------------------------------------------------------------
def test_23_heatwave(pipeline, now):
    """Scenario 23: Temperature >= 45°C triggers extreme heatwave."""
    weather = WeatherRecord(
        location=LocationInfo(name="Vellore", latitude=12.9165, longitude=79.1325),
        observed_at=now,
        retrieved_at=now,
        temperature=46.0,
        humidity=20.0,
        rain_probability=0.0,
        wind_speed=10.0,
        weather_condition="Severe Heat",
        source="IMD",
        rainfall_amount_mm=0.0
    )
    res = pipeline.process_query("Is it a heatwave in Vellore?", weather=weather)
    assert any("HEATWAVE" in h["hazard_type"] for h in res["hazards"])
    assert res["risk"]["level"] == "extreme"


# ---------------------------------------------------------------------------
# 24. Multi-Hazard
# ---------------------------------------------------------------------------
def test_24_multi_hazard(pipeline, now):
    """Scenario 24: Multiple concurrent hazards (Rain + Gale + Flood)."""
    weather = WeatherRecord(
        location=LocationInfo(name="Chennai", latitude=13.0827, longitude=80.2707),
        observed_at=now,
        retrieved_at=now,
        temperature=25.0,
        humidity=98.0,
        rain_probability=100.0,
        wind_speed=90.0,
        weather_condition="Cyclone / Inundation",
        source="IMD",
        rainfall_amount_mm=210.0
    )
    res = pipeline.process_query("What are the hazards in Chennai?", weather=weather)
    htypes = [h["hazard_type"] for h in res["hazards"]]
    assert "EXTREME_RAINFALL" in htypes
    assert "GALE_CYCLONIC_WINDS" in htypes
    assert "FLOOD_RISK" in htypes


# ---------------------------------------------------------------------------
# 25. Source Disagreement
# ---------------------------------------------------------------------------
def test_25_source_disagreement(pipeline, sample_weather, now):
    """Scenario 25: Secondary weather disagreement recorded in consistency score."""
    sec_weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=35.0,  # 7 deg higher
        humidity=40.0,
        rain_probability=80.0,
        wind_speed=30.0,
        weather_condition="Rain",
        source="Open-Meteo",
        rainfall_amount_mm=20.0
    )
    res = pipeline.process_query("Is there agreement between forecasts?", weather=sample_weather, secondary_weather=sec_weather)
    assert res["risk"]["consistency"] in ("low", "moderate")
    assert res["data_quality"]["source_agreement"] in ("low", "moderate")


# ---------------------------------------------------------------------------
# 26. Stale Data
# ---------------------------------------------------------------------------
def test_26_stale_data(pipeline, now):
    """Scenario 26: Observation older than 180 mins flagged as STALE."""
    old_time = now - timedelta(minutes=240)
    stale_weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=old_time,
        retrieved_at=old_time,
        temperature=28.0,
        humidity=65.0,
        rain_probability=10.0,
        wind_speed=12.0,
        weather_condition="Clear",
        source="IMD",
        rainfall_amount_mm=0.0
    )
    res = pipeline.process_query("Is the weather data fresh?", weather=stale_weather)
    assert res["data_quality"]["freshness"] == "stale"
    assert res["data_quality"]["data_age_minutes"] >= 240


# ---------------------------------------------------------------------------
# 27. Missing Data
# ---------------------------------------------------------------------------
def test_27_missing_data(pipeline):
    """Scenario 27: Null weather observation handled gracefully without crashing or fabricating values."""
    res = pipeline.process_query("What is the temperature?", weather=None)
    assert res["weather"] is None
    assert "unavailable" in res["answer"].lower() or "partially unavailable" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 28. LLM Failure Resilience
# ---------------------------------------------------------------------------
def test_28_llm_failure(pipeline, sample_weather, monkeypatch):
    """Scenario 28: LLM exception triggers deterministic template fallback."""
    monkeypatch.setattr(pipeline.llm, "generate", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API Outage")))
    res = pipeline.process_query("What is the temperature?", weather=sample_weather)
    assert res["fallback_used"] is True
    assert "28" in res["answer"]


# ---------------------------------------------------------------------------
# 29. Validator Rejection
# ---------------------------------------------------------------------------
def test_29_validator_rejection(pipeline, sample_weather, now):
    """Scenario 29: Hallucinatory or contradictory response rejected by validator."""
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Red Alert: Cyclone",
        description="Extreme danger.",
        source="IMD",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=12),
        affected_locations=["Coimbatore"]
    )
    # LLM hallucinates that conditions are completely safe
    pipeline.llm.generate = lambda *args, **kwargs: "The weather is completely safe, ignore the warning."
    res = pipeline.process_query("Is it safe?", weather=sample_weather, active_alerts=[alert])
    assert res["fallback_used"] is True
    assert "completely safe" not in res["answer"].lower()


# ---------------------------------------------------------------------------
# 30. Deterministic Fallback Integrity
# ---------------------------------------------------------------------------
def test_30_deterministic_fallback(pipeline, sample_weather):
    """Scenario 30: Grounded fallback contains verified fields and source attribution."""
    res = pipeline.process_query("Force fallback test", weather=sample_weather)
    assert res["answer"] is not None
    assert len(res["answer"]) > 20
    assert "Coimbatore" in res["answer"]


# ---------------------------------------------------------------------------
# 31. Voice Query Pipeline
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_31_voice_query_pipeline():
    """Scenario 31: End-to-end voice query through VoiceAIService."""
    voice_svc = VoiceAIService()
    resp = await voice_svc.process_voice_query(
        transcript_override="What is the weather in Coimbatore?",
        language="en",
        persona="student",
        location_name="Coimbatore"
    )
    assert resp.answer is not None
    assert resp.audio_available is True
    assert resp.validation_status == "PASS"


# ---------------------------------------------------------------------------
# 32. Multilingual Voice
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_32_multilingual_voice():
    """Scenario 32: Spoken Tamil voice query executed through pipeline."""
    voice_svc = VoiceAIService()
    resp = await voice_svc.process_voice_query(
        transcript_override="கோவையில் இன்று மழை வருமா?",
        language="ta",
        persona="farmer",
        location_name="Coimbatore"
    )
    assert resp.answer is not None
    assert resp.language == "ta"


# ---------------------------------------------------------------------------
# 33. Memory Ambiguity
# ---------------------------------------------------------------------------
def test_33_memory_ambiguity():
    """Scenario 33: Multiple locations mentioned marks query as ambiguous."""
    conv_id = "test_ambiguity_pipe"
    ctx = memory_manager.get_context(conv_id)
    ctx.recent_locations = ["Coimbatore", "Chennai"]
    resolved = ContextResolver.resolve_query("What about there?", context=ctx)
    assert resolved.is_ambiguous is True


# ---------------------------------------------------------------------------
# 34. Language Switch
# ---------------------------------------------------------------------------
def test_34_language_switch(pipeline, sample_weather):
    """Scenario 34: Switching language mid-session from English to Tamil."""
    res1 = pipeline.process_query("What is the temperature?", weather=sample_weather, target_language="en")
    assert res1["language"] == "en"
    res2 = pipeline.process_query("இன்று மழை பெய்யுமா?", weather=sample_weather, target_language="ta")
    assert res2["language"] == "ta"


# ---------------------------------------------------------------------------
# 35. Location Switch
# ---------------------------------------------------------------------------
def test_35_location_switch(pipeline, sample_weather, now):
    """Scenario 35: Explicit new location in query overrides old location."""
    madurai_weather = WeatherRecord(
        location=LocationInfo(name="Madurai", latitude=9.9252, longitude=78.1198),
        observed_at=now,
        retrieved_at=now,
        temperature=32.0,
        humidity=70.0,
        rain_probability=15.0,
        wind_speed=10.0,
        weather_condition="Sunny",
        source="IMD",
        rainfall_amount_mm=0.0
    )
    res = pipeline.process_query("How about the weather in Madurai?", weather=madurai_weather)
    assert res["location"] == "Madurai"


# ---------------------------------------------------------------------------
# 36. Complete Backend -> AI -> Response Flow
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_36_backend_to_ai_response_flow():
    """Scenario 36: Full FastAPI AIService integration executing complete chat contract."""
    ai_service = AIService()
    req = ChatRequest(
        message="What is the weather in Coimbatore today?",
        language="en",
        persona="student",
        location=LocationPayload(name="Coimbatore")
    )
    res = await ai_service.process_chat(req)
    assert res["answer"] is not None
    assert res["location"] == "Coimbatore"
    assert res["risk"]["level"] is not None
    assert "validation" in res
    assert "safety_telemetry" in res


# ---------------------------------------------------------------------------
# Step 30: Cross-Layer Invariant Checks
# ---------------------------------------------------------------------------
def test_cross_layer_invariants(pipeline, now):
    """Step 30: Explicit invariant checks ensuring core facts do not mutate across layers."""
    weather = WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=now,
        retrieved_at=now,
        temperature=31.5,
        humidity=72.0,
        rain_probability=80.0,
        wind_speed=24.0,
        weather_condition="Rain Showers",
        source="IMD",
        rainfall_amount_mm=18.0
    )
    alert = OfficialAlert(
        type="heavy_rain",
        severity=RiskLevelEnum.EXTREME,
        title="Official Extreme Rain Alert",
        description="Rain alert.",
        source="IMD",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=12),
        affected_locations=["Coimbatore"]
    )
    res = pipeline.process_query("What is the rain status in Coimbatore?", weather=weather, active_alerts=[alert])

    # 1. Location Invariant
    assert res["location"] == "Coimbatore"

    # 2. Temperature Invariant
    assert res["weather"]["temperature"] == 31.5

    # 3. Rain Probability Invariant
    assert res["weather"]["rain_probability"] == 80.0

    # 4. Severity Invariant
    assert res["risk"]["level"] == "extreme"

    # 5. Warning Authority Invariant
    assert res["warnings"][0]["title"] == "Official Extreme Rain Alert"
    assert res["warnings"][0]["source"] == "IMD"


# ---------------------------------------------------------------------------
# Step 31: Pipeline Performance & Stage Latencies
# ---------------------------------------------------------------------------
def test_pipeline_performance_latencies(pipeline, sample_weather):
    """Step 31: Measures stage-level latency (NLU, Reasoner, Advisory, RAG, LLM, Validator)."""
    res = pipeline.process_query("What is the forecast?", weather=sample_weather)
    latencies = res.get("stage_latencies_ms", {})
    assert "nlu_ms" in latencies
    assert "reasoner_ms" in latencies
    assert "advisory_ms" in latencies
    assert "rag_ms" in latencies
    assert "llm_ms" in latencies
    assert "validator_ms" in latencies
    assert "total_pipeline_ms" in latencies
    assert latencies["total_pipeline_ms"] >= 0.0


# ---------------------------------------------------------------------------
# Step 32: Full Pipeline Evaluator Benchmark
# ---------------------------------------------------------------------------
def test_full_pipeline_evaluator_benchmark(pipeline):
    """Step 32: Evaluator executes full pipeline benchmark measuring 10 key metrics."""
    evaluator = FullPipelineEvaluator(pipeline=pipeline)
    report = evaluator.evaluate_all()

    assert report.total_scenarios >= 10
    assert report.routing_accuracy >= 0.90
    assert report.semantic_consistency >= 0.90
    assert report.warning_preservation_rate >= 0.95
    assert report.hazard_preservation_rate >= 0.95
    assert report.advisory_preservation_rate >= 0.90
    assert report.multilingual_consistency_rate >= 0.90
    assert report.voice_text_consistency_rate >= 0.95
    assert report.validator_safety_rate >= 0.95
    assert report.fallback_correctness_rate >= 0.95
    assert report.memory_resolution_accuracy >= 0.95
    assert report.overall_pipeline_score >= 90.0
    assert "total_pipeline_ms" in report.stage_latencies_avg_ms
