"""
Test Suite: SkyZen Conversational Reference & Follow-Up Resolution
Validates:
1. Multi-turn acceptance sequence (tomorrow -> leave for college -> take bike -> return at 5 -> Friday)
2. Pronoun and reference expressions (there, then, when I leave, when I come back, at 5, what about Friday, and my bike, should I take it, is it safe, what about the return trip)
3. Ambiguity handling and clarification triggers without guessing or exposing internal terminology
"""

import pytest
from ai.memory.models import (
    ConversationState,
    ClarificationState,
    ResolvedQueryContext,
    TurnTypeEnum,
)
from ai.memory.state_service import ConversationStateService
from ai.models import IntentEnum


@pytest.fixture
def service() -> ConversationStateService:
    """Provides a fresh ConversationStateService instance with test TTL."""
    return ConversationStateService(ttl_seconds=300, max_turns=10)


class TestSkyZenExampleAcceptanceSequence:
    """Validates the exact 5-turn sequence specified in requirements."""

    def test_complete_acceptance_sequence(self, service: ConversationStateService):
        conv_id = "test-seq-acceptance-1"
        st = service.get_state(conv_id)
        st.active_location = "Coimbatore"

        # -----------------------------------------------------------------
        # Turn 1: User: "Will it rain tomorrow?"
        # -----------------------------------------------------------------
        t1_analysis = service.analyze_turn("Will it rain tomorrow?", st)
        assert t1_analysis.turn_type == TurnTypeEnum.NEW_QUESTION
        assert t1_analysis.resolved_date == "tomorrow"
        assert t1_analysis.resolved_topic == "rain"
        assert t1_analysis.resolved_location == "Coimbatore"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="Will it rain tomorrow?",
            assistant_message="Light scattered rain is expected tomorrow in Coimbatore with 35% probability.",
            resolved_ctx=t1_analysis
        )
        assert st.turn_index == 1
        assert st.active_date == "tomorrow"
        assert st.active_topic == "rain"
        assert st.active_location == "Coimbatore"

        # -----------------------------------------------------------------
        # Turn 2: User: "What about when I leave for college?"
        # System must retain tomorrow + weather topic and resolve user's
        # known/usual college departure time (08:30).
        # -----------------------------------------------------------------
        t2_analysis = service.analyze_turn("What about when I leave for college?", st)
        assert t2_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Retains tomorrow + weather topic
        assert t2_analysis.resolved_date == "tomorrow"
        assert "date" in t2_analysis.inherited_fields
        assert t2_analysis.resolved_topic == "rain"
        assert "topic" in t2_analysis.inherited_fields
        # Resolves departure phase and schedule anchor
        assert t2_analysis.resolved_activity == "college"
        assert t2_analysis.resolved_trip_phase == "departure"
        assert t2_analysis.resolved_departure_time == "08:30"
        assert t2_analysis.resolved_time == "08:30"
        assert t2_analysis.resolved_location == "Coimbatore"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="What about when I leave for college?",
            assistant_message="At 8:30 AM tomorrow morning during your college departure, skies will be cloudy with no heavy rain.",
            resolved_ctx=t2_analysis
        )
        assert st.turn_index == 2
        assert st.active_date == "tomorrow"
        assert st.active_activity == "college"
        assert st.active_departure_time == "08:30"
        assert st.active_trip_phase == "departure"

        # -----------------------------------------------------------------
        # Turn 3: User: "Should I take my bike?"
        # System must retain:
        # - tomorrow
        # - college trip
        # - departure time
        # - current location/destination
        # -----------------------------------------------------------------
        t3_analysis = service.analyze_turn("Should I take my bike?", st)
        assert t3_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Retains tomorrow
        assert t3_analysis.resolved_date == "tomorrow"
        assert "date" in t3_analysis.inherited_fields
        # Retains college trip
        assert t3_analysis.resolved_activity == "college"
        assert "activity" in t3_analysis.inherited_fields
        # Retains departure time (08:30)
        assert t3_analysis.resolved_time == "08:30"
        assert t3_analysis.resolved_departure_time == "08:30"
        assert "time" in t3_analysis.inherited_fields or "departure_time" in t3_analysis.inherited_fields
        # Retains location and destination
        assert t3_analysis.resolved_location == "Coimbatore"
        assert t3_analysis.resolved_destination == "college"
        # Identifies transport mode
        assert t3_analysis.resolved_transport_mode == "bike"
        assert t3_analysis.resolved_intent == "bike_travel"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="Should I take my bike?",
            assistant_message="Yes, taking your bike for your 8:30 AM college commute tomorrow is safe; wind speed is low and roads are clear.",
            resolved_ctx=t3_analysis
        )
        assert st.turn_index == 3
        assert st.active_transport_mode == "bike"
        assert st.active_vehicle_or_item == "bike"

        # -----------------------------------------------------------------
        # Turn 4: User: "What about coming back at 5?"
        # System must change only the relevant dimension:
        # - trip phase = return
        # - time = 5 PM (17:00)
        # Preserving: tomorrow, college trip, bike, location
        # -----------------------------------------------------------------
        t4_analysis = service.analyze_turn("What about coming back at 5?", st)
        assert t4_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Changed dimensions:
        assert t4_analysis.resolved_trip_phase == "return"
        assert t4_analysis.resolved_time == "17:00"
        assert t4_analysis.resolved_return_time == "17:00"
        # Preserved dimensions:
        assert t4_analysis.resolved_date == "tomorrow"
        assert t4_analysis.resolved_activity == "college"
        assert t4_analysis.resolved_transport_mode == "bike"
        assert t4_analysis.resolved_location == "Coimbatore"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="What about coming back at 5?",
            assistant_message="Around 5:00 PM tomorrow for your return trip, isolated showers are likely. Carry a raincoat if riding your bike.",
            resolved_ctx=t4_analysis
        )
        assert st.turn_index == 4
        assert st.active_trip_phase == "return"
        assert st.active_time == "17:00"
        assert st.active_return_time == "17:00"
        assert st.active_transport_mode == "bike"
        assert st.active_activity == "college"
        assert st.active_date == "tomorrow"

        # -----------------------------------------------------------------
        # Turn 5: User: "And Friday?"
        # System must preserve the active question/activity and change date to Friday.
        # Preserving: college, bike, return trip at 5 PM, location
        # -----------------------------------------------------------------
        t5_analysis = service.analyze_turn("And Friday?", st)
        assert t5_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Date changed to Friday
        assert t5_analysis.resolved_date == "Friday"
        # Active question / activity / transport / time / location preserved
        assert t5_analysis.resolved_activity == "college"
        assert t5_analysis.resolved_transport_mode == "bike"
        assert t5_analysis.resolved_trip_phase == "return"
        assert t5_analysis.resolved_time == "17:00"
        assert t5_analysis.resolved_location == "Coimbatore"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="And Friday?",
            assistant_message="On Friday around 5:00 PM, weather will be clear and dry for your return college bike trip.",
            resolved_ctx=t5_analysis
        )
        assert st.turn_index == 5
        assert st.active_date == "Friday"
        assert st.active_activity == "college"
        assert st.active_transport_mode == "bike"
        assert st.active_time == "17:00"


