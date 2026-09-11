"""Automated Verification Suite for SkyZen Personal Response Experience.

Validates that SkyZen behaves like a PERSONAL ASSISTANT, not a weather report generator:
1. Response answers the user's actual question first (Action First).
2. Response is concise (normally 1–3 short sentences).
3. Only includes weather variables relevant to the question (no telemetry dumps).
4. Never dumps decision traces, raw JSON, internal class names, or implementation terminology into answer.
5. Structured "Why this answer?" detail path (why_this_answer) is present with evidence, sources, and freshness.
6. Never fabricates missing values or claims unavailable data is available.
7. Never contradicts official IMD warnings.
8. LLM failure fallback returns natural deterministic personal assistant response.
9. Validator failure fallback returns safe deterministic response.
10. Multilingual support (English, Tamil, Hindi) produces concise, natural answers.
"""

from datetime import datetime, timezone
import pytest

from ai.models import (
    ForecastItem,
    HazardDetection,
    LanguageEnum,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    SourceAgreementEnum,
    FreshnessStatusEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.decision import (
    DecisionEngine,
    PersonalDecisionEngine,
    build_why_this_answer,
    DecisionTypeEnum,
    DecisionVerdictEnum,
)
from ai.llm.generator import GroundedLLMGenerator
from ai.pipeline import WeatherGPTPipeline
from ai.validator import ResponseValidator


def _count_sentences(text: str) -> int:
    """Helper to count sentences by punctuation marks."""
    import re
    cleaned = text.strip()
    if not cleaned:
        return 0
    sentences = [s.strip() for s in re.split(r"[.!?।]\s*", cleaned) if s.strip()]
    return len(sentences)


@pytest.fixture
def clean_reasoning():
    return WeatherReasoningResult(
        location="Coimbatore",
        evaluated_at=datetime.now(timezone.utc),
        overall_risk=RiskLevelEnum.LOW,
        source_agreement=SourceAgreementEnum.HIGH,
        data_complete=True,
        freshness=FreshnessStatusEnum.FRESH,
        data_age_minutes=5,
        consistency_score=92.0,
        sources_used=["IMD", "Open-Meteo"],
    )


@pytest.fixture
def clear_weather():
    return WeatherRecord(
        location=LocationInfo(name="Coimbatore", latitude=11.0168, longitude=76.9558),
        observed_at=datetime.now(timezone.utc),
        temperature=28.5,
        humidity=62.0,
        rain_probability=10.0,
        rainfall_amount_mm=0.0,
        wind_speed=12.0,
        weather_condition="Clear",
        retrieved_at=datetime.now(timezone.utc),
        source="IMD",
    )


@pytest.fixture
def rainy_forecast():
    return [
        ForecastItem(
            time="08:00",
            temperature=27.0,
            rain_probability=15.0,
            condition="Clear",
            wind_speed=10.0,
        ),
        ForecastItem(
            time="17:00",
            temperature=25.0,
            rain_probability=65.0,
            condition="Thunderstorm",
            rainfall_amount_mm=12.0,
            wind_speed=24.0,
        ),
    ]


class TestPersonalResponseExperience:
    """Tests evaluating concise, action-first personal assistant behavior."""

    def test_01_college_commute_action_first_and_concise(self, clear_weather, rainy_forecast):
        """User: 'Can I go to college today?' -> Answers question directly in 1-3 short sentences."""
        pipeline = WeatherGPTPipeline()
        result = pipeline.process_query(
            message="Can I go to college today?",
            weather=clear_weather,
            forecast=rainy_forecast,
            persona=PersonaEnum.STUDENT,
        )

        answer = result["answer"]
        assert len(answer) > 10
        # Brevity: 1 to 3 sentences
        sentences = _count_sentences(answer)
        assert sentences <= 3, f"Answer had {sentences} sentences (expected <= 3): {answer}"

        # Action-first check: answers about college or trip directly
        lower = answer.lower()
        assert any(k in lower for k in ["yes", "fine", "college", "trip", "morning", "go", "attend", "clear"])

        # No raw telemetry report dump in main answer
        assert "humidity" not in lower
        assert "consistency score:" not in lower
        assert "data confidence indicator:" not in lower
        assert "decisionadvisory" not in lower
        assert "personaldecisionengine" not in lower

    def test_02_bike_travel_action_first_with_relevant_rain_timing(self, clean_reasoning, clear_weather, rainy_forecast):
        """User: 'Should I take my bike?' -> 'Yes for the morning... rain risk higher at return time...'"""
        generator = GroundedLLMGenerator()
        nlu = parse_query("Should I take my bike?")

        advisory = DecisionEngine.generate_advisory(
            reasoning=clean_reasoning,
            weather=clear_weather,
            forecast=rainy_forecast,
            nlu=nlu,
            persona=PersonaEnum.COMMUTER,
        )

        answer = generator._generate_fallback(
            nlu=nlu,
            weather=clear_weather,
            reasoning=clean_reasoning,
            advisory=advisory,
        )

        # Must be 1-3 sentences
        assert _count_sentences(answer) <= 3
        lower = answer.lower()
        # Direct action and relevant rain advice
        assert any(k in lower for k in ["bike", "ride", "morning", "trip", "fine", "yes"])
        assert any(k in lower for k in ["rain", "umbrella", "gear", "evening", "return"])

        # Never dump implementation details
        assert "{" not in answer and "}" not in answer
        assert "decisiontrace" not in lower
        assert "responsereasoner" not in lower

    def test_03_will_it_rain_relevant_variables_only(self, clean_reasoning, clear_weather):
        """User: 'Will it rain?' -> Answers rain probability concisely without unsolicited telemetry."""
        generator = GroundedLLMGenerator()
        nlu = parse_query("Will it rain?")
        advisory = DecisionEngine.generate_advisory(
            reasoning=clean_reasoning,
            weather=clear_weather,
            nlu=nlu,
        )

        answer = generator._generate_fallback(
            nlu=nlu,
            weather=clear_weather,
            reasoning=clean_reasoning,
            advisory=advisory,
        )

        assert _count_sentences(answer) <= 2
        lower = answer.lower()
        # Answers rain directly
        assert "rain" in lower
        assert "unlikely" in lower or "10%" in lower or "clear" in lower

        # Does NOT dump irrelevant variables like humidity or air pressure
        assert "humidity" not in lower
        assert "hpa" not in lower
        assert "barometric" not in lower

    def test_04_no_decision_trace_or_raw_json_leaks(self, clear_weather, rainy_forecast):
        """Ensures answers NEVER leak internal terminology, class names, or decision traces."""
        pipeline = WeatherGPTPipeline()
        result = pipeline.process_query(
            message="Do I need an umbrella for my 8 AM to 5 PM classes?",
            weather=clear_weather,
            forecast=rainy_forecast,
        )

        answer = result["answer"]
        lower = answer.lower()

        forbidden_terms = [
            "decisionadvisory",
            "decisiontrace",
            "personaldecisionengine",
            "responsevalidator",
            "groundedllmgenerator",
            "risklevelenum",
            "sourceagreementenum",
            "reason_codes",
            "evidence_links",
            "observed_facts",
            "forecast consistency score: 92/100",
            "\"verdict\":",
            "\"decision_type\":",
        ]

        for term in forbidden_terms:
            assert term not in lower, f"Forbidden term '{term}' was leaked in answer: {answer}"

    def test_05_why_this_answer_structured_detail_path(self, clean_reasoning, clear_weather, rainy_forecast):
        """Verifies structured 'Why this answer?' detail path exists and contains rich evidence."""
        nlu = parse_query("Can I go to college today?")
        advisory = DecisionEngine.generate_advisory(
            reasoning=clean_reasoning,
            weather=clear_weather,
            forecast=rainy_forecast,
            nlu=nlu,
            persona=PersonaEnum.STUDENT,
        )

        why_data = build_why_this_answer(
            reasoning=clean_reasoning,
            weather=clear_weather,
            forecast=rainy_forecast,
            advisory=advisory,
            personal_decision=getattr(advisory, "personal_decision", None),
            language=LanguageEnum.EN,
        )

        assert isinstance(why_data, dict)
        assert "summary" in why_data
        assert "verdict" in why_data
        assert "primary_factors" in why_data
        assert len(why_data["primary_factors"]) > 0
        assert "evidence" in why_data
        assert "sources" in why_data
        assert "IMD" in why_data["sources"]
        assert "data_freshness" in why_data
        assert "data_age_minutes" in why_data
        assert "consistency_score" in why_data
        assert why_data["consistency_score"] == 92.0
        assert "confidence_level" in why_data
        assert why_data["confidence_level"] == "HIGH"

    def test_06_pipeline_payload_includes_why_this_answer(self, clear_weather, rainy_forecast):
        """Verifies WeatherGPTPipeline returns why_this_answer alongside concise answer."""
        pipeline = WeatherGPTPipeline()
        result = pipeline.process_query(
            message="Should I take my bike?",
            weather=clear_weather,
            forecast=rainy_forecast,
        )

        assert "why_this_answer" in result
        why = result["why_this_answer"]
        assert why is not None
        assert "summary" in why
        assert "evidence" in why
        assert "sources" in why
        assert "consistency_score" in why

        # The main answer is concise (< 3 sentences)
        assert _count_sentences(result["answer"]) <= 3

    def test_07_official_warning_prominently_acknowledged_and_not_contradicted(self, clear_weather):
        """Active official warning must be prominently stated with safety instruction."""
        now = datetime.now(timezone.utc)
        warning_alert = OfficialAlert(
            type="warning",
            severity=RiskLevelEnum.HIGH,
            title="Orange Alert - Heavy Rain & Squally Wind",
            description="Intense rainfall up to 120 mm expected in next 6 hours.",
            source="IMD",
            affected_locations=["Coimbatore"],
            issued_at=now,
            expires_at=now,
        )

        warn_reasoning = WeatherReasoningResult(
            location="Coimbatore",
            evaluated_at=now,
            overall_risk=RiskLevelEnum.HIGH,
            active_warnings=[warning_alert],
            detected_hazards=[HazardDetection(hazard_type="heavy_rain", severity=RiskLevelEnum.HIGH, details="Torrential downpour")],
            source_agreement=SourceAgreementEnum.HIGH,
            freshness=FreshnessStatusEnum.FRESH,
            data_age_minutes=5,
            consistency_score=88.0,
            sources_used=["IMD"],
        )

        nlu = parse_query("Can I go outside?")
        advisory = DecisionEngine.generate_advisory(
            reasoning=warn_reasoning,
            weather=clear_weather,
            nlu=nlu,
        )

        generator = GroundedLLMGenerator()
        ans = generator._generate_fallback(
            nlu=nlu,
            weather=clear_weather,
            reasoning=warn_reasoning,
            advisory=advisory,
        )

        # Sentences <= 3
        assert _count_sentences(ans) <= 3

        # Must mention warning/alert
        lower = ans.lower()
        assert any(w in lower for w in ["warning", "alert", "orange"])
        assert "not advisable" in lower or "stay indoors" in lower or "avoid" in lower

        # Passes ResponseValidator with zero violations
        val = ResponseValidator.validate_response(
            response_text=ans,
            reasoning=warn_reasoning,
            weather=clear_weather,
            advisory=advisory,
            nlu=nlu,
        )
        assert val.is_valid is True
        assert val.warning_consistency_passed is True

    def test_08_llm_failure_returns_deterministic_personal_assistant_response(self, clear_weather):
        """When LLM provider fails, pipeline returns deterministic personal answer."""
        from ai.llm.provider import MockLLMProvider
        failing_provider = MockLLMProvider()
        failing_provider.should_fail = True
        failing_provider.failure_exception = RuntimeError("API connection timeout")

        pipeline = WeatherGPTPipeline()
        pipeline.llm.provider = failing_provider

        result = pipeline.process_query(
            message="Can I go to college today?",
            weather=clear_weather,
        )

        assert result["fallback_used"] is True
        answer = result["answer"]
        assert len(answer) > 0
        assert _count_sentences(answer) <= 3
        assert any(k in answer.lower() for k in ["yes", "fine", "college", "trip", "clear", "pleasant"])

    def test_09_validator_rejection_returns_safe_deterministic_response(self, clear_weather):
        """When generated response violates safety, validator fallback produces safe response."""
        now = datetime.now(timezone.utc)
        warning_alert = OfficialAlert(
            type="warning",
            severity=RiskLevelEnum.HIGH,
            title="Red Alert - Flash Flood Threat",
            description="Danger of flooding in low lying areas.",
            source="IMD",
            affected_locations=["Coimbatore"],
            issued_at=now,
            expires_at=now,
        )
        warn_reasoning = WeatherReasoningResult(
            location="Coimbatore",
            evaluated_at=now,
            overall_risk=RiskLevelEnum.HIGH,
            active_warnings=[warning_alert],
            detected_hazards=[HazardDetection(hazard_type="flash_flood", severity=RiskLevelEnum.HIGH, details="Dangerous flooding")],
            source_agreement=SourceAgreementEnum.HIGH,
            freshness=FreshnessStatusEnum.FRESH,
            data_age_minutes=5,
            consistency_score=85.0,
            sources_used=["IMD"],
        )

        pipeline = WeatherGPTPipeline()
        bad_response = "The weather is completely safe, no precautions needed, go have fun outside!"
        val = ResponseValidator.validate_response(
            response_text=bad_response,
            reasoning=warn_reasoning,
            weather=clear_weather,
        )
        assert val.is_valid is False
        assert val.fallback_required is True

        # Pipeline fallback generation produces safe concise response
        safe_fallback = pipeline.llm._generate_fallback(
            nlu=parse_query("Can I go out?"),
            weather=clear_weather,
            reasoning=warn_reasoning,
            advisory=DecisionEngine.generate_advisory(reasoning=warn_reasoning, weather=clear_weather),
        )
        assert any(w in safe_fallback.lower() for w in ["warning", "alert", "flood"])
        assert "safe" not in safe_fallback.lower() or "not advisable" in safe_fallback.lower()

    def test_10_multilingual_concise_personal_responses(self, clean_reasoning, clear_weather):
        """Validates concise personal assistant responses in Tamil and Hindi."""
        generator = GroundedLLMGenerator()
        nlu_ta = parse_query("இன்று நான் கல்லூரிக்கு செல்லலாமா?")
        advisory_ta = DecisionEngine.generate_advisory(
            reasoning=clean_reasoning,
            weather=clear_weather,
            nlu=nlu_ta,
            target_language=LanguageEnum.TA,
            persona=PersonaEnum.STUDENT,
        )

        ans_ta = generator._generate_fallback(
            nlu=nlu_ta,
            weather=clear_weather,
            reasoning=clean_reasoning,
            advisory=advisory_ta,
            target_language=LanguageEnum.TA,
        )

        # Tamil response must contain Tamil script, be 1-3 sentences, and directly answer
        assert any("\u0B80" <= c <= "\u0BFF" for c in ans_ta)
        assert _count_sentences(ans_ta) <= 3

        # Hindi test
        nlu_hi = parse_query("क्या मैं आज कॉलेज जा सकता हूँ?")
        advisory_hi = DecisionEngine.generate_advisory(
            reasoning=clean_reasoning,
            weather=clear_weather,
            nlu=nlu_hi,
            target_language=LanguageEnum.HI,
            persona=PersonaEnum.STUDENT,
        )

        ans_hi = generator._generate_fallback(
            nlu=nlu_hi,
            weather=clear_weather,
            reasoning=clean_reasoning,
            advisory=advisory_hi,
            target_language=LanguageEnum.HI,
        )

        assert any("\u0900" <= c <= "\u097F" for c in ans_hi)
        assert _count_sentences(ans_hi) <= 3
