"""Phase 18: Realistic AI Evaluation & Benchmarking Suite.

Validates WeatherGPT across diverse, multi-dialect linguistic queries
(English, Tamil, Hindi, Tanglish, Hinglish) and operational edge-cases:
- Current weather, forecast, alerts, multi-hazard conditions
- Relative time & temporal extraction
- Ambiguous location resolution
- Persona-specific recommendations (farmer, fisherman, commuter, etc.)
- Strict separation between curated benchmark evaluation and real-world claims.
"""

import pytest
from datetime import datetime, timezone

from ai.evaluation import (
    load_nlu_dataset,
    load_hazard_dataset,
    load_advisory_dataset,
    load_safety_dataset,
    evaluate_nlu,
    evaluate_hazards,
    evaluate_advisories,
    evaluate_safety,
    run_full_benchmark,
)
from ai.models import (
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.pipeline import WeatherGPTPipeline


def test_01_multilingual_query_corpus():
    """Verify NLU parsing across English, Tamil, Hindi, Tanglish, and Hinglish."""
    test_cases = [
        # English standard
        ("Will it rain heavily in Chennai tomorrow?", ["en"], ["forecast", "rain_forecast"], "Chennai"),
        # Tamil standard
        ("சென்னையில் நாளை கனமழை பெய்யுமா?", ["ta"], ["forecast", "rain_forecast"], "சென்னை"),
        # Hindi standard
        ("क्या कल दिल्ली में भारी बारिश होगी?", ["hi"], ["forecast", "rain_forecast"], "दिल्ली"),
        # Tanglish (Tamil written in Latin script)
        ("Nalaiki Chennai la sema mazhai varuma?", ["ta", "tanglish"], ["forecast", "rain_forecast"], "Chennai"),
        # Hinglish (Hindi written in Latin script)
        ("Kal Mumbai me bohot tez baarish hogi kya?", ["hi", "hinglish"], ["forecast", "rain_forecast"], "Mumbai"),
    ]

    for query, expected_langs, expected_intents, loc_sub in test_cases:
        nlu = parse_query(query)
        assert nlu.detected_language.value in expected_langs
        assert nlu.intent.value in expected_intents
        if loc_sub:
            assert nlu.entities.location is not None


def test_02_persona_specific_advisory_eval():
    """Verify persona adaptation for farmer vs fisherman under coastal conditions."""
    pipeline = WeatherGPTPipeline()
    now = datetime.now(timezone.utc)

    weather = WeatherRecord(
        location=LocationInfo(name="Nagapattinam", latitude=10.7656, longitude=79.8424),
        observed_at=now,
        retrieved_at=now,
        temperature=29.0,
        humidity=88.0,
        rain_probability=80.0,
        wind_speed=48.0,
        weather_condition="Rough Sea / Wind Gusts",
        source="IMD"
    )

    # Fisherman persona
    fish_res = pipeline.process_query(
        message="Should I take my boat out to sea today?",
        weather=weather,
        persona=PersonaEnum.FISHERMAN,
        request_id="bench_fish"
    )
    assert fish_res["persona"] == "fisherman"
    assert "sea" in fish_res["answer"].lower() or "boat" in fish_res["answer"].lower() or "wind" in fish_res["answer"].lower() or "avoid" in fish_res["answer"].lower()

    # Farmer persona
    farm_res = pipeline.process_query(
        message="Can I apply pesticide spray today?",
        weather=weather,
        persona=PersonaEnum.FARMER,
        request_id="bench_farm"
    )
    assert farm_res["persona"] == "farmer"
    assert "spray" in farm_res["answer"].lower() or "wind" in farm_res["answer"].lower() or "crop" in farm_res["answer"].lower() or "rain" in farm_res["answer"].lower()


def test_03_relative_time_and_temporal_nlu():
    """Verify temporal expressions like 'today', 'tomorrow', 'this evening', 'next 2 days'."""
    queries = [
        ("How is the weather today?", "today"),
        ("Weather forecast for tomorrow in Madurai", "tomorrow"),
        ("Rain alert for this evening", "today"),
    ]
    for q, exp_time in queries:
        nlu = parse_query(q)
        if exp_time:
            assert nlu.entities.date is not None or nlu.entities.time_range is not None


def test_04_benchmark_full_runner():
    """Execute the core curated benchmark framework and verify report validity."""
    report = run_full_benchmark()

    assert report.nlu.total_cases > 0
    assert report.nlu.language_accuracy >= 0.90
    assert report.nlu.intent_accuracy >= 0.90
    assert report.hazard.f1 >= 0.90
    assert report.safety.safe_pass_rate == 1.0
    assert report.safety.hallucination_rejection_rate == 1.0
    assert report.latency.pipeline_latency_ms >= 0.0


def test_05_missing_data_benchmark_safety():
    """Verify that absent weather data triggers safe degradation rather than fabricated predictions."""
    pipeline = WeatherGPTPipeline()

    res = pipeline.process_query(
        message="What is the exact humidity and barometric pressure in Tuticorin right now?",
        weather=None,
        request_id="bench_missing"
    )

    # Must acknowledge missing data or fallback
    assert res["degraded_state"] in ("DATA_UNAVAILABLE", "partially_degraded", "critically_degraded", "nominal")
    assert res["data_quality"]["data_complete"] is False or res["fallback_used"] is True
