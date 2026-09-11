"""Regression Tests for SkyZen Persistent Conversational Memory.

Verifies:
1. Complete five-turn conversation sequence:
   - Turn 1: "Will it rain tomorrow?"
   - Turn 2: "What about when I leave for college?"
   - Turn 3: "Should I take my bike?"
   - Turn 4: "What about coming back at 5?"
   - Turn 5: "And Friday?"
   Preserves relevant context while changing only the explicitly changed dimension.
2. Supports all 11 required dimensions:
   - active intent
   - location
   - date
   - time
   - activity
   - destination
   - transport
   - trip phase
   - previous decision
   - clarification state
   - language
3. Does not permanently store temporary weather facts.
4. Preserves stable user preferences.
5. Survives application restart/login by rehydrating from database models.
6. Bounded relevant-context retrieval for LLM grounding (does not leak full DB/history).
"""

import pytest
from datetime import datetime, timezone

from ai.memory.state_service import ConversationStateService, state_service
from ai.memory.models import TurnTypeEnum, ConversationState, ClarificationState, ConversationTurn
from backend.db.session import SessionLocal
from backend.db.models import Conversation, Message, User, UserPreference, SavedLocation


class TestFiveTurnConversationSequence:
    """Regression tests for the complete five-turn acceptance sequence."""

    def test_complete_five_turn_conversation(self):
        service = ConversationStateService()
        conv_id = "test-five-turn-acceptance"
        st = service.get_state(conv_id)
        st.active_location = "Coimbatore"
        st.preferred_language = "en"

        # =====================================================================
        # Turn 1: User: "Will it rain tomorrow?"
        # =====================================================================
        t1_analysis = service.analyze_turn("Will it rain tomorrow?", st)
        assert t1_analysis.turn_type == TurnTypeEnum.NEW_QUESTION
        assert t1_analysis.resolved_date == "tomorrow"
        assert t1_analysis.resolved_topic == "rain"
        assert t1_analysis.resolved_location == "Coimbatore"
        assert t1_analysis.resolved_intent in ("rain_query", "weather_information")
        assert t1_analysis.resolved_activity is None
        assert t1_analysis.resolved_transport_mode is None
        assert t1_analysis.resolved_trip_phase is None
        assert t1_analysis.clarification.needed is False
        assert t1_analysis.resolved_language == "en"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="Will it rain tomorrow?",
            assistant_message="Rain is unlikely tomorrow morning in Coimbatore with only a 15% chance of drizzle.",
            resolved_ctx=t1_analysis,
            decision_context={"verdict": "Rain unlikely", "action": "Rain unlikely tomorrow morning"}
        )

        # Assert Turn 1 State
        assert st.turn_index == 1
        assert st.current_intent in ("rain_query", "weather_information")
        assert st.active_location == "Coimbatore"
        assert st.active_date == "tomorrow"
        assert st.active_time is None
        assert st.active_activity is None
        assert st.active_destination is None
        assert st.active_transport_mode is None
        assert st.active_trip_phase is None
        assert st.previous_decision == "Rain unlikely tomorrow morning"
        assert st.clarification_state.needed is False
        assert st.preferred_language == "en"

        # =====================================================================
        # Turn 2: User: "What about when I leave for college?"
        # System must retain tomorrow + weather topic and resolve user's
        # known/usual college departure time (08:30).
        # =====================================================================
        t2_analysis = service.analyze_turn("What about when I leave for college?", st)
        assert t2_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Changed dimensions:
        assert t2_analysis.resolved_activity == "college"
        assert t2_analysis.resolved_destination == "college"
        assert t2_analysis.resolved_trip_phase == "departure"
        assert t2_analysis.resolved_departure_time == "08:30"
        assert t2_analysis.resolved_time == "08:30"
        # Preserved dimensions:
        assert t2_analysis.resolved_date == "tomorrow"
        assert "date" in t2_analysis.inherited_fields
        assert t2_analysis.resolved_topic == "rain"
        assert "topic" in t2_analysis.inherited_fields
        assert t2_analysis.resolved_location == "Coimbatore"
        assert t2_analysis.resolved_transport_mode is None
        assert t2_analysis.clarification.needed is False
        assert t2_analysis.resolved_language == "en"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="What about when I leave for college?",
            assistant_message="At 8:30 AM tomorrow during your college departure, skies will be cloudy with no rain expected.",
            resolved_ctx=t2_analysis,
            decision_context={"verdict": "Clear", "action": "Skies will be cloudy with no rain"}
        )

        # Assert Turn 2 State
        assert st.turn_index == 2
        assert st.current_intent in ("college_commute", "rain_query")
        assert st.active_location == "Coimbatore"
        assert st.active_date == "tomorrow"
        assert st.active_time == "08:30"
        assert st.active_departure_time == "08:30"
        assert st.active_activity == "college"
        assert st.active_destination == "college"
        assert st.active_transport_mode is None
        assert st.active_trip_phase == "departure"
        assert st.previous_decision == "Skies will be cloudy with no rain"
        assert st.clarification_state.needed is False
        assert st.preferred_language == "en"

        # =====================================================================
        # Turn 3: User: "Should I take my bike?"
        # System must retain:
        # - tomorrow
        # - college trip
        # - departure time (08:30)
        # - destination
        # and resolve transport = bike, intent = bike_travel.
        # =====================================================================
        t3_analysis = service.analyze_turn("Should I take my bike?", st)
        assert t3_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Changed dimension:
        assert t3_analysis.resolved_transport_mode == "bike"
        assert t3_analysis.resolved_intent == "bike_travel"
        # Preserved dimensions:
        assert t3_analysis.resolved_date == "tomorrow"
        assert "date" in t3_analysis.inherited_fields
        assert t3_analysis.resolved_activity == "college"
        assert "activity" in t3_analysis.inherited_fields
        assert t3_analysis.resolved_destination == "college"
        assert t3_analysis.resolved_departure_time == "08:30"
        assert t3_analysis.resolved_time == "08:30"
        assert t3_analysis.resolved_trip_phase == "departure"
        assert t3_analysis.resolved_location == "Coimbatore"
        assert t3_analysis.clarification.needed is False
        assert t3_analysis.resolved_language == "en"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="Should I take my bike?",
            assistant_message="Yes, taking your bike for your 8:30 AM college commute tomorrow is fine. Roads will be dry.",
            resolved_ctx=t3_analysis,
            decision_context={"verdict": "Safe", "action": "Taking your bike tomorrow morning is fine"}
        )

        # Assert Turn 3 State
        assert st.turn_index == 3
        assert st.current_intent == "bike_travel"
        assert st.active_location == "Coimbatore"
        assert st.active_date == "tomorrow"
        assert st.active_time == "08:30"
        assert st.active_departure_time == "08:30"
        assert st.active_activity == "college"
        assert st.active_destination == "college"
        assert st.active_transport_mode == "bike"
        assert st.active_trip_phase == "departure"
        assert st.previous_decision == "Taking your bike tomorrow morning is fine"
        assert st.clarification_state.needed is False
        assert st.preferred_language == "en"

        # =====================================================================
        # Turn 4: User: "What about coming back at 5?"
        # System must change ONLY the relevant dimension:
        # - trip phase = return
        # - time = 5 PM (17:00)
        # - return_time = 17:00
        # Preserving: tomorrow, college trip, bike, destination, location.
        # =====================================================================
        t4_analysis = service.analyze_turn("What about coming back at 5?", st)
        assert t4_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Changed dimensions:
        assert t4_analysis.resolved_trip_phase == "return"
        assert t4_analysis.resolved_time == "17:00"
        assert t4_analysis.resolved_return_time == "17:00"
        # Preserved dimensions:
        assert t4_analysis.resolved_date == "tomorrow"
        assert t4_analysis.resolved_activity == "college"
        assert t4_analysis.resolved_destination == "college"
        assert t4_analysis.resolved_transport_mode == "bike"
        assert t4_analysis.resolved_departure_time == "08:30"
        assert t4_analysis.resolved_location == "Coimbatore"
        assert t4_analysis.resolved_intent == "bike_travel"
        assert t4_analysis.clarification.needed is False
        assert t4_analysis.resolved_language == "en"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="What about coming back at 5?",
            assistant_message="Around 5:00 PM tomorrow on your return trip, isolated showers are likely. Carry a raincoat if riding your bike.",
            resolved_ctx=t4_analysis,
            decision_context={"verdict": "Moderate Risk", "action": "Carry a raincoat for return trip"}
        )

        # Assert Turn 4 State
        assert st.turn_index == 4
        assert st.current_intent == "bike_travel"
        assert st.active_location == "Coimbatore"
        assert st.active_date == "tomorrow"
        assert st.active_time == "17:00"
        assert st.active_return_time == "17:00"
        assert st.active_departure_time == "08:30"
        assert st.active_activity == "college"
        assert st.active_destination == "college"
        assert st.active_transport_mode == "bike"
        assert st.active_trip_phase == "return"
        assert st.previous_decision == "Carry a raincoat for return trip"
        assert st.clarification_state.needed is False
        assert st.preferred_language == "en"

        # =====================================================================
        # Turn 5: User: "And Friday?"
        # System must preserve the active question/activity and change ONLY date to Friday.
        # Preserving: college, bike, return trip at 5 PM, destination, location.
        # =====================================================================
        t5_analysis = service.analyze_turn("And Friday?", st)
        assert t5_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        # Changed dimension:
        assert t5_analysis.resolved_date == "Friday"
        # Preserved dimensions:
        assert t5_analysis.resolved_time == "17:00"
        assert t5_analysis.resolved_return_time == "17:00"
        assert t5_analysis.resolved_activity == "college"
        assert t5_analysis.resolved_destination == "college"
        assert t5_analysis.resolved_transport_mode == "bike"
        assert t5_analysis.resolved_trip_phase == "return"
        assert t5_analysis.resolved_location == "Coimbatore"
        assert t5_analysis.resolved_intent == "bike_travel"
        assert t5_analysis.clarification.needed is False
        assert t5_analysis.resolved_language == "en"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="And Friday?",
            assistant_message="On Friday around 5:00 PM, return college bike travel looks clear and dry.",
            resolved_ctx=t5_analysis,
            decision_context={"verdict": "Clear", "action": "Return college bike travel is clear on Friday"}
        )

        # Assert Turn 5 State
        assert st.turn_index == 5
        assert st.current_intent == "bike_travel"
        assert st.active_location == "Coimbatore"
        assert st.active_date == "Friday"
        assert st.active_time == "17:00"
        assert st.active_return_time == "17:00"
        assert st.active_departure_time == "08:30"
        assert st.active_activity == "college"
        assert st.active_destination == "college"
        assert st.active_transport_mode == "bike"
        assert st.active_trip_phase == "return"
        assert st.previous_decision == "Return college bike travel is clear on Friday"
        assert st.clarification_state.needed is False
        assert st.preferred_language == "en"


