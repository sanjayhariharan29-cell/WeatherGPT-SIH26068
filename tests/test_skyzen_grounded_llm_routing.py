"""Comprehensive Test Suite for SkyZen Grounded LLM Provider Routing.

Validates:
1. LLM Provider abstraction (BaseLLMProvider, GeminiLLMProvider, GroqLLMProvider, RoutingLLMProvider).
2. Multi-provider routing and sequential failover (Primary -> Secondary -> Deterministic Fallback).
3. Secret redaction and credential safety (no raw keys in repr, logs, or exceptions).
4. Structured grounded context partition into 6 distinct sections:
   - [VERIFIED WEATHER EVIDENCE]
   - [OFFICIAL WARNINGS]
   - [DETERMINISTIC DECISION]
   - [USER CONTEXT]
   - [CONVERSATION CONTEXT]
   - [UNCERTAINTY & DATA UNAVAILABILITY]
5. Strict negative constraint enforcement (no invented numbers, no fake alerts, no decision overrides).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch
import pytest

from ai.config.settings import LLMConfig
from ai.llm.provider import (
    BaseLLMProvider,
    GeminiLLMProvider,
    GroqLLMProvider,
    RoutingLLMProvider,
    MockLLMProvider,
    get_llm_provider,
)
from ai.llm.context_builder import build_grounded_context
from ai.llm.generator import GroundedLLMGenerator
from ai.llm.prompts import SYSTEM_INSTRUCTION
from ai.models import (
    ForecastItem,
    HazardDetection,
    LanguageEnum,
    LocationInfo,
    NLUResult,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.decision import DecisionEngine, PersonalDecisionEngine


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def sample_weather():
    return WeatherRecord(
        location=LocationInfo(name="Madurai", latitude=9.9252, longitude=78.1198),
        observed_at=datetime.now(timezone.utc),
        temperature=31.5,
        humidity=65.0,
        rain_probability=20.0,
        rainfall_amount_mm=0.0,
        wind_speed=14.0,
        weather_condition="Partly Cloudy",
        retrieved_at=datetime.now(timezone.utc),
        source="IMD",
    )


@pytest.fixture
def sample_forecast():
    return [
        ForecastItem(
            time="14:00",
            temperature=33.0,
            rain_probability=25.0,
            condition="Partly Cloudy",
            wind_speed=15.0,
        ),
        ForecastItem(
            time="18:00",
            temperature=29.0,
            rain_probability=60.0,
            condition="Scattered Showers",
            wind_speed=18.0,
        ),
    ]


@pytest.fixture
def sample_reasoning(sample_weather, sample_forecast):
    from ai.reasoner import WeatherReasoner
    return WeatherReasoner.evaluate(sample_weather, forecast=sample_forecast)


@pytest.fixture
def sample_advisory(sample_reasoning):
    return DecisionEngine.generate_advisory(sample_reasoning)


# =====================================================================
# 1. Secret Redaction and Credential Safety
# =====================================================================

class TestSecretRedaction:
    def test_llm_config_redacts_api_keys(self):
        cfg = LLMConfig(
            provider="gemini",
            api_key="SUPER_SECRET_GEMINI_KEY_12345",
            groq_api_key="SUPER_SECRET_GROQ_KEY_67890",
        )
        repr_str = repr(cfg)
        str_str = str(cfg)

        # Raw keys MUST NOT be present in string representations
        assert "SUPER_SECRET_GEMINI_KEY_12345" not in repr_str
        assert "SUPER_SECRET_GROQ_KEY_67890" not in repr_str
        assert "SUPER_SECRET_GEMINI_KEY_12345" not in str_str
        assert "SUPER_SECRET_GROQ_KEY_67890" not in str_str

        # Redacted tokens must appear
        assert "***REDACTED***" in repr_str
        assert cfg.api_key == "SUPER_SECRET_GEMINI_KEY_12345"
        assert cfg.groq_api_key == "SUPER_SECRET_GROQ_KEY_67890"

    def test_groq_provider_does_not_leak_key_in_repr(self):
        groq_p = GroqLLMProvider(api_key="gsk_secret_12345", model="llama-3.3-70b-versatile")
        assert "gsk_secret_12345" not in repr(groq_p)
        assert groq_p.name == "groq"

    def test_gemini_provider_does_not_leak_key_in_repr(self):
        gemini_p = GeminiLLMProvider(api_key="AIzaSy_secret_67890", model="gemini-2.5-flash")
        assert "AIzaSy_secret_67890" not in repr(gemini_p)
        assert gemini_p.name == "gemini"


# =====================================================================
# 2. Multi-Provider Routing and Failover
# =====================================================================

class TestProviderRoutingFailover:
    def test_primary_provider_success(self):
        p1 = MockLLMProvider(canned_response="Primary answer from Gemini.")
        p1.name = "gemini"
        p2 = MockLLMProvider(canned_response="Secondary answer from Groq.")
        p2.name = "groq"

        router = RoutingLLMProvider(providers=[p1, p2])
        ans = router.generate_text("System", "User")

        assert ans == "Primary answer from Gemini."
        assert router.last_provider_used == "gemini"

    def test_primary_fails_secondary_succeeds(self):
        p1 = MockLLMProvider(should_fail=True)
        p1.name = "gemini"
        p2 = MockLLMProvider(canned_response="Fallback response from Groq.")
        p2.name = "groq"

        router = RoutingLLMProvider(providers=[p1, p2])
        ans = router.generate_text("System", "User")

        assert ans == "Fallback response from Groq."
        assert router.last_provider_used == "groq"

    def test_primary_timeout_secondary_succeeds(self):
        p1 = MockLLMProvider(simulate_timeout=True)
        p1.name = "gemini"
        p2 = MockLLMProvider(canned_response="Timely response from Groq.")
        p2.name = "groq"

        router = RoutingLLMProvider(providers=[p1, p2])
        ans = router.generate_text("System", "User")

        assert ans == "Timely response from Groq."
        assert router.last_provider_used == "groq"

    def test_all_providers_fail_triggers_routing_fallback(self):
        p1 = MockLLMProvider(should_fail=True)
        p1.name = "gemini"
        p2 = MockLLMProvider(simulate_timeout=True)
        p2.name = "groq"
        fb = MockLLMProvider(canned_response="Static safety fallback.")
        fb.name = "safety_fallback"

        router = RoutingLLMProvider(providers=[p1, p2], fallback_provider=fb)
        ans = router.generate_text("System", "User")

        assert ans == "Static safety fallback."
        assert router.last_provider_used == "safety_fallback"

    def test_generator_with_router_preserves_provider_metadata(
        self, sample_weather, sample_reasoning, sample_advisory
    ):
        nlu = parse_query("Can I travel to Madurai?")
        p1 = MockLLMProvider(should_fail=True)
        p1.name = "gemini"
        p2 = MockLLMProvider(canned_response="Yes. Weather conditions in Madurai are favorable for travel.")
        p2.name = "groq"

        router = RoutingLLMProvider(providers=[p1, p2])
        gen = GroundedLLMGenerator(provider=router)
        resp = gen.generate_response(nlu, sample_weather, sample_reasoning, sample_advisory)

        assert resp.is_fallback is False
        assert resp.provider_used == "groq"
        assert "Madurai" in resp.answer

    def test_generator_all_providers_fail_uses_deterministic_fallback(
        self, sample_weather, sample_reasoning, sample_advisory
    ):
        nlu = parse_query("Can I go to college today?")
        p1 = MockLLMProvider(should_fail=True)
        p1.name = "gemini"
        p2 = MockLLMProvider(should_fail=True)
        p2.name = "groq"

        router = RoutingLLMProvider(providers=[p1, p2])
        gen = GroundedLLMGenerator(provider=router)
        resp = gen.generate_response(nlu, sample_weather, sample_reasoning, sample_advisory)

        assert resp.is_fallback is True
        assert resp.provider_used == "deterministic_fallback"
        assert len(resp.answer) > 10


# =====================================================================
# 3. Factory Routing Configuration
# =====================================================================

class TestFactoryRouting:
    def test_factory_creates_routing_provider_with_fallbacks(self):
        cfg = LLMConfig(
            provider="gemini",
            api_key="dummy_gemini_key",
            groq_api_key="dummy_groq_key",
            fallback_provider="groq",
        )
        provider = get_llm_provider(cfg)
        assert isinstance(provider, RoutingLLMProvider)
        assert len(provider.providers) == 2
        assert provider.providers[0].name == "gemini"
        assert provider.providers[1].name == "groq"

    def test_factory_prioritizes_groq_when_configured_as_primary(self):
        cfg = LLMConfig(
            provider="groq",
            api_key="dummy_gemini_key",
            groq_api_key="dummy_groq_key",
            fallback_provider="gemini",
        )
        provider = get_llm_provider(cfg)
        assert isinstance(provider, RoutingLLMProvider)
        assert provider.providers[0].name == "groq"
        assert provider.providers[1].name == "gemini"


# =====================================================================
# 4. Structured Grounded Context: 6 Distinct Sections
# =====================================================================

class TestStructuredGroundedContext:
    def test_prompt_clearly_distinguishes_six_required_sections(
        self, sample_weather, sample_forecast, sample_reasoning, sample_advisory
    ):
        nlu = parse_query("Should I take my bike to work tomorrow?")
        context = build_grounded_context(
            nlu=nlu,
            weather=sample_weather,
            reasoning=sample_reasoning,
            advisory=sample_advisory,
            forecast=sample_forecast,
            context_summary="User asked about rain tomorrow in earlier turn."
        )

        prompt = context.formatted_prompt

        # Verify the 6 required sections are prominently demarcated
        assert "[USER CONTEXT]" in prompt
        assert "[CONVERSATION CONTEXT]" in prompt
        assert "[DETERMINISTIC DECISION]" in prompt
        assert "[OFFICIAL WARNINGS]" in prompt
        assert "[VERIFIED WEATHER EVIDENCE]" in prompt
        assert "[UNCERTAINTY & DATA UNAVAILABILITY]" in prompt

        # Verify subheaders and traceability
        assert "--- USER REQUEST (UNTRUSTED USER INPUT) ---" in prompt
        assert "--- SHORT-TERM CONVERSATIONAL CONTEXT ---" in prompt
        assert "--- DETERMINISTIC ACTION DECISION & ADVISORY ---" in prompt
        assert "--- 3. OFFICIAL IMD WARNINGS (ABSOLUTE PRIORITY) ---" in prompt
        assert "--- 1. OBSERVED FACTS (AUTHORITATIVE SENSOR DATA) ---" in prompt
        assert "--- 2. SHORT-TERM FORECAST FACTS ---" in prompt
        assert "--- 5. DATA QUALITY, FRESHNESS & FORECAST CONSISTENCY ---" in prompt

    def test_uncertainty_and_unavailability_section_marks_missing_data(
        self, sample_weather, sample_reasoning, sample_advisory
    ):
        nlu = parse_query("What is the temperature?")
        weather_no_temp = sample_weather.model_copy(update={"temperature": None})
        sample_reasoning.missing_fields = ["temperature_c"]

        context = build_grounded_context(
            nlu=nlu,
            weather=weather_no_temp,
            reasoning=sample_reasoning,
            advisory=sample_advisory
        )

        prompt = context.formatted_prompt
        assert "[UNCERTAINTY & DATA UNAVAILABILITY]" in prompt
        assert "temperature_c" in prompt
        assert "Current Temperature: UNAVAILABLE" in prompt


# =====================================================================
# 5. Strict Negative Constraints Invariants
# =====================================================================

class TestNegativeConstraintsInvariants:
    def test_negative_constraints_present_in_prompt_and_system_instruction(
        self, sample_weather, sample_reasoning, sample_advisory
    ):
        nlu = parse_query("Can I go outside?")
        context = build_grounded_context(
            nlu=nlu,
            weather=sample_weather,
            reasoning=sample_reasoning,
            advisory=sample_advisory
        )

        prompt = context.formatted_prompt

        # Prompt must contain the 7 strict negative constraints
        assert "STRICT NEGATIVE CONSTRAINTS (GROUNDED SAFETY INVARIANTS):" in prompt
        assert "The LLM must NOT invent weather values" in prompt
        assert "The LLM must NOT invent warnings" in prompt
        assert "The LLM must NOT override deterministic decisions" in prompt
        assert "The LLM must NOT assume missing location" in prompt
        assert "The LLM must NOT assume missing time" in prompt
        assert "The LLM must NOT turn unavailable data into facts" in prompt
        assert "The LLM must NOT fabricate source identity" in prompt

        # SYSTEM_INSTRUCTION must also contain Rule 12 with all 7 constraints
        assert "12. STRICT NEGATIVE CONSTRAINTS (GROUNDED SAFETY INVARIANTS):" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT invent weather values" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT invent warnings or alerts" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT override deterministic decisions" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT assume missing location" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT assume missing time" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT turn unavailable data into facts" in SYSTEM_INSTRUCTION
        assert "The LLM must NOT fabricate source identity" in SYSTEM_INSTRUCTION

    def test_llm_hallucinating_unverified_warning_triggers_guard_fallback(
        self, sample_weather, sample_reasoning, sample_advisory
    ):
        nlu = parse_query("Is there an alert?")
        # LLM invents a Cyclone Warning when none is active
        invented_warning_response = "Warning: A Cyclone Warning has been issued for Madurai."
        provider = MockLLMProvider(canned_response=invented_warning_response)
        generator = GroundedLLMGenerator(provider=provider)

        resp = generator.generate_response(nlu, sample_weather, sample_reasoning, sample_advisory)

        # Must be rejected by grounding guard and fall back to deterministic response
        assert resp.is_fallback is True
        assert resp.provider_used == "deterministic_fallback"
