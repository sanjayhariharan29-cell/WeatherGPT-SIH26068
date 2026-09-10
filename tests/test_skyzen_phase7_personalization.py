"""SkyZen Phase 7: Smart Conversational Personalization Test Suite.

Validates:
1. All 5 Personas (Student, Farmer, Fisherman, Commuter, Disaster/Safety).
2. Schedule-based reasoning (e.g., departure 8 AM, return 5 PM; deterministic umbrella decision).
3. Follow-up question conversational context inheritance (date, location, topic, return schedule).
4. Clean context reset on demand ("reset", "start over", "clear").
5. Safety hierarchy: Official warnings ALWAYS take precedence and appear first; never overridden.
6. Fact invariance: Identical underlying weather data yields identical facts across all personas.
7. Deterministic reasoning: Core decisions (umbrella, sea venturing ban, irrigation pause) are made in code, not LLM.
8. Multilingual reasoning (English, Tamil, Hindi).
9. Conflicting data source variance handling.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

from ai.models import (
    WeatherRecord,
    ForecastItem,
    OfficialAlert,
    LocationInfo,
    PersonaEnum,
    LanguageEnum,
    AdvisoryPriorityEnum,
    AdvisoryTypeEnum,
    RiskLevelEnum,
)
from ai.reasoner.reasoner import WeatherReasoner
from ai.decision.decision_engine import DecisionEngine
from ai.pipeline import WeatherGPTPipeline
from ai.nlu import parse_query
from ai.memory.manager import ConversationMemoryManager
from ai.memory.resolver import ContextResolver
from ai.memory.models import ConversationContext, ConversationTurn


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_location(name="Coimbatore", lat=11.0168, lon=76.9558) -> LocationInfo:
    return LocationInfo(
        name=name,
        latitude=lat,
        longitude=lon,
        district="Coimbatore",
        state="Tamil Nadu"
    )

def make_weather(
    temp=29.0,
    rain_prob=20.0,
    wind=15.0,
    humidity=65.0,
    condition="Partly Cloudy",
    loc_name="Coimbatore"
) -> WeatherRecord:
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=make_location(loc_name),
        observed_at=now,
        retrieved_at=now,
        temperature=temp,
        humidity=humidity,
        rain_probability=rain_prob,
        wind_speed=wind,
        weather_condition=condition,
        source="IMD (Primary)",
        rainfall_amount_mm=0.0
    )

def make_hourly_forecast(base_time=None) -> List[ForecastItem]:
    """Generates 24-hour forecast items starting from 00:00 to 23:00 today."""
    if not base_time:
        base_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    items = []
    for h in range(24):
        item_time = base_time + timedelta(hours=h)
        # Morning dry (08:00 = 10%), Evening rain (17:00 = 65%)
        if 6 <= h <= 11:
            rain_p = 10.0
            cond = "Clear"
        elif 15 <= h <= 19:
            rain_p = 65.0
            cond = "Moderate Rain"
        else:
            rain_p = 25.0
            cond = "Partly Cloudy"

        items.append(ForecastItem(
            time=item_time.isoformat(),
            temperature=28.0 + (2.0 if 12 <= h <= 15 else -2.0),
            rain_probability=rain_p,
            weather_condition=cond,
            condition=cond,
            wind_speed=14.0
        ))
    return items


# ===========================================================================
# 1. PERSONA: STUDENT (Schedule-based reasoning & deterministic umbrella)
# ===========================================================================

class TestStudentPersonaSchedule:

    def test_student_schedule_rain_on_return_triggers_umbrella(self):
        """User leaves at 8 AM (dry) and returns at 5 PM (rain 65%) -> recommend umbrella."""
        query = "I leave for college at 8 AM and return at 5 PM."
        nlu = parse_query(query)
        assert nlu.entities.departure_time is not None
        assert nlu.entities.return_time is not None
        assert "8" in nlu.entities.departure_time
        assert "5" in nlu.entities.return_time

        weather = make_weather(temp=27.0, rain_prob=15.0)
        forecast = make_hourly_forecast()
        reasoning = WeatherReasoner.evaluate(primary_weather=weather, forecast=forecast)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.STUDENT,
            nlu=nlu,
            weather=weather,
            forecast=forecast
        )

        assert advisory.schedule_decision is not None
        sched = advisory.schedule_decision
        assert sched["has_schedule"] is True
        assert sched["recommend_umbrella"] is True
        assert "umbrella" in sched["umbrella_rationale"].lower()
        assert sched["return_prob"] >= 50.0  # evening rain
        # Key precautions should include umbrella and transit safety
        assert any("umbrella" in p.lower() for p in advisory.key_precautions)

    def test_student_dry_schedule_umbrella_not_required(self):
        """Dry conditions across both travel windows -> umbrella not strictly required."""
        query = "I leave for college at 8 AM and return at 11 AM."
        nlu = parse_query(query)
        weather = make_weather(temp=26.0, rain_prob=5.0)
        forecast = make_hourly_forecast()
        reasoning = WeatherReasoner.evaluate(primary_weather=weather, forecast=forecast)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.STUDENT,
            nlu=nlu,
            weather=weather,
            forecast=forecast
        )

        sched = advisory.schedule_decision
        assert sched is not None
        assert sched["has_schedule"] is True
        # Departure at 8 AM has 10% rain, return at 11 AM has 10% rain -> < threshold (30%)
        assert sched["recommend_umbrella"] is False
        assert "not strictly required" in sched["umbrella_rationale"].lower() or "dry" in sched["umbrella_rationale"].lower()


# ===========================================================================
# 2. PERSONA: FARMER (Agricultural weather implications)
# ===========================================================================

class TestFarmerPersona:

    def test_farmer_heavy_rain_prioritizes_irrigation_and_spraying(self):
        """Farmer receives rain -> advises suspending irrigation and postponing pesticide spraying."""
        weather = make_weather(temp=28.0, rain_prob=75.0, wind=22.0, condition="Heavy Rain")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.FARMER,
            weather=weather
        )

        assert advisory.persona == PersonaEnum.FARMER
        full_text = f"{advisory.advisory_text} {' '.join(advisory.key_precautions)}".lower()
        # Must address agricultural implications
        assert "irrigation" in full_text
        assert "spray" in full_text or "chemical" in full_text
        assert "drainage" in full_text or "runoff" in full_text

    def test_farmer_high_wind_advises_staking_crops(self):
        """Farmer high wind (> 35 km/h) -> recommends securing tall crops and pausing foliar spray."""
        weather = make_weather(temp=30.0, rain_prob=10.0, wind=42.0, condition="Windy")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.FARMER,
            weather=weather
        )

        full_text = f"{advisory.advisory_text} {' '.join(advisory.key_precautions)}".lower()
        assert "wind" in full_text
        assert "spray" in full_text or "crop" in full_text


# ===========================================================================
# 3. PERSONA: FISHERMAN (Marine warnings & sea venturing ban)
# ===========================================================================

class TestFishermanPersona:

    def test_fisherman_squall_wind_triggers_sea_ban(self):
        """Fisherman wind > 40 km/h deterministically triggers advisory not to venture into sea."""
        weather = make_weather(temp=29.0, rain_prob=60.0, wind=48.0, condition="Squally Weather")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.FISHERMAN,
            weather=weather
        )

        assert advisory.persona == PersonaEnum.FISHERMAN
        full_text = f"{advisory.headline} {advisory.advisory_text} {' '.join(advisory.key_precautions)}".lower()
        # Sea venture restriction must be explicit
        assert any(phrase in full_text for phrase in ["not venture into", "avoid venturing", "moorings", "not to venture"])
        assert "boat" in full_text or "craft" in full_text

    def test_fisherman_calm_conditions_advises_routine_caution(self):
        """Calm weather -> safe for operations while monitoring standard coastal VHF updates."""
        weather = make_weather(temp=29.0, rain_prob=5.0, wind=12.0, condition="Clear")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.FISHERMAN,
            weather=weather
        )

        full_text = f"{advisory.advisory_text} {' '.join(advisory.key_precautions)}".lower()
        assert "normal" in full_text or "favorable" in full_text or "clear" in full_text


# ===========================================================================
# 4. PERSONA: COMMUTER (Travel buffer, visibility, underpasses)
# ===========================================================================

class TestCommuterPersona:

    def test_commuter_rain_advises_buffer_time_and_underpasses(self):
        """Commuter rain scenario -> advises 20-30 min extra travel buffer and waterlogged underpass avoidance."""
        weather = make_weather(temp=26.0, rain_prob=65.0, wind=28.0, condition="Rain")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.COMMUTER,
            weather=weather
        )

        assert advisory.persona == PersonaEnum.COMMUTER
        full_text = f"{advisory.advisory_text} {' '.join(advisory.key_precautions)}".lower()
        assert "buffer time" in full_text
        assert "underpass" in full_text or "waterlogg" in full_text or "transit" in full_text


# ===========================================================================
# 5. PERSONA: DISASTER / SAFETY (Official warnings & emergency mobilization)
# ===========================================================================

class TestDisasterSafetyPersona:

    def test_disaster_safety_alert_triggers_command_posture(self):
        """Disaster response persona with active alert -> triggers standby mobilization & dewatering pumps."""
        alert = OfficialAlert(
            source="IMD",
            type="severe_storm_alert",
            severity=RiskLevelEnum.HIGH,
            title="Severe Storm Warning",
            description="Intense squall with heavy localized rainfall expected.",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=12)
        )
        weather = make_weather(temp=25.0, rain_prob=80.0, wind=45.0, condition="Heavy Rain")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather, active_alerts=[alert])

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.DISASTER_RESPONSE,
            weather=weather
        )

        assert advisory.persona == PersonaEnum.DISASTER_RESPONSE
        full_text = f"{advisory.headline} {advisory.advisory_text} {' '.join(advisory.key_precautions)}".lower()
        assert "mobiliz" in full_text or "standby" in full_text or "emergency" in full_text
        assert "pump" in full_text or "shelter" in full_text or "radar" in full_text


# ===========================================================================
# 6. SAFETY HIERARCHY: OFFICIAL WARNING ALWAYS COMES FIRST
# ===========================================================================

class TestSafetyHierarchy:

    def test_official_warning_never_overridden_by_persona(self):
        """Even for student or farmer, official warning headline MUST appear first and cannot be overridden."""
        cyclone_alert = OfficialAlert(
            source="IMD",
            type="cyclone_alert",
            severity=RiskLevelEnum.EXTREME,
            title="IMD Red Alert: Severe Cyclonic Storm",
            description="Dangerous cyclonic winds and inundation imminent. Total evacuation in low areas.",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        weather = make_weather(temp=26.0, rain_prob=95.0, wind=85.0, condition="Squall")
        reasoning = WeatherReasoner.evaluate(primary_weather=weather, active_alerts=[cyclone_alert])

        # Test across Student and Farmer personas
        for test_persona in [PersonaEnum.STUDENT, PersonaEnum.FARMER, PersonaEnum.COMMUTER]:
            advisory = DecisionEngine.generate_advisory(
                reasoning=reasoning,
                persona=test_persona,
                weather=weather
            )
            assert advisory.priority == AdvisoryPriorityEnum.CRITICAL
            assert "IMD Red Alert" in advisory.headline or "Severe Cyclonic Storm" in advisory.headline
            assert advisory.key_precautions[0].startswith("OFFICIAL WARNING") or "official warning" in advisory.key_precautions[0].lower()


# ===========================================================================
# 7. CONVERSATIONAL CONTINUITY: FOLLOW-UP QUESTIONS & RESOLVER
# ===========================================================================

class TestConversationalContinuity:

    def test_follow_up_college_departure_inherits_date_and_location(self):
        """Turn 1 establishes Coimbatore + tomorrow. Turn 2 asks about leaving college."""
        mgr = ConversationMemoryManager()
        conv_id = "test_phase7_followup"

        # Turn 1: User asks about rain tomorrow in Coimbatore
        t1_user = ConversationTurn(role="user", message="Will it rain tomorrow in Coimbatore?", location="Coimbatore")
        t1_asst = ConversationTurn(role="assistant", message="Rain is possible tomorrow in Coimbatore.", location="Coimbatore")
        mgr.update_context(
            conversation_id=conv_id,
            user_turn=t1_user,
            assistant_turn=t1_asst,
            location="Coimbatore",
            date_context="tomorrow",
            active_topic="rain",
            persona="student",
            return_time="5:00 PM"
        )

        ctx = mgr.get_context(conv_id)
        # Turn 2: Follow-up question without repeating location or date
        resolved = ContextResolver.resolve_query(
            message="What about when I leave college?",
            context=ctx
        )

        # Verifications
        assert resolved.resolved_location == "Coimbatore"
        assert resolved.resolved_date == "tomorrow"
        assert resolved.resolved_topic == "rain"
        assert "location" in resolved.inherited_fields
        assert "date_context" in resolved.inherited_fields
        assert resolved.resolved_time in ("5:00 PM", "5 PM", "17:00") or "return_time" in resolved.inherited_fields


# ===========================================================================
# 8. CONTEXT RESET: ON DEMAND ("reset" / "start over" / "clear")
# ===========================================================================

class TestContextReset:

    @pytest.mark.parametrize("reset_msg", [
        "reset",
        "please reset context",
        "start over",
        "clear context",
        "start fresh"
    ])
    def test_context_reset_clears_history(self, reset_msg):
        """Reset keywords completely detach and wipe prior context."""
        mgr = ConversationMemoryManager()
        conv_id = "test_phase7_reset"

        mgr.update_context(
            conversation_id=conv_id,
            location="Madurai",
            date_context="tomorrow",
            persona="farmer"
        )

        assert ContextResolver.is_reset_query(reset_msg) is True

        ctx = mgr.get_context(conv_id)
        resolved = ContextResolver.resolve_query(reset_msg, context=ctx)
        # After reset query, context is purged
        assert len(resolved.inherited_fields) == 0
        assert resolved.resolved_location == "Coimbatore"  # fallback default, not Madurai


# ===========================================================================
# 9. FACT INVARIANCE: WEATHER FACTS REMAIN IDENTICAL ACROSS PERSONAS
# ===========================================================================

class TestFactInvariance:

    def test_facts_identical_across_all_five_personas(self):
        """Underlying factual measurements (temperature, rain prob, wind) must NOT mutate per persona."""
        fixed_weather = make_weather(temp=31.4, rain_prob=42.0, wind=18.5, humidity=72.0, loc_name="Tiruppur")
        pipeline = WeatherGPTPipeline()

        personas = [
            PersonaEnum.STUDENT,
            PersonaEnum.FARMER,
            PersonaEnum.FISHERMAN,
            PersonaEnum.COMMUTER,
            PersonaEnum.DISASTER_RESPONSE
        ]

        results = []
        for p in personas:
            res = pipeline.process_query(
                message="What is the weather today?",
                weather=fixed_weather,
                persona=p
            )
            results.append(res)

        # Check all results share exact same factual weather summary
        first_summary = results[0]["weather"]
        for idx, res in enumerate(results[1:], start=1):
            assert res["weather"]["temperature"] == first_summary["temperature"] == 31.4
            assert res["weather"]["rain_probability"] == first_summary["rain_probability"] == 42.0
            assert res["weather"]["wind_speed"] == first_summary["wind_speed"] == 18.5
            assert res["weather"]["humidity"] == first_summary["humidity"] == 72.0
            # Decision trace also records identical factual observations
            dt = res["decision_trace"]
            assert dt["temperature"]["current_c"] == 31.4
            assert dt["rainfall_indicators"]["probability_percent"] == 42.0


# ===========================================================================
# 10. MULTILINGUAL REASONING: TAMIL AND HINDI
# ===========================================================================

class TestMultilingualPersonalization:

    def test_tamil_student_advisory(self):
        """Advisory generated in Tamil (ta) properly provides Tamil precautions."""
        weather = make_weather(temp=28.0, rain_prob=60.0)
        forecast = make_hourly_forecast()
        reasoning = WeatherReasoner.evaluate(primary_weather=weather, forecast=forecast)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.STUDENT,
            target_language=LanguageEnum.TA,
            weather=weather,
            forecast=forecast
        )

        assert advisory.language == LanguageEnum.TA
        # Should contain Tamil script characters
        tamil_char_present = any('\u0b80' <= c <= '\u0bff' for c in advisory.advisory_text)
        assert tamil_char_present is True

    def test_hindi_farmer_advisory(self):
        """Advisory generated in Hindi (hi) provides agricultural guidance in Devanagari."""
        weather = make_weather(temp=32.0, rain_prob=70.0, wind=25.0)
        reasoning = WeatherReasoner.evaluate(primary_weather=weather)

        advisory = DecisionEngine.generate_advisory(
            reasoning=reasoning,
            persona=PersonaEnum.FARMER,
            target_language=LanguageEnum.HI,
            weather=weather
        )

        assert advisory.language == LanguageEnum.HI
        # Should contain Hindi Devanagari script characters
        hindi_char_present = any('\u0900' <= c <= '\u097f' for c in advisory.advisory_text)
        assert hindi_char_present is True


# ===========================================================================
# 11. CONFLICTING DATA: SOURCE VARIANCE SAFETY MARGIN
# ===========================================================================

class TestConflictingDataSourceVariance:

    def test_source_disagreement_recorded_and_safety_margin_applied(self):
        """IMD (30°C, 20% rain) vs Open-Meteo (22°C, 80% rain) -> conservative safety margin."""
        primary = make_weather(temp=30.0, rain_prob=20.0, wind=10.0)
        secondary = make_weather(temp=22.0, rain_prob=80.0, wind=35.0)
        secondary.source = "Open-Meteo (Secondary)"

        reasoning = WeatherReasoner.evaluate(primary_weather=primary, secondary_weather=secondary)
        assert reasoning.source_agreement.value in ("moderate", "low", "divergent", "conflicting")

        pipeline = WeatherGPTPipeline()
        res = pipeline.process_query(
            message="Will it rain today?",
            weather=primary,
            secondary_weather=secondary,
            persona=PersonaEnum.COMMUTER
        )

        dt = res["decision_trace"]
        assert dt["source_agreement"] in ("moderate", "low", "divergent", "conflicting")
        # Explanation points must note variance/agreement
        assert any("agreement" in pt.lower() or "variance" in pt.lower() for pt in dt["explanation_points"])