class TestRestartAndDatabaseHydration:
    """Regression tests verifying state survives simulated application restart/login."""

    def test_state_hydration_from_database_after_memory_purge(self):
        db = SessionLocal()
        conv_id = "test-restart-hydration-regression"

        try:
            # Clean up prior test artifacts
            db.query(Message).filter(Message.conversation_id == conv_id).delete()
            db.query(Conversation).filter(Conversation.id == conv_id).delete()
            db.commit()

            # Create conversation record
            conv = Conversation(id=conv_id, title="Commute persistence test")
            db.add(conv)
            db.commit()

            # Insert 5-turn history into Message table
            history = [
                ("user", "Will it rain tomorrow in Coimbatore?"),
                ("bot", "Rain is unlikely tomorrow morning in Coimbatore."),
                ("user", "What about when I leave for college?"),
                ("bot", "At 8:30 AM tomorrow during college departure, skies will be cloudy."),
                ("user", "Should I take my bike?"),
                ("bot", "Yes, taking your bike for your 8:30 AM college commute tomorrow is fine."),
                ("user", "What about coming back at 5?"),
                ("bot", "Around 5:00 PM tomorrow on your return trip, isolated showers are likely."),
                ("user", "And Friday?"),
                ("bot", "On Friday around 5:00 PM, return college bike travel looks clear and dry.")
            ]

            for sender, text in history:
                msg = Message(
                    conversation_id=conv_id,
                    sender=sender,
                    content=text,
                    intent="bike_travel" if "bike" in text else "college_commute",
                    language="en",
                    risk_level="low",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(msg)
            db.commit()

            # SIMULATE APPLICATION RESTART:
            # 1. Reset singleton state service in-memory store
            state_service.reset_state(conv_id)
            assert conv_id not in state_service._states

            # 2. Re-instantiate fresh service instance
            fresh_service = ConversationStateService()
            assert conv_id not in fresh_service._states

            # 3. Retrieve state via get_state(conv_id, db_session=db)
            hydrated = fresh_service.get_state(conv_id, db_session=db)

            # Assert hydrated properties survived restart
            assert hydrated is not None
            assert hydrated.turn_index == 5
            assert hydrated.active_date == "Friday"
            assert hydrated.active_time == "17:00"
            assert hydrated.active_activity == "college"
            assert hydrated.active_destination == "college"
            assert hydrated.active_transport_mode == "bike"
            assert hydrated.active_trip_phase == "return"
            assert hydrated.active_location == "Coimbatore"
            assert len(hydrated.turns) == 10
            assert hydrated.previous_decision is not None

            # 4. Seamless continuation: user issues Turn 6 after restart
            t6 = fresh_service.analyze_turn("What about coming back at 6?", hydrated)
            assert t6.turn_type == TurnTypeEnum.FOLLOW_UP
            # Only time changes to 18:00
            assert t6.resolved_time == "18:00"
            assert t6.resolved_return_time == "18:00"
            # Friday, college, bike, return trip, Coimbatore are preserved!
            assert t6.resolved_date == "Friday"
            assert t6.resolved_activity == "college"
            assert t6.resolved_transport_mode == "bike"
            assert t6.resolved_trip_phase == "return"
            assert t6.resolved_location == "Coimbatore"

        finally:
            db.query(Message).filter(Message.conversation_id == conv_id).delete()
            db.query(Conversation).filter(Conversation.id == conv_id).delete()
            db.commit()
            db.close()


class TestBoundedContextAndNoEphemeralWeatherFacts:
    """Verifies bounded context retrieval and exclusion of ephemeral weather measurements."""

    def test_bounded_context_length_and_content(self):
        st = ConversationState(
            conversation_id="test-bounded-ctx",
            active_location="Coimbatore",
            active_destination="college",
            active_date="Friday",
            active_time="17:00",
            active_trip_phase="return",
            active_transport_mode="bike",
            active_activity="college",
            active_topic="rain",
            previous_decision="Return college bike travel is clear on Friday"
        )
        # Add 6 turns (3 exchanges)
        for i in range(1, 4):
            st.turns.append(ConversationTurn(role="user", message=f"User question {i}"))
            st.turns.append(ConversationTurn(role="assistant", message=f"Assistant answer {i}"))

        # Bounded context retrieval with max_turns=2
        ctx_summary = st.to_bounded_context(max_turns=2)

        # Must include key active entity anchors and previous decision
        assert "Active Location: Coimbatore" in ctx_summary
        assert "Destination: college" in ctx_summary
        assert "Target Date: Friday" in ctx_summary
        assert "Target Time: 17:00" in ctx_summary
        assert "Transport: bike" in ctx_summary
        assert "Activity: college" in ctx_summary
        assert "Trip Phase: return" in ctx_summary
        assert "Previous Decision: Return college bike travel is clear on Friday" in ctx_summary

        # Must bound historical exchanges: only turns 2 and 3 should appear, turn 1 must be excluded
        assert "User question 3" in ctx_summary
        assert "User question 2" in ctx_summary
        assert "User question 1" not in ctx_summary

        # Must not contain raw weather telemetry matrices
        assert "temperature: " not in ctx_summary
        assert "humidity: " not in ctx_summary
        assert "wind_kph: " not in ctx_summary

    def test_temporary_weather_facts_not_stored_in_decision_context(self):
        service = ConversationStateService()
        st = service.get_state("test-no-temp-facts")
        res = service.analyze_turn("Will it rain tomorrow in Coimbatore?", st)

        # Simulate engine passing raw telemetry alongside decision
        transient_telemetry = {
            "verdict": "Safe",
            "action": "Travel looks fine",
            "temperature_c": 28.5,
            "humidity_percent": 82.0,
            "wind_speed_kmh": 14.2,
            "hourly_forecast_matrix": [12.0, 14.0, 15.0]
        }

        updated_st = service.update_state(
            conversation_id="test-no-temp-facts",
            user_message="Will it rain tomorrow in Coimbatore?",
            assistant_message="No rain expected tomorrow in Coimbatore.",
            resolved_ctx=res,
            decision_context=transient_telemetry
        )

        # Verify raw telemetry keys were stripped
        stored_ctx = updated_st.previous_resolved_decision_context
        assert stored_ctx.get("verdict") == "Safe"
        assert stored_ctx.get("action") == "Travel looks fine"
        assert "temperature_c" not in stored_ctx
        assert "humidity_percent" not in stored_ctx
        assert "wind_speed_kmh" not in stored_ctx
        assert "hourly_forecast_matrix" not in stored_ctx


class TestStableUserPreferences:
    """Verifies that stable user preferences persist and are loaded across sessions."""

    def test_save_and_hydrate_user_preferences(self):
        db = SessionLocal()
        user_id = "test-user-pref-persistence"
        conv_id = "test-conv-user-pref"

        try:
            # Clean up old records
            db.query(SavedLocation).filter(SavedLocation.user_id == user_id).delete()
            db.query(UserPreference).filter(UserPreference.user_id == user_id).delete()
            db.query(Message).filter(Message.conversation_id == conv_id).delete()
            db.query(Conversation).filter(Conversation.id == conv_id).delete()
            db.query(User).filter(User.id == user_id).delete()
            db.commit()

            # Create User with stable preferences
            user = User(
                id=user_id,
                name="Sanjay",
                email="sanjay.test@weathergpt.local",
                password_hash="fakehash",
                language="ta",
                persona="commuter"
            )
            db.add(user)
            db.commit()

            saved_loc = SavedLocation(user_id=user_id, name="Salem", latitude=11.6643, longitude=78.1460)
            db.add(saved_loc)
            pref = UserPreference(user_id=user_id, preferred_units="metric", persona="commuter")
            db.add(pref)

            conv = Conversation(id=conv_id, user_id=user_id, title="Preference Test Chat")
            db.add(conv)
            db.commit()

            # Re-fetch state from DB
            service = ConversationStateService()
            st = service.get_state(conv_id, user_id=user_id, db_session=db)

            # Assert stable user preferences were hydrated into active state
            assert st.preferred_language == "ta"
            assert st.persona == "commuter"
            assert st.active_location == "Salem"
            assert st.user_preferences.get("preferred_units") == "metric"

        finally:
            db.query(SavedLocation).filter(SavedLocation.user_id == user_id).delete()
            db.query(UserPreference).filter(UserPreference.user_id == user_id).delete()
            db.query(Message).filter(Message.conversation_id == conv_id).delete()
            db.query(Conversation).filter(Conversation.id == conv_id).delete()
            db.query(User).filter(User.id == user_id).delete()
            db.commit()
            db.close()


class TestMultilingualAndClarificationPersistence:
    """Verifies that clarification state and language dimensions are preserved across turns."""

    def test_clarification_trigger_and_resolution_flow(self):
        service = ConversationStateService()
        conv_id = "test-clarification-flow"
        st = service.get_state(conv_id)

        # Turn 1: Safety-critical query with missing marine area
        t1 = service.analyze_turn("Can I go to sea?", st)
        assert t1.turn_type == TurnTypeEnum.AMBIGUOUS_REQUEST
        assert t1.clarification.needed is True
        assert t1.clarification.field == "marine_area"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="Can I go to sea?",
            assistant_message=t1.clarification.prompt or "Which area are you planning to fish in?",
            resolved_ctx=t1
        )
        assert st.clarification_state.needed is True
        assert st.clarification_state.field == "marine_area"

        # Turn 2: User answers clarification: "Near Rameswaram."
        t2 = service.analyze_turn("Near Rameswaram.", st)
        assert t2.turn_type == TurnTypeEnum.CLARIFICATION_RESPONSE
        assert t2.resolved_location == "Rameswaram"
        assert t2.clarification.needed is False
        assert t2.resolved_intent == "fishing_decision"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="Near Rameswaram.",
            assistant_message="Wind speed near Rameswaram is 18 km/h. Sea conditions are safe for coastal fishing.",
            resolved_ctx=t2,
            decision_context={"verdict": "Safe", "action": "Sea conditions are safe for coastal fishing"}
        )
        # Clarification state is resolved
        assert st.clarification_state.needed is False
        assert st.active_location == "Rameswaram"
        assert st.previous_decision == "Sea conditions are safe for coastal fishing"

    def test_tamil_conversation_dimension_preservation(self):
        service = ConversationStateService()
        conv_id = "test-tamil-persistence"
        st = service.get_state(conv_id)
        st.active_location = "Madurai"
        st.preferred_language = "ta"

        # Turn 1: "நாளை மழை பெய்யுமா?" (Will it rain tomorrow?)
        t1 = service.analyze_turn("நாளை மழை பெய்யுமா?", st, explicit_language="ta")
        assert t1.resolved_date == "tomorrow"
        assert t1.resolved_topic == "rain"
        assert t1.resolved_language == "ta"

        st = service.update_state(
            conversation_id=conv_id,
            user_message="நாளை மழை பெய்யுமா?",
            assistant_message="மதுரையில் நாளை மிதமான மழை பெய்ய வாய்ப்புள்ளது.",
            resolved_ctx=t1
        )
        assert st.active_date == "tomorrow"
        assert st.active_topic == "rain"

        # Turn 2: "நான் கிளம்பும்போது?" (When I leave?)
        t2 = service.analyze_turn("நான் கிளம்பும்போது?", st, explicit_language="ta")
        assert t2.resolved_trip_phase == "departure"
        # Preserved tomorrow, rain, Madurai
        assert t2.resolved_date == "tomorrow"
        assert t2.resolved_topic == "rain"
        assert t2.resolved_location == "Madurai"

