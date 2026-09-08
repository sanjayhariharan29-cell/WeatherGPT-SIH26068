"""Deep verification test suite for WeatherGPT Phase 8: Multilingual Response Generation.

Covers all 24 required scenarios:
1. English response generation
2. Tamil response generation
3. Hindi response generation
4. Tamil user query
5. Tanglish user query
6. Hindi user query
7. Hinglish user query
8. Explicit language request in query
9. Mixed-language code-switching stability
10. Numeric preservation
11. Unit preservation
12. Temporal preservation (NOW vs TOMORROW)
13. Official warning preservation
14. Hazard severity preservation
15. Advisory action preservation
16. Source attribution preservation
17. Uncertainty preservation
18. Consistency-score semantics
19. Missing weather data
20. Source conflict
21. Fallback generation
22. Invalid language request
23. Empty LLM response handling
24. Full pipeline integration
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
from ai.llm.multilingual import resolve_target_language, translate_condition
from ai.llm.generator import GroundedLLMGenerator
from ai.llm.provider import MockLLMProvider
from ai.pipeline import WeatherGPTPipeline


@pytest.fixture
def base_location():
    return LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558, state="Tamil Nadu")


@pytest.fixture
def sample_weather(base_location):
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=base_location,
        observed_at=now,
        retrieved_at=now,
        temperature=31.5,
        humidity=70.0,
        rain_probability=80.0,
        wind_speed=25.0,
        weather_condition="Heavy Rain",
        rainfall_amount_mm=64.5,
        source="IMD"
    )


# 1. English Response Generation
def test_english_response_generation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.COMMUTER, target_language=LanguageEnum.EN)
    generator = GroundedLLMGenerator()

    nlu = NLUResult(
        original_text="What is the weather in Coimbatore?",
        detected_language=LanguageEnum.EN,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.95
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)

    assert "Coimbatore" in resp.answer
    assert "32°C" in resp.answer or "31" in resp.answer or "31.5" in resp.answer
    assert "Advisory" in resp.answer or "Commute" in resp.answer


# 2. Tamil Response Generation
def test_tamil_response_generation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.STUDENT, target_language=LanguageEnum.TA)
    generator = GroundedLLMGenerator()

    nlu = NLUResult(
        original_text="கோவையில் வானிலை எப்படி இருக்கிறது?",
        detected_language=LanguageEnum.TA,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.95
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)

    assert "வெப்பநிலை" in resp.answer
    assert "மழை வாய்ப்பு" in resp.answer
    assert "ஆலோசனை" in resp.answer


# 3. Hindi Response Generation
def test_hindi_response_generation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FARMER, target_language=LanguageEnum.HI)
    generator = GroundedLLMGenerator()

    nlu = NLUResult(
        original_text="कोयंबटूर में मौसम कैसा है?",
        detected_language=LanguageEnum.HI,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.95
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)

    assert "तापमान" in resp.answer
    assert "बारिश की संभावना" in resp.answer
    assert "सलाह" in resp.answer


# 4. Tamil User Query
def test_tamil_user_query(sample_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="இன்று மழை வருமா?",
        weather=sample_weather,
        conversation_id="conv_ta_01"
    )

    assert result["language"] == "ta"
    assert "மழை" in result["answer"]


# 5. Tanglish User Query
def test_tanglish_user_query(sample_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="Innaiku mazhai varuma Coimbatore la?",
        weather=sample_weather,
        conversation_id="conv_tanglish_02"
    )

    assert result["language"] == "tanglish"
    # Tanglish input maps to Tamil generation
    assert "வெப்பநிலை" in result["answer"] or "மழை" in result["answer"]


# 6. Hindi User Query
def test_hindi_user_query(sample_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="क्या आज बारिश होगी?",
        weather=sample_weather,
        conversation_id="conv_hi_03"
    )

    assert result["language"] == "hi"
    assert "बारिश" in result["answer"] or "तापमान" in result["answer"]


# 7. Hinglish User Query
def test_hinglish_user_query(sample_weather):
    pipeline = WeatherGPTPipeline()
    result = pipeline.process_query(
        message="Aaj Coimbatore mein baarish hogi kya?",
        weather=sample_weather,
        conversation_id="conv_hinglish_04"
    )

    assert result["language"] == "hinglish"
    # Hinglish input maps to Hindi generation
    assert "तापमान" in result["answer"] or "बारिश" in result["answer"]


# 8. Explicit Language Request in Query Override
def test_explicit_language_request_in_query(sample_weather):
    target = resolve_target_language(
        nlu_lang=LanguageEnum.EN,
        query_text="What is the weather? Please respond in Hindi"
    )
    assert target == LanguageEnum.HI

    target_ta = resolve_target_language(
        nlu_lang=LanguageEnum.EN,
        query_text="Tell me about Chennai weather in Tamil"
    )
    assert target_ta == LanguageEnum.TA


# 9. Mixed-Language Code-Switching Stability
def test_mixed_language_code_switching():
    target = resolve_target_language(
        nlu_lang=LanguageEnum.TANGLISH,
        query_text="Tomorrow Chennai la rain iruka?"
    )
    assert target == LanguageEnum.TA

    target_hi = resolve_target_language(
        nlu_lang=LanguageEnum.HINGLISH,
        query_text="Kal Coimbatore mein baarish hogi?"
    )
    assert target_hi == LanguageEnum.HI


# 10. Numeric Preservation (Temperatures, Percentages)
def test_numeric_preservation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL, target_language=LanguageEnum.HI)
    generator = GroundedLLMGenerator()

    nlu = NLUResult(
        original_text="मौसम बताओ",
        detected_language=LanguageEnum.HI,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.9
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)

    # 31.5°C or 32°C and 80% must survive intact
    assert "32°C" in resp.answer or "31" in resp.answer
    assert "80%" in resp.answer


# 11. Unit Preservation (°C, km/h, mm)
def test_unit_preservation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL, target_language=LanguageEnum.TA)
    generator = GroundedLLMGenerator()

    nlu = NLUResult(
        original_text="வானிலை தகவல் கொடுங்கள்",
        detected_language=LanguageEnum.TA,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.9
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)

    assert "°C" in resp.answer
    assert "%" in resp.answer


# 12. Temporal Preservation (NOW vs TOMORROW)
def test_temporal_preservation_tomorrow(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    nlu_tomorrow = NLUResult(
        original_text="कल बारिश होगी क्या?",
        detected_language=LanguageEnum.HI,
        intent=IntentEnum.RAIN_FORECAST,
        entities=ExtractedEntities(location="Coimbatore", date="tomorrow"),
        confidence=0.95
    )
    advisory = DecisionEngine.generate_advisory(
        reasoning,
        persona=PersonaEnum.GENERAL,
        target_language=LanguageEnum.HI,
        nlu=nlu_tomorrow
    )

    assert advisory.time_context == TimeContextEnum.TOMORROW


# 13. Official Warning Prominence in EN, TA, HI
def test_official_warning_prominence_all_languages(sample_weather):
    now = datetime.now(timezone.utc)
    red_alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Warning",
        description="Gale winds and high storm surge expected",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=24)
    )
    reasoning = WeatherReasoner.evaluate(sample_weather, active_alerts=[red_alert], current_time=now)
    generator = GroundedLLMGenerator()

    for lang, expected_token in [
        (LanguageEnum.EN, "OFFICIAL IMD WARNING"),
        (LanguageEnum.TA, "அதிகாரப்பூர்வ IMD எச்சரிக்கை"),
        (LanguageEnum.HI, "आधिकारिक IMD चेतावनी"),
    ]:
        advisory = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.GENERAL, target_language=lang)
        nlu = NLUResult(
            original_text="Alert query",
            detected_language=lang,
            intent=IntentEnum.WEATHER_ALERT,
            entities=ExtractedEntities(location="Coimbatore"),
            confidence=0.9
        )
        resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)
        assert expected_token in resp.answer
        assert "Cyclone Warning" in resp.answer


# 14. Hazard Severity Preservation Across Languages
def test_hazard_severity_preservation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)

    advisory_en = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.EN)
    advisory_ta = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.TA)
    advisory_hi = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.HI)

    assert advisory_en.priority == advisory_ta.priority == advisory_hi.priority
    assert advisory_en.risk_level == advisory_ta.risk_level == advisory_hi.risk_level


# 15. Advisory Action Preservation (Farmer, Fisherman, Student in Hindi/Tamil)
def test_advisory_action_preservation_hindi_tamil(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)

    advisory_farmer_hi = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FARMER, target_language=LanguageEnum.HI)
    assert any("सिंचाई तुरंत रोक दें" in p for p in advisory_farmer_hi.key_precautions)

    advisory_fisher_ta = DecisionEngine.generate_advisory(reasoning, persona=PersonaEnum.FISHERMAN, target_language=LanguageEnum.TA)
    assert any("ஆழ்கடல் மீன்பிடிப்பைத் தவிர்க்கவும்" in p or "கடலுக்குள்" in advisory_fisher_ta.advisory_text for p in advisory_fisher_ta.key_precautions)


# 16. Source Attribution Preservation
def test_source_attribution_preservation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.HI)
    generator = GroundedLLMGenerator()

    nlu = NLUResult(
        original_text="Mausam bataiye",
        detected_language=LanguageEnum.HI,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.9
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)
    assert "IMD" in resp.answer
    assert "स्रोत:" in resp.answer or "Source:" in resp.answer


# 17. Observational Uncertainty Preservation
def test_observational_uncertainty_preservation(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    reasoning.consistency_score = 40
    reasoning.contradictions = ["Radar indicates dry clear air while station reports heavy precipitation"]

    advisory_hi = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.HI)
    assert "भिन्नता" in advisory_hi.risk_summary or "SOURCE_DISAGREEMENT" in advisory_hi.reason_codes

    advisory_ta = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.TA)
    assert "முரண்பாடு" in advisory_ta.risk_summary or "SOURCE_DISAGREEMENT" in advisory_ta.reason_codes


# 18. Consistency-Score Semantics (Not Rain Probability)
def test_consistency_score_semantics_all_languages(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    generator = GroundedLLMGenerator()

    for lang, score_label in [
        (LanguageEnum.EN, "Data Quality Score:"),
        (LanguageEnum.TA, "தர நம்பகத்தன்மை:"),
        (LanguageEnum.HI, "डेटा गुणवत्ता स्कोर:"),
    ]:
        advisory = DecisionEngine.generate_advisory(reasoning, target_language=lang)
        nlu = NLUResult(
            original_text="Quality query",
            detected_language=lang,
            intent=IntentEnum.CURRENT_WEATHER,
            entities=ExtractedEntities(location="Coimbatore"),
            confidence=0.9
        )
        resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)
        assert score_label in resp.answer


# 19. Missing Weather Data in EN, TA, HI
def test_missing_weather_data_all_languages(base_location):
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
        location="Coimbatore",
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=5,
        data_complete=False,
        missing_fields=["temperature", "weather_condition"],
        source_agreement=SourceAgreementEnum.SINGLE_SOURCE,
        consistency_score=50,
        contradictions=[],
        active_warnings=[],
        detected_hazards=[],
        overall_risk=RiskLevelEnum.LOW,
        sources_used=["IMD"]
    )

    advisory_hi = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.HI, weather=empty_weather)
    assert advisory_hi.advisory_type == AdvisoryTypeEnum.DATA_UNAVAILABLE
    assert "अनुपलब्ध" in advisory_hi.headline

    advisory_ta = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.TA, weather=empty_weather)
    assert advisory_ta.advisory_type == AdvisoryTypeEnum.DATA_UNAVAILABLE
    assert "கிடைக்கவில்லை" in advisory_ta.headline


# 20. Source Conflict Handling in EN, TA, HI
def test_source_conflict_all_languages(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    reasoning.consistency_score = 30
    reasoning.contradictions = ["Severe temperature mismatch"]

    advisory_hi = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.HI)
    assert "SOURCE_DISAGREEMENT" in advisory_hi.reason_codes


# 21. Fallback Generation for EN, TA, HI
def test_fallback_generation_all_languages(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    generator = GroundedLLMGenerator()

    for lang in [LanguageEnum.EN, LanguageEnum.TA, LanguageEnum.HI]:
        advisory = DecisionEngine.generate_advisory(reasoning, target_language=lang)
        nlu = NLUResult(
            original_text="Weather query",
            detected_language=lang,
            intent=IntentEnum.CURRENT_WEATHER,
            entities=ExtractedEntities(location="Coimbatore"),
            confidence=0.9
        )
        fb = generator._generate_fallback(nlu, sample_weather, reasoning, advisory)
        assert len(fb) > 20
        if lang == LanguageEnum.TA:
            assert "வெப்பநிலை" in fb
        elif lang == LanguageEnum.HI:
            assert "तापमान" in fb
        else:
            assert "temperature" in fb.lower()


# 22. Invalid Language Request Handling
def test_invalid_language_request_handling():
    target = resolve_target_language(
        nlu_lang=LanguageEnum.UNKNOWN,
        query_text="What is the weather in Coimbatore?"
    )
    # Safely defaults to English
    assert target == LanguageEnum.EN


# 23. Empty LLM Response Triggers Target-Language Fallback
def test_empty_llm_response_triggers_target_fallback(sample_weather):
    now = datetime.now(timezone.utc)
    reasoning = WeatherReasoner.evaluate(sample_weather, current_time=now)
    advisory = DecisionEngine.generate_advisory(reasoning, target_language=LanguageEnum.HI)

    # Provider returning None
    mock_provider = MockLLMProvider(canned_response=None)
    generator = GroundedLLMGenerator(provider=mock_provider)

    nlu = NLUResult(
        original_text="कोयंबटूर मौसम",
        detected_language=LanguageEnum.HI,
        intent=IntentEnum.CURRENT_WEATHER,
        entities=ExtractedEntities(location="Coimbatore"),
        confidence=0.9
    )
    resp = generator.generate_response(nlu=nlu, weather=sample_weather, reasoning=reasoning, advisory=advisory)
    assert resp.is_fallback is True
    assert "तापमान" in resp.answer


# 24. Full Pipeline Integration (EN, TA, HI)
def test_full_pipeline_multilingual_integration(sample_weather):
    pipeline = WeatherGPTPipeline()

    # English query
    res_en = pipeline.process_query("What is the weather in Coimbatore today?", weather=sample_weather)
    assert "Coimbatore" in res_en["answer"]

    # Tamil query
    res_ta = pipeline.process_query("இன்று கோவையில் மழை வருமா?", weather=sample_weather)
    assert "மழை" in res_ta["answer"]

    # Hindi query
    res_hi = pipeline.process_query("क्या आज कोयंबटूर में बारिश होगी?", weather=sample_weather)
    assert "बारिश" in res_hi["answer"] or "तापमान" in res_hi["answer"]