class TestSpecificReferenceExpressions:
    """Validates individual deictic and anaphoric reference expressions."""

    def test_reference_there_and_there_tomorrow(self, service: ConversationStateService):
        conv_id = "test-ref-there"
        st = service.get_state(conv_id)

        # Turn 1: establish location Chennai
        t1 = service.analyze_turn("Weather in Chennai today?", st)
        st = service.update_state(conv_id, "Weather in Chennai today?", "Chennai is 32°C.", t1)

        # Reference: "there tomorrow"
        t2 = service.analyze_turn("How is the weather there tomorrow?", st)
        assert t2.resolved_location == "Chennai"
        assert "location" in t2.inherited_fields
        assert t2.resolved_date == "tomorrow"

        # Reference: "there"
        t3 = service.analyze_turn("Will it be windy there?", st)
        assert t3.resolved_location == "Chennai"
        assert "location" in t3.inherited_fields

    def test_reference_then_resolved(self, service: ConversationStateService):
        conv_id = "test-ref-then"
        st = service.get_state(conv_id)

        # Turn 1: establish Sunday evening
        t1 = service.analyze_turn("Will it rain on Sunday evening in Madurai?", st)
        st = service.update_state(conv_id, "Will it rain on Sunday evening in Madurai?", "Rain expected.", t1)

        # Reference: "then" -> resolves to Sunday evening
        t2 = service.analyze_turn("Is it safe then?", st)
        assert t2.resolved_location == "Madurai"
        assert t2.resolved_date == "Sunday"
        assert t2.resolved_time == "evening"
        assert t2.is_ambiguous is False

    def test_reference_what_about_the_evening(self, service: ConversationStateService):
        conv_id = "test-ref-evening"
        st = service.get_state(conv_id)

        # Turn 1: establish Friday in Trichy
        t1 = service.analyze_turn("Is it raining in Trichy on Friday morning?", st)
        st = service.update_state(conv_id, "Is it raining in Trichy on Friday morning?", "Clear skies.", t1)

        # Reference: "what about the evening?"
        t2 = service.analyze_turn("What about the evening?", st)
        assert t2.resolved_time == "evening"
        assert t2.resolved_date == "Friday"
        assert t2.resolved_location in ("Trichy", "Tiruchirappalli")

    def test_reference_and_my_bike_and_should_i_take_it(self, service: ConversationStateService):
        conv_id = "test-ref-bike-it"
        st = service.get_state(conv_id)

        # Turn 1: Weather check
        t1 = service.analyze_turn("Will it rain tomorrow in Salem?", st)
        st = service.update_state(conv_id, "Will it rain tomorrow in Salem?", "Light drizzle.", t1)

        # Reference: "and my bike?"
        t2 = service.analyze_turn("And my bike?", st)
        assert t2.resolved_transport_mode == "bike"
        assert t2.resolved_date == "tomorrow"
        assert t2.resolved_location == "Salem"
        st = service.update_state(conv_id, "And my bike?", "Roads might be slightly slippery.", t2)

        # Reference: "should I take it?" -> resolves "it" to bike
        t3 = service.analyze_turn("Should I take it?", st)
        assert t3.resolved_transport_mode == "bike"
        assert "transport_mode" in t3.inherited_fields
        assert t3.is_ambiguous is False

    def test_reference_what_about_the_return_trip(self, service: ConversationStateService):
        conv_id = "test-ref-return-trip"
        st = service.get_state(conv_id)

        # Turn 1: Office departure
        t1 = service.analyze_turn("Can I drive to office tomorrow morning in Bangalore?", st)
        st = service.update_state(conv_id, "Can I drive to office tomorrow morning in Bangalore?", "Roads clear.", t1)

        # Reference: "what about the return trip?"
        t2 = service.analyze_turn("What about the return trip?", st)
        assert t2.resolved_trip_phase == "return"
        assert t2.resolved_return_time == "18:00"  # Office return default
        assert t2.resolved_time == "18:00"
        assert t2.resolved_date == "tomorrow"
        assert t2.resolved_location in ("Bangalore", "Bengaluru")


