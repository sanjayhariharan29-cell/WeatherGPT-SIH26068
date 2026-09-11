"""End-to-End Tests for SKYZEN Fisherman Personal Weather Decision Experience.

Acceptance Journey:
1. User: "Can I go to sea?"
   - SkyZen must NOT guess the location.
   - SkyZen: "Which area are you planning to fish in?"
2. User: "Near Rameswaram, between India and Sri Lanka."
   - System resolves the location/region (Rameswaram).
   - Collects legitimate available verified data.
   - Answers directly: "Can I go?"
   - Active Warning: "I wouldn't recommend going during that period because an official marine warning is active."
   - Manageable: "Conditions look manageable for the requested period based on the available verified data."

Required Test Scenarios:
- missing location
- clarification
- location response
- valid weather data
- warning active
- no warning
- unavailable data
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
from ai.decision.models import DecisionTypeEnum, DecisionVerdictEnum
from ai.pipeline import WeatherGPTPipeline
from backend.services.geocoding_service import GeocodingService


@pytest.fixture
def state_service() -> ConversationStateService:
    return ConversationStateService(ttl_seconds=600, max_turns=10)


@pytest.fixture
def geocoding_service() -> GeocodingService:
    return GeocodingService()


@pytest.fixture
def pipeline() -> WeatherGPTPipeline:
    return WeatherGPTPipeline()


def _make_weather_record(
    location_name: str = "Rameswaram",
    lat: float = 9.2845,
    lon: float = 79.3126,
    temp: float = 29.0,
    wind: float = 14.0,
    rain_prob: float = 10.0,
    humidity: float = 75.0,
    condition: str = "Partly Cloudy",
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
            district="Ramanathapuram",
            state="Tamil Nadu"
        ),
        observed_at=obs_time,
        retrieved_at=obs_time,
        temperature=temp,
        humidity=humidity,
        rain_probability=rain_prob,
        wind_speed=wind,
        weather_condition=condition,
        source=source,
        rainfall_amount_mm=0.0
    )


def _make_official_marine_alert(
    title: str = "Squally Weather Advisory for Fishermen",
    description: str = "Squally wind speed reaching 45-55 kmph gusting to 65 kmph likely over Gulf of Mannar and adjoining Comorin area.",
    severity: RiskLevelEnum = RiskLevelEnum.HIGH,
    affected_locations: List[str] = None
) -> OfficialAlert:
    now = datetime.now(timezone.utc)
    return OfficialAlert(
        data_type=WeatherDataType.OFFICIAL_WARNING,
        id="IMD-MARINE-RAMESWARAM-01",
        type="cyclone_squall",
        severity=severity,
        title=title,
        description=description,
        instructions="Fishermen are advised not to venture into Gulf of Mannar and adjoining areas.",
        source="IMD",
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=12),
        status="ACTIVE",
        affected_locations=affected_locations or ["Rameswaram", "Ramanathapuram", "Gulf of Mannar"]
    )


class TestFishermanPersonalWeatherDecision:
    """Complete test suite for the Fisherman decision journey and all 9 required scenarios."""

    # -------------------------------------------------------------------------
    # Scenario 1 & 2: Missing Location & Clarification Prompt
    # -------------------------------------------------------------------------
    def test_missing_location_and_clarification(self, state_service: ConversationStateService):
        """User: 'Can I go to sea?'
        SkyZen must NOT guess the location.
        SkyZen asks: 'Which area are you planning to fish in?'
        """
        conv_id = "test-fisherman-missing-loc"
        st = state_service.get_state(conv_id)

        # Turn 1: User asks without location
        t1 = state_service.analyze_turn("Can I go to sea?", st)

        # Must NOT guess or default to any specific place
        assert t1.is_ambiguous is True
        assert t1.clarification.needed is True
        assert t1.clarification.missing_type == MissingInformationType.INSUFFICIENT_MARINE_AREA.value

        # Prompt must exactly ask which area to fish in
        assert t1.clarification.prompt == "Which area are you planning to fish in?"
        assert t1.clarification.pending_intent == IntentEnum.FISHING_DECISION.value

        # Verify Tamil and Hindi clarification prompts as well
        prompt_ta = clarification_engine.get_prompt(MissingInformationType.INSUFFICIENT_MARINE_AREA, language="ta")
        assert "மீன்பிடிக்க" in prompt_ta or "கடல்" in prompt_ta
        prompt_hi = clarification_engine.get_prompt(MissingInformationType.INSUFFICIENT_MARINE_AREA, language="hi")
        assert "मछली" in prompt_hi or "क्षेत्र" in prompt_hi

    # -------------------------------------------------------------------------
    # Scenario 3: Location Response Resolution
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_location_response_resolution(
        self,
        state_service: ConversationStateService,
        geocoding_service: GeocodingService
    ):
        """User responds: 'Near Rameswaram, between India and Sri Lanka.'
        System must resolve the location to Rameswaram and resume fishing decision.
        """
        conv_id = "test-fisherman-resume"
        st = state_service.get_state(conv_id)

        # Turn 1: Initial query triggers clarification
        t1 = state_service.analyze_turn("Can I go to sea?", st)
        st = state_service.update_state(
            conversation_id=conv_id,
            user_message="Can I go to sea?",
            assistant_message=t1.clarification.prompt,
            resolved_ctx=t1
        )

        # Turn 2: User provides location with regional description
        loc_reply = "Near Rameswaram, between India and Sri Lanka."
        t2 = state_service.analyze_turn(loc_reply, st)

        assert t2.turn_type == TurnTypeEnum.CLARIFICATION_RESPONSE
        assert t2.is_ambiguous is False
        assert t2.clarification.needed is False
        assert t2.resolved_location == "Rameswaram"
        assert t2.resolved_intent == IntentEnum.FISHING_DECISION.value

        # Verify Geocoding resolves to Rameswaram in Ramanathapuram district
        geo_res = await geocoding_service.resolve_location(loc_reply)
        assert geo_res["name"] == "Rameswaram"
        assert geo_res["district"] == "Ramanathapuram"
        assert abs(geo_res["latitude"] - 9.2845) < 0.01
        assert abs(geo_res["longitude"] - 79.3126) < 0.01

    # -------------------------------------------------------------------------
    # Scenario 4: Valid Weather Data (Manageable Conditions)
    # -------------------------------------------------------------------------
    def test_valid_weather_data_manageable(self, pipeline: WeatherGPTPipeline):
        """Conditions are calm, verified, fresh, with no warnings.
        The answer must address 'Can I go?' with:
        'Conditions look manageable for the requested period based on the available verified data.'
        """
        weather = _make_weather_record(
            location_name="Rameswaram",
            temp=28.5,
            wind=12.0,      # Mild wind
            rain_prob=5.0,  # Negligible rain
            humidity=72.0,
            condition="Clear",
            age_minutes=10
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=weather,
            forecast=[],
            active_alerts=[],  # Warning check verified, 0 alerts active
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "Conditions look manageable for the requested period based on the available verified data." in answer
        assert "Here is today's weather report" not in answer

        # Verify personal decision engine output
        nlu = parse_query("Can I go to sea in Rameswaram?")
        reasoning = result["reasoning"]
        dec_res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert dec_res.decision_type == DecisionTypeEnum.FISHING_MARINE
        assert dec_res.verdict == DecisionVerdictEnum.GO
        assert dec_res.concise_answer_en == "Conditions look manageable for the requested period based on the available verified data."

    # -------------------------------------------------------------------------
    # Scenario 5: Warning Active
    # -------------------------------------------------------------------------
    def test_warning_active(self, pipeline: WeatherGPTPipeline):
        """An official marine warning is active.
        The answer must address 'Can I go?' with:
        'I wouldn't recommend going during that period because an official marine warning is active.'
        """
        weather = _make_weather_record(
            location_name="Rameswaram",
            temp=27.0,
            wind=32.0,
            rain_prob=60.0,
            condition="Heavy Rain"
        )
        alert = _make_official_marine_alert(
            title="Rough Sea and High Wind Warning",
            severity=RiskLevelEnum.HIGH,
            affected_locations=["Rameswaram"]
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=weather,
            forecast=[],
            active_alerts=[alert],
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "I wouldn't recommend going during that period because an official marine warning is active." in answer

        # Verify personal decision engine output
        nlu = parse_query("Can I go to sea in Rameswaram?")
        reasoning = result["reasoning"]
        dec_res = PersonalDecisionEngine.evaluate(nlu, weather, [], reasoning, LanguageEnum.EN)
        assert dec_res.decision_type == DecisionTypeEnum.FISHING_MARINE
        assert dec_res.verdict == DecisionVerdictEnum.NO_GO
        assert dec_res.concise_answer_en == "I wouldn't recommend going during that period because an official marine warning is active."

    # -------------------------------------------------------------------------
    # Scenario 6: No Warning (Explicit clearance verified)
    # -------------------------------------------------------------------------
    def test_no_warning_clearance(self, pipeline: WeatherGPTPipeline):
        """Active warning check succeeds with 0 warnings, verified weather is benign.
        Answer addresses 'Can I go?' confirming manageable conditions.
        """
        weather = _make_weather_record(
            location_name="Rameswaram",
            temp=29.0,
            wind=15.0,
            rain_prob=15.0,
            condition="Scattered Clouds",
            age_minutes=20
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=weather,
            forecast=[],
            active_alerts=[],  # Verified zero warnings
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        assert "Conditions look manageable for the requested period based on the available verified data." in result["answer"]
        assert result["risk"]["level"] == "low"

    # -------------------------------------------------------------------------
    # Scenario 7: Unavailable Data & Warning Info Unavailable
    # -------------------------------------------------------------------------
    def test_unavailable_data(self, pipeline: WeatherGPTPipeline):
        """Weather observation data is null / unavailable.
        SkyZen must NOT invent data and must address 'Can I go?' by stating
        that verified weather data is currently unavailable.
        """
        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=None,
            forecast=[],
            active_alerts=[],
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "unavailable" in answer.lower()
        assert "cannot recommend" in answer.lower() or "not recommended" in answer.lower()

    def test_official_warning_info_unavailable(self, pipeline: WeatherGPTPipeline):
        """Official IMD warning info is unavailable (active_alerts=None).
        If official warning information is unavailable, SkyZen must say so!
        """
        weather = _make_weather_record(
            location_name="Rameswaram",
            wind=10.0,
            temp=28.0,
            condition="Clear"
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=weather,
            forecast=[],
            active_alerts=None,  # Warning service unavailable / unconfigured
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "official warning information is currently unavailable" in answer.lower()
        assert "not recommended" in answer.lower() or "caution" in answer.lower()

    # -------------------------------------------------------------------------
    # Scenario 8: Stale Data
    # -------------------------------------------------------------------------
    def test_stale_data_handling(self, pipeline: WeatherGPTPipeline):
        """Weather observation telemetry is > 180 minutes old.
        SkyZen must not recommend going to sea based on stale telemetry.
        """
        stale_weather = _make_weather_record(
            location_name="Rameswaram",
            wind=12.0,
            temp=28.0,
            condition="Clear",
            age_minutes=240  # 4 hours old (STALE)
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=stale_weather,
            forecast=[],
            active_alerts=[],
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "stale" in answer.lower()
        assert "wouldn't recommend" in answer.lower() or "not recommended" in answer.lower()

    # -------------------------------------------------------------------------
    # Scenario 9: Provider Failure (Graceful degradation without fabrication)
    # -------------------------------------------------------------------------
    def test_provider_failure_no_hallucination(self, pipeline: WeatherGPTPipeline):
        """When weather and alert providers fail, system must not fabricate
        marine data (no synthetic wave heights, no fake buoy data, no invented facts).
        """
        failed_weather = WeatherRecord(
            data_type=WeatherDataType.CURRENT,
            location=LocationInfo(
                name="Rameswaram",
                latitude=9.2845,
                longitude=79.3126,
                district="Ramanathapuram",
                state="Tamil Nadu"
            ),
            observed_at=datetime.now(timezone.utc),
            retrieved_at=datetime.now(timezone.utc),
            temperature=0.0,
            humidity=0.0,
            rain_probability=0.0,
            wind_speed=0.0,
            weather_condition="Unknown",
            source="DATA_UNAVAILABLE",
            rainfall_amount_mm=0.0
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=failed_weather,
            forecast=[],
            active_alerts=None,
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "unavailable" in answer.lower()
        # Verify forbidden synthetic marine terms are not invented
        forbidden_hallucinations = ["wave height: 1.2m", "swell period 14s", "thermocline", "buoy 42001"]
        for f in forbidden_hallucinations:
            assert f not in answer.lower()

    # -------------------------------------------------------------------------
    # High Wind / Storm Hazard without Official Alert
    # -------------------------------------------------------------------------
    def test_squally_winds_without_official_alert(self, pipeline: WeatherGPTPipeline):
        """Winds are squally (42 km/h) even without an official warning alert.
        Personal decision engine must directly recommend against going.
        """
        high_wind_weather = _make_weather_record(
            location_name="Rameswaram",
            wind=42.0,  # Hazardous squally winds
            temp=27.0,
            condition="Squall",
            age_minutes=15
        )

        result = pipeline.process_query(
            message="Can I go to sea in Rameswaram?",
            weather=high_wind_weather,
            forecast=[],
            active_alerts=[],
            persona=PersonaEnum.FISHERMAN,
            target_language=LanguageEnum.EN
        )

        answer = result["answer"]
        assert "wouldn't recommend going" in answer.lower()
        assert "high wind" in answer.lower() or "42" in answer

    # -------------------------------------------------------------------------
    # Acceptance Journey Multi-Turn Integration
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_acceptance_journey_complete_flow(
        self,
        state_service: ConversationStateService,
        geocoding_service: GeocodingService,
        pipeline: WeatherGPTPipeline
    ):
        """Simulates full conversational acceptance journey:
        Turn 1:
        User: 'Can I go to sea?'
        SkyZen: 'Which area are you planning to fish in?'

        Turn 2:
        User: 'Near Rameswaram, between India and Sri Lanka.'
        SkyZen: 'Conditions look manageable for the requested period based on the available verified data.'
        """
        conv_id = "test-journey-complete"
        st = state_service.get_state(conv_id)

        # Turn 1:
        t1 = state_service.analyze_turn("Can I go to sea?", st)
        assert t1.clarification.needed is True
        turn1_response = t1.clarification.prompt
        assert turn1_response == "Which area are you planning to fish in?"

        st = state_service.update_state(
            conversation_id=conv_id,
            user_message="Can I go to sea?",
            assistant_message=turn1_response,
            resolved_ctx=t1
        )

        # Turn 2:
        user_turn2 = "Near Rameswaram, between India and Sri Lanka."
        t2 = state_service.analyze_turn(user_turn2, st)
        assert t2.resolved_location == "Rameswaram"
        assert t2.resolved_intent == IntentEnum.FISHING_DECISION.value

        # Geocode resolved location
        loc = await geocoding_service.resolve_location(t2.resolved_location)
        assert loc["name"] == "Rameswaram"

        # Provide verified weather
        weather = _make_weather_record(
            location_name=loc["name"],
            lat=loc["latitude"],
            lon=loc["longitude"],
            wind=14.0,
            temp=29.0,
            rain_prob=10.0,
            condition="Partly Cloudy"
        )

        # Pipeline processes resolved query
        pipe_res = pipeline.process_query(
            message=t2.resolved_message,
            weather=weather,
            forecast=[],
            active_alerts=[],
            persona=PersonaEnum.FISHERMAN,
            conversation_id=conv_id,
            target_language=LanguageEnum.EN
        )

        turn2_response = pipe_res["answer"]
        assert "Conditions look manageable for the requested period based on the available verified data." in turn2_response
        assert "Here is today's weather report" not in turn2_response
