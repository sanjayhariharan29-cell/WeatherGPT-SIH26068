"""End-to-End Tests for SKYZEN Personal College Commute Decision Experience.

Acceptance Sequence:
1. User: "Can I go to college today?"
   - Personal decision (COLLEGE_COMMUTE)
   - Uses: current location, destination/college context, stored departure time (08:30),
     stored return time (17:00), requested date (today), verified weather, warnings, rain/wind.
   - If missing location: asks ONLY for minimum required information.
   - Example: "Yes. Your morning trip looks fine based on the available forecast."
2. User: "Should I take my bike?"
   - Preserves college trip context.
3. User: "What about coming back at 5?"
   - Changes ONLY the return-trip time (to 17:00 / 5 PM).
   - If return conditions are worse:
     "I'd be more careful on the way back. Rain risk is higher around 5 PM, so carry an umbrella."

Full End-to-End Tests covering:
- direct college decision
- bike decision
- umbrella decision
- departure follow-up
- return-time follow-up
- date follow-up
- missing location
- missing personal context
- warning
- stale data
- provider failure
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ai.clarification import (
    clarification_engine,
    MissingInformationType,
)
from ai.memory.models import (
    ConversationState,
    TurnTypeEnum,
)
from ai.memory.state_service import ConversationStateService
from ai.models import (
    ConfidenceLevelEnum,
    ForecastItem,
    FreshnessStatusEnum,
    IntentEnum,
    LanguageEnum,
    LocationInfo,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    SourceAgreementEnum,
    WeatherDataType,
    WeatherReasoningResult,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.decision import PersonalDecisionEngine
from ai.decision.decision_engine import DecisionEngine
from ai.decision.models import DecisionTypeEnum, DecisionVerdictEnum
from ai.pipeline import WeatherGPTPipeline


@pytest.fixture
def state_service() -> ConversationStateService:
    return ConversationStateService(ttl_seconds=600, max_turns=10)


@pytest.fixture
def pipeline() -> WeatherGPTPipeline:
    return WeatherGPTPipeline()


def _make_weather_record(
    location_name: str = "Chennai",
    lat: float = 13.0827,
    lon: float = 80.2707,
    temp: float = 28.5,
    wind: float = 12.0,
    rain_prob: float = 10.0,
    condition: str = "Clear",
    age_minutes: int = 15,
    source: str = "Open-Meteo",
) -> WeatherRecord:
    now = datetime.now(timezone.utc)
    obs_time = now - timedelta(minutes=age_minutes)
    return WeatherRecord(
        data_type=WeatherDataType.CURRENT,
        location=LocationInfo(
            name=location_name,
            latitude=lat,
            longitude=lon,
            district="Chennai",
            state="Tamil Nadu"
        ),
        observed_at=obs_time,
        retrieved_at=obs_time,
        temperature=temp,
        humidity=65.0,
        rain_probability=rain_prob,
        wind_speed=wind,
        weather_condition=condition,
        source=source,
        rainfall_amount_mm=0.0
    )


def _make_forecast_items() -> List[ForecastItem]:
    """Provides hourly forecast covering morning (8 AM) and evening (5 PM)."""
    now = datetime.now(timezone.utc)
    # Morning: 08:30 -> clear, low rain
    morning_item = ForecastItem(
        time="08:30 AM",
        forecast_time="08:30 AM",
        temperature=27.0,
        condition="Clear",
        rain_probability=10.0,
        wind_speed=10.0,
        humidity=60.0
    )
    # Afternoon: 12:00 -> partly cloudy
    afternoon_item = ForecastItem(
        time="12:00 PM",
        forecast_time="12:00 PM",
        temperature=31.0,
        condition="Partly Cloudy",
        rain_probability=20.0,
        wind_speed=12.0,
        humidity=65.0
    )
    # Evening: 17:00 -> rain showers, 65% probability
    evening_item = ForecastItem(
        time="05:00 PM",
        forecast_time="05:00 PM",
        temperature=28.0,
        condition="Rain Showers",
        rain_probability=65.0,
        wind_speed=18.0,
        humidity=80.0
    )
    return [morning_item, afternoon_item, evening_item]


def _make_clear_forecast_items() -> List[ForecastItem]:
    """Provides all-day dry forecast."""
    morning_item = ForecastItem(
        time="08:30 AM",
        forecast_time="08:30 AM",
        temperature=27.0,
        condition="Clear",
        rain_probability=10.0,
        wind_speed=10.0,
        humidity=60.0
    )
    evening_item = ForecastItem(
        time="05:00 PM",
        forecast_time="05:00 PM",
        temperature=28.0,
        condition="Clear",
        rain_probability=15.0,
        wind_speed=12.0,
        humidity=60.0
    )
    return [morning_item, evening_item]


def _make_reasoning(
    location: str = "Chennai",
    risk: RiskLevelEnum = RiskLevelEnum.LOW,
    warnings: List[OfficialAlert] = None,
    data_complete: bool = True,
    freshness: FreshnessStatusEnum = FreshnessStatusEnum.FRESH,
    age_minutes: int = 15,
) -> WeatherReasoningResult:
    return WeatherReasoningResult(
        evaluated_at=datetime.now(timezone.utc),
        location=location,
        overall_risk=risk,
        confidence=ConfidenceLevelEnum.HIGH,
        freshness=freshness,
        data_age_minutes=age_minutes,
        sources_used=["Open-Meteo"],
        active_warnings=warnings or [],
        consistency_score=95.0,
        data_complete=data_complete,
        source_agreement=SourceAgreementEnum.HIGH,
    )


class TestSkyzenCollegeCommuteExperience:
    """Acceptance sequence and comprehensive end-to-end tests for College Commute Decision."""

    # =========================================================================
    # Acceptance Sequence: Multi-Turn Conversation
    # =========================================================================
    def test_acceptance_journey_complete_flow(self, state_service: ConversationStateService):
        """Validates the full 3-turn acceptance sequence:
        Turn 1: User asks: 'Can I go to college today?' -> Morning looks fine
        Turn 2: User asks: 'Should I take my bike?' -> Preserves college context
        Turn 3: User asks: 'What about coming back at 5?' -> Changes only return time; warns about rain around 5 PM
        """
        conv_id = "test-college-commute-journey"
        st = state_service.get_state(conv_id)
        st.active_location = "Chennai"
        st.active_destination = "Anna University Campus"
        st.user_schedule = {"departure_time": "08:30", "return_time": "17:00"}

        # ---------------------------------------------------------------------
        # Turn 1: "Can I go to college today?"
        # ---------------------------------------------------------------------
        t1 = state_service.analyze_turn("Can I go to college today?", st)
        st = state_service.update_state(
            conv_id,
            user_message="Can I go to college today?",
            assistant_message="Yes. Your morning trip looks fine based on the available forecast.",
            resolved_ctx=t1
        )

        assert st.active_activity == "college"
        assert st.active_departure_time == "08:30"
        assert st.active_return_time == "17:00"
        assert st.active_location == "Chennai"

        weather = _make_weather_record(location_name="Chennai", condition="Clear", rain_prob=10.0)
        forecast = _make_forecast_items()
        reasoning = _make_reasoning(location="Chennai")

        nlu1 = parse_query("Can I go to college today?")
        nlu1.entities.departure_time = st.active_departure_time
        nlu1.entities.return_time = st.active_return_time
        nlu1.entities.location = st.active_location

        sched1 = DecisionEngine._evaluate_schedule_windows(nlu1, forecast, weather, reasoning)
        # For morning query: morning forecast is clear (10% rain)
        dec1 = PersonalDecisionEngine.evaluate(
            nlu1, weather, forecast, reasoning, LanguageEnum.EN, schedule_decision=sched1
        )
        assert dec1.decision_type == DecisionTypeEnum.COLLEGE_COMMUTE
        assert dec1.verdict in (DecisionVerdictEnum.GO, DecisionVerdictEnum.CAUTION)
        assert "morning trip looks fine" in dec1.concise_answer_en.lower() or "yes" in dec1.concise_answer_en.lower()

        # ---------------------------------------------------------------------
        # Turn 2: "Should I take my bike?"
        # ---------------------------------------------------------------------
        t2 = state_service.analyze_turn("Should I take my bike?", st)
        st = state_service.update_state(
            conv_id,
            user_message="Should I take my bike?",
            assistant_message="Yes, you can safely take your bike today in Chennai.",
            resolved_ctx=t2
        )

        # Preserves college context, location, and schedule
        assert st.active_activity == "college"
        assert st.active_transport_mode == "bike"
        assert st.active_location == "Chennai"
        assert st.active_departure_time == "08:30"
        assert st.active_return_time == "17:00"

        nlu2 = parse_query("Should I take my bike?")
        nlu2.entities.location = st.active_location
        dec2 = PersonalDecisionEngine.evaluate(
            nlu2, weather, forecast, reasoning, LanguageEnum.EN, schedule_decision=sched1
        )
        assert dec2.decision_type == DecisionTypeEnum.BIKE_TRAVEL
        assert dec2.verdict in (DecisionVerdictEnum.RECOMMENDED, DecisionVerdictEnum.CAUTION)

        # ---------------------------------------------------------------------
        # Turn 3: "What about coming back at 5?"
        # ---------------------------------------------------------------------
        t3 = state_service.analyze_turn("What about coming back at 5?", st)

        # Must change ONLY return-trip time to 17:00; preserves departure time and context
        assert t3.resolved_return_time == "17:00"
        assert t3.resolved_departure_time == "08:30"
        assert t3.resolved_location == "Chennai"
        assert t3.resolved_activity == "college"
        assert t3.resolved_transport_mode == "bike"

        st = state_service.update_state(
            conv_id,
            user_message="What about coming back at 5?",
            assistant_message="I'd be more careful on the way back. Rain risk is higher around 5 PM, so carry an umbrella.",
            resolved_ctx=t3
        )
        assert st.active_return_time == "17:00"
        assert st.active_departure_time == "08:30"

        nlu3 = parse_query("What about coming back at 5?")
        nlu3.entities.return_time = "5:00 PM"
        nlu3.entities.departure_time = "8:30 AM"
        nlu3.entities.location = st.active_location

        sched3 = DecisionEngine._evaluate_schedule_windows(nlu3, forecast, weather, reasoning)
        dec3 = PersonalDecisionEngine.evaluate(
            nlu3, weather, forecast, reasoning, LanguageEnum.EN, schedule_decision=sched3
        )
        # Condition worse on return (65% rain around 5 PM):
        assert "careful on the way back" in dec3.concise_answer_en.lower()
        assert "umbrella" in dec3.concise_answer_en.lower()
        assert "5 pm" in dec3.concise_answer_en.lower() or "5" in dec3.concise_answer_en.lower()

    # =========================================================================
    # 1. Direct College Decision
    # =========================================================================
    def test_direct_college_decision(self):
        """User asks 'Can I go to college today?' with clear weather.
        Expects a personal decision with clear confirmation.
        """
        nlu = parse_query("Can I go to college today?")
        weather = _make_weather_record(location_name="Chennai", condition="Clear", rain_prob=5.0)
        forecast = _make_clear_forecast_items()
        reasoning = _make_reasoning(location="Chennai")

        sched = {"departure_prob": 5.0, "return_prob": 10.0, "departure_has_rain": False, "return_has_rain": False}
        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN, schedule_decision=sched)

        assert res.decision_type == DecisionTypeEnum.COLLEGE_COMMUTE
        assert res.verdict == DecisionVerdictEnum.GO
        assert "morning trip looks fine based on the available forecast" in res.concise_answer_en.lower()
        assert not res.evidence.is_stale

    # =========================================================================
    # 2. Bike Decision
    # =========================================================================
    def test_bike_decision(self):
        """User asks 'Should I take my bike?' with clear, low-wind conditions."""
        nlu = parse_query("Should I take my bike?")
        weather = _make_weather_record(location_name="Chennai", condition="Clear", wind=12.0, rain_prob=10.0)
        forecast = _make_clear_forecast_items()
        reasoning = _make_reasoning(location="Chennai")

        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN)
        assert res.decision_type == DecisionTypeEnum.BIKE_TRAVEL
        assert res.verdict == DecisionVerdictEnum.RECOMMENDED
        assert "safely take your bike" in res.concise_answer_en.lower() or "safe to ride" in res.recommended_action.lower()

    # =========================================================================
    # 3. Umbrella Decision
    # =========================================================================
    def test_umbrella_decision(self):
        """User asks 'Do I need an umbrella today?' when evening rain is expected."""
        nlu = parse_query("Do I need an umbrella today?")
        weather = _make_weather_record(location_name="Chennai", rain_prob=15.0)
        forecast = _make_forecast_items()
        reasoning = _make_reasoning(location="Chennai")

        sched = {"return_prob": 65.0, "return_has_rain": True}
        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN, schedule_decision=sched)

        assert res.decision_type == DecisionTypeEnum.UMBRELLA
        assert res.verdict == DecisionVerdictEnum.RECOMMENDED
        assert "umbrella" in res.concise_answer_en.lower()

    # =========================================================================
    # 4. Departure Follow-up
    # =========================================================================
    def test_departure_follow_up(self, state_service: ConversationStateService):
        """User asks 'What about leaving at 7 AM?'
        System changes departure time, preserving return time and college context.
        """
        conv_id = "test-dep-followup"
        st = state_service.get_state(conv_id)
        st.active_activity = "college"
        st.active_location = "Coimbatore"
        st.active_departure_time = "08:30"
        st.active_return_time = "17:00"

        turn = state_service.analyze_turn("What about leaving at 7 AM?", st)
        assert turn.resolved_departure_time == "07:00"
        assert turn.resolved_return_time == "17:00"
        assert turn.resolved_activity == "college"

    # =========================================================================
    # 5. Return-time Follow-up
    # =========================================================================
    def test_return_time_follow_up(self, state_service: ConversationStateService):
        """User asks 'What about coming back at 5?'
        System changes return time, preserving departure time and college context.
        If return conditions are worse, advises extra care and umbrella.
        """
        conv_id = "test-ret-followup"
        st = state_service.get_state(conv_id)
        st.active_activity = "college"
        st.active_location = "Chennai"
        st.active_departure_time = "08:30"
        st.active_return_time = "16:00"

        turn = state_service.analyze_turn("What about coming back at 5?", st)
        assert turn.resolved_return_time == "17:00"
        assert turn.resolved_departure_time == "08:30"
        assert turn.resolved_activity == "college"

        # Check decision logic when return conditions are worse around 5 PM
        nlu = parse_query("What about coming back at 5?")
        weather = _make_weather_record(location_name="Chennai", rain_prob=10.0)
        forecast = _make_forecast_items()
        reasoning = _make_reasoning(location="Chennai")

        sched = {
            "departure_prob": 10.0,
            "return_prob": 65.0,
            "return_time": "5 PM",
            "departure_has_rain": False,
            "return_has_rain": True,
        }
        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN, schedule_decision=sched)
        assert res.verdict == DecisionVerdictEnum.CAUTION
        assert "careful on the way back" in res.concise_answer_en.lower()
        assert "5 pm" in res.concise_answer_en.lower()
        assert "umbrella" in res.concise_answer_en.lower()

    # =========================================================================
    # 6. Date Follow-up
    # =========================================================================
    def test_date_follow_up(self, state_service: ConversationStateService):
        """User asks 'What about tomorrow?'
        System changes date to tomorrow, preserving college context and schedule.
        """
        conv_id = "test-date-followup"
        st = state_service.get_state(conv_id)
        st.active_activity = "college"
        st.active_location = "Madurai"
        st.active_departure_time = "08:30"
        st.active_return_time = "17:00"

        turn = state_service.analyze_turn("What about tomorrow?", st)
        assert turn.resolved_date == "tomorrow"
        assert turn.resolved_activity == "college"
        assert turn.resolved_departure_time == "08:30"
        assert turn.resolved_return_time == "17:00"

    # =========================================================================
    # 7. Missing Location
    # =========================================================================
    def test_missing_location(self, state_service: ConversationStateService):
        """User asks 'Can I go to college today?' with no location or campus known.
        System asks ONLY for the minimum required location information.
        """
        conv_id = "test-missing-loc"
        st = state_service.get_state(conv_id)
        # Ensure no location in state
        st.active_location = None
        st.active_destination = None

        turn = state_service.analyze_turn("Can I go to college today?", st)
        assert turn.clarification.needed is True
        assert turn.clarification.missing_type == MissingInformationType.MISSING_LOCATION.value
        assert "location" in turn.clarification.prompt.lower() or "city" in turn.clarification.prompt.lower() or "where" in turn.clarification.prompt.lower()

    # =========================================================================
    # 8. Missing Personal Context
    # =========================================================================
    def test_missing_personal_context(self, state_service: ConversationStateService):
        """User asks 'Can I go to college today?' with known location but no stored schedule.
        System applies standard sensible commute windows (08:30 departure, 17:00 return)
        without failing or fabricating arbitrary values.
        """
        conv_id = "test-missing-schedule"
        st = state_service.get_state(conv_id)
        st.active_location = "Tiruchirappalli"
        st.user_schedule = {}  # Empty schedule

        turn = state_service.analyze_turn("Can I go to college today?", st)
        assert turn.resolved_departure_time == "08:30"
        assert turn.resolved_return_time == "17:00"
        assert turn.resolved_location == "Tiruchirappalli"

    # =========================================================================
    # 9. Warning
    # =========================================================================
    def test_warning(self):
        """Active official IMD warning in effect during commute day.
        System delivers CAUTION verdict and advises checking official college announcements.
        """
        nlu = parse_query("Can I go to college today?")
        weather = _make_weather_record(location_name="Chennai", condition="Heavy Rain", rain_prob=85.0)
        forecast = _make_forecast_items()
        now = datetime.now(timezone.utc)
        alert = OfficialAlert(
            data_type=WeatherDataType.OFFICIAL_WARNING,
            id="ALERT-IMD-001",
            type="heavy_rain",
            severity=RiskLevelEnum.HIGH,
            title="Red Alert - Extremely Heavy Rainfall",
            description="Incessant heavy downpours leading to waterlogging in low-lying areas.",
            instructions="Stay indoors; schools and colleges to follow district collector advisories.",
            source="IMD",
            issued_at=now,
            expires_at=now + timedelta(hours=12),
            status="ACTIVE",
            affected_locations=["Chennai"]
        )
        reasoning = _make_reasoning(location="Chennai", risk=RiskLevelEnum.HIGH, warnings=[alert])

        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN)
        assert res.verdict == DecisionVerdictEnum.CAUTION
        assert "college notices" in res.recommended_action.lower() or "official" in res.recommended_action.lower()
        assert "imd" in res.recommended_action.lower() or "alert" in res.recommended_action.lower()

    # =========================================================================
    # 10. Stale Data
    # =========================================================================
    def test_stale_data(self):
        """Weather telemetry is older than 180 minutes.
        System marks verdict as NOT_RECOMMENDED due to stale telemetry.
        """
        nlu = parse_query("Can I go to college today?")
        weather = _make_weather_record(location_name="Chennai", age_minutes=240)
        forecast = _make_forecast_items()
        reasoning = _make_reasoning(
            location="Chennai",
            freshness=FreshnessStatusEnum.STALE,
            age_minutes=240
        )

        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN)
        assert res.verdict == DecisionVerdictEnum.NOT_RECOMMENDED
        assert res.evidence.is_stale is True
        assert "stale" in res.concise_answer_en.lower() or "stale" in res.recommended_action.lower()

    # =========================================================================
    # 11. Provider Failure
    # =========================================================================
    def test_provider_failure(self):
        """Weather provider failure: observation data unavailable/incomplete.
        System informs user that weather data is unavailable rather than fabricating values.
        """
        nlu = parse_query("Can I go to college today?")
        weather = None  # Telemetry failed / missing
        forecast = []
        reasoning = _make_reasoning(location="Chennai", data_complete=False)

        res = PersonalDecisionEngine.evaluate(nlu, weather, forecast, reasoning, LanguageEnum.EN)
        assert res.verdict == DecisionVerdictEnum.NOT_RECOMMENDED
        assert res.evidence.data_available is False
        assert "unavailable" in res.concise_answer_en.lower() or "unavailable" in res.recommended_action.lower()