class TestAmbiguityAndClarification:
    """Validates that genuinely ambiguous references trigger concise clarification without guessing."""

    def test_ambiguous_it_without_prior_item_triggers_clarification(self, service: ConversationStateService):
        conv_id = "test-ambig-it"
        st = service.get_state(conv_id)

        # Turn 1: General weather question without any vehicle or item mentioned
        t1 = service.analyze_turn("Weather in Ooty tomorrow?", st)
        st = service.update_state(conv_id, "Weather in Ooty tomorrow?", "14°C and cloudy.", t1)

        # Turn 2: User says "Should I take it?" when no vehicle/item exists in state
        t2 = service.analyze_turn("Should I take it?", st)
        assert t2.is_ambiguous is True
        assert t2.turn_type == TurnTypeEnum.AMBIGUOUS_REQUEST
        assert t2.clarification.needed is True
        assert "bike" in t2.clarification.prompt.lower() or "umbrella" in t2.clarification.prompt.lower()
        # Verify no internal terminology leaked in prompt
        assert "intent" not in t2.clarification.prompt.lower()
        assert "nlu" not in t2.clarification.prompt.lower()
        assert "slot" not in t2.clarification.prompt.lower()

    def test_ambiguous_then_without_time_triggers_clarification(self, service: ConversationStateService):
        conv_id = "test-ambig-then"
        st = service.get_state(conv_id)

        # Start of conversation: "Is it safe then?" with no time or date established
        t1 = service.analyze_turn("Is it safe then in Chennai?", st)
        assert t1.is_ambiguous is True
        assert t1.clarification.needed is True
        assert "day or time" in t1.clarification.prompt.lower()
        # No internal terminology
        assert "enum" not in t1.clarification.prompt.lower()
        assert "pipeline" not in t1.clarification.prompt.lower()

    def test_ambiguous_there_without_prior_location_triggers_clarification(self, service: ConversationStateService):
        conv_id = "test-ambig-there"
        st = service.get_state(conv_id)

        # No location established yet
        t1 = service.analyze_turn("Will it rain heavily there?", st)
        assert t1.is_ambiguous is True
        assert t1.clarification.needed is True
        assert "city" in t1.clarification.prompt.lower() or "district" in t1.clarification.prompt.lower()


class TestBoundedContextExclusion:
    """Verifies that conversation history is compressed to bounded context rather than raw chat dumps."""

    def test_bounded_context_compactness(self, service: ConversationStateService):
        conv_id = "test-bounded-ctx"
        st = service.get_state(conv_id)

        # Simulate 6 turns
        for i in range(1, 7):
            t = service.analyze_turn(f"Weather update turn {i} in Chennai", st)
            st = service.update_state(conv_id, f"Weather update turn {i} in Chennai", f"Answer {i}", t)

        bounded = st.to_bounded_context(max_turns=2)
        # Must contain bounded summary anchors
        assert "Active Location: Chennai" in bounded
        # Must not contain all 6 turns
        assert "turn 1" not in bounded.lower()
        assert "turn 2" not in bounded.lower()
        # Must only have recent 2 turns
        assert "turn 5" in bounded.lower() or "turn 6" in bounded.lower()
