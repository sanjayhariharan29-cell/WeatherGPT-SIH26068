"""Comprehensive tests for SkyZen Personal Weather AI Conversation State Architecture.

Validates the 8 core conversational scenarios:
1. New conversation
2. Follow-up (pronouns/elliptical resolution)
3. Context continuation (topic persistence)
4. Topic change (switching city/subject)
5. Clarification response (answering pending prompt)
6. Ambiguous request (multiple locations or missing location)
7. Context expiration / reset
8. Safety-critical context preservation (severe alerts retained across follow-ups)
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from ai.memory.models import (
    ConversationState,
    ConversationTurn,
    ClarificationState,
    TurnTypeEnum,
)
from ai.memory.state_service import ConversationStateService, state_service
from backend.services.chat_integration_service import ChatIntegrationService


@pytest.fixture
def service():
    """Provides a fresh ConversationStateService instance."""
    return ConversationStateService(ttl_seconds=300, max_turns=10)


class TestSkyZenConversationStateService:
    """Unit tests for the standalone ConversationStateService engine."""

    def test_01_new_conversation(self, service: ConversationStateService):
        """Scenario 1: Starting a new conversation sets up clean state and detects NEW_QUESTION."""
        conv_id = "test-conv-new-1"
        st = service.get_state(conv_id)
        assert st.turn_index == 0
        assert st.active_location is None
        assert st.safety_critical_context is None

        query = "What is the weather in Chennai today?"
        analysis = service.analyze_turn(query, st)

        assert analysis.turn_type == TurnTypeEnum.NEW_QUESTION
        assert analysis.resolved_location == "Chennai"
        assert analysis.resolved_date == "today"

        # Update state
        updated = service.update_state(
            conversation_id=conv_id,
            user_message=query,
            assistant_message="Chennai is 31°C with clear skies.",
            resolved_ctx=analysis
        )
        assert updated.turn_index == 1
        assert updated.active_location == "Chennai"
        assert updated.previous_user_question == query
        assert len(updated.turns) == 2

    def test_02_follow_up(self, service: ConversationStateService):
        """Scenario 2: Follow-up question resolves implicit pronoun references ("there", "tomorrow")."""
        conv_id = "test-conv-followup-2"
        st = service.get_state(conv_id)
        
        # Turn 1: Chennai
        t1_analysis = service.analyze_turn("Will it rain in Chennai today?", st)
        service.update_state(conv_id, "Will it rain in Chennai today?", "Low rain chance in Chennai.", t1_analysis)

        # Turn 2: Follow-up with "there" and "tomorrow"
        st_after_t1 = service.get_state(conv_id)
        t2_query = "What about tomorrow there?"
        t2_analysis = service.analyze_turn(t2_query, st_after_t1)

        assert t2_analysis.turn_type == TurnTypeEnum.FOLLOW_UP
        assert t2_analysis.resolved_location == "Chennai"
        assert "location" in t2_analysis.inherited_fields
        assert "Chennai" in t2_analysis.resolved_message
        assert t2_analysis.resolved_date == "tomorrow"

        # Check bounded context: contains only recent turn
        bounded = st_after_t1.to_bounded_context(max_turns=2)
        assert "Chennai" in bounded
        assert len(bounded.splitlines()) <= 5

    def test_03_context_continuation(self, service: ConversationStateService):
        """Scenario 3: Topic continuation preserves active location without explicit pronouns."""
        conv_id = "test-conv-continue-3"
        st = service.get_state(conv_id)
        
        # Turn 1: Madurai
        t1 = service.analyze_turn("Current temperature in Madurai", st)
        service.update_state(conv_id, "Current temperature in Madurai", "Madurai is 34°C.", t1)

        # Turn 2: "Is it very humid?" (no location mentioned)
        st_t2 = service.get_state(conv_id)
        t2 = service.analyze_turn("Is it very humid?", st_t2)

        assert t2.turn_type in (TurnTypeEnum.TOPIC_CONTINUATION, TurnTypeEnum.FOLLOW_UP)
        assert t2.resolved_location == "Madurai"
        assert "location" in t2.inherited_fields

    def test_04_topic_change(self, service: ConversationStateService):
        """Scenario 4: Topic change detects explicit switch to a new city."""
        conv_id = "test-conv-topic-change-4"
        st = service.get_state(conv_id)

        # Turn 1: Coimbatore
        t1 = service.analyze_turn("Weather in Coimbatore", st)
        service.update_state(conv_id, "Weather in Coimbatore", "Coimbatore is 28°C.", t1)

        # Turn 2: Switch to Tirunelveli
        st_t2 = service.get_state(conv_id)
        t2 = service.analyze_turn("Actually how about Tirunelveli?", st_t2)

        assert t2.turn_type in (TurnTypeEnum.TOPIC_CHANGE, TurnTypeEnum.EXPLICIT_CORRECTION)
        assert t2.resolved_location == "Tirunelveli"

        updated = service.update_state(conv_id, "Actually how about Tirunelveli?", "Tirunelveli is 32°C.", t2)
        assert updated.active_location == "Tirunelveli"
        assert updated.recent_locations == ["Coimbatore", "Tirunelveli"]

    def test_05_clarification_response(self, service: ConversationStateService):
        """Scenario 5: User answers a pending clarification request."""
        conv_id = "test-conv-clarif-5"
        st = service.get_state(conv_id)

        # System requested clarification previously
        st.clarification_state = ClarificationState(
            needed=True,
            field="location",
            prompt="Which city or district would you like weather for?",
            pending_query="What's the weather?"
        )

        # User responds with just city name
        t1 = service.analyze_turn("Salem", st)
        assert t1.turn_type == TurnTypeEnum.CLARIFICATION_RESPONSE
        assert t1.resolved_location == "Salem"

        # Update state clears clarification needed
        updated = service.update_state(conv_id, "Salem", "Salem is currently 30°C.", t1)
        assert updated.active_location == "Salem"
        assert updated.clarification_state.needed is False

    def test_06_ambiguous_request(self, service: ConversationStateService):
        """Scenario 6: Ambiguous weather request triggers structured clarification."""
        conv_id = "test-conv-ambig-6"
        st = service.get_state(conv_id)

        # Query with weather inquiry but absolutely no location in query or state
        t1 = service.analyze_turn("Will it rain heavily today?", st)
        assert t1.turn_type == TurnTypeEnum.AMBIGUOUS_REQUEST
        assert t1.is_ambiguous is True
        assert t1.clarification.needed is True
        assert "district or city" in t1.clarification.prompt.lower()

    def test_07_context_expiration_and_reset(self, service: ConversationStateService):
        """Scenario 7: State resets explicitly or upon TTL expiration."""
        conv_id = "test-conv-expire-7"
        st = service.get_state(conv_id)
        
        # Turn 1
        t1 = service.analyze_turn("Weather in Ooty", st)
        service.update_state(conv_id, "Weather in Ooty", "Ooty is 16°C and misty.", t1)
        assert service.get_state(conv_id).active_location == "Ooty"

        # A) Explicit reset query
        reset_t = service.analyze_turn("Start fresh, clear context", service.get_state(conv_id))
        assert reset_t.turn_type == TurnTypeEnum.NEW_QUESTION

        service.reset_state(conv_id)
        fresh_st = service.get_state(conv_id)
        assert fresh_st.active_location is None
        assert fresh_st.turn_index == 0

        # B) TTL expiration
        expired_st = service.get_state(conv_id)
        expired_st.updated_at = datetime.now(timezone.utc) - timedelta(seconds=1000)
        # Accessing state triggers expiration cleanup
        renewed_st = service.get_state(conv_id)
        assert renewed_st.turn_index == 0

    def test_08_safety_critical_context_preservation(self, service: ConversationStateService):
        """Scenario 8: Severe IMD warning is preserved across follow-up turns."""
        conv_id = "test-conv-safety-8"
        st = service.get_state(conv_id)

        # Turn 1: User asks about Chennai during severe cyclone alert
        t1 = service.analyze_turn("Is there any cyclone near Chennai?", st)
        service.update_state(
            conversation_id=conv_id,
            user_message="Is there any cyclone near Chennai?",
            assistant_message="RED ALERT: Severe Cyclonic Storm approaching coastal Chennai. Evacuate low-lying areas.",
            resolved_ctx=t1,
            safety_alerts=[{
                "title": "Cyclone Warning Red Alert",
                "severity": "RED",
                "area": "Chennai",
                "instructions": "Do not venture out."
            }]
        )

        st_after_t1 = service.get_state(conv_id)
        assert st_after_t1.safety_critical_context is not None
        assert st_after_t1.safety_critical_context["has_active_warning"] is True
        assert st_after_t1.safety_critical_context["severity"] == "RED"

        # Turn 2: Innocent follow-up question ("What about tomorrow's temperature?")
        t2 = service.analyze_turn("What about tomorrow's temperature?", st_after_t1)
        assert t2.turn_type == TurnTypeEnum.FOLLOW_UP
        assert t2.resolved_location == "Chennai"

        # Bounded context contains the safety-critical warning!
        bounded_ctx = st_after_t1.to_bounded_context(max_turns=2)
        assert "ACTIVE OFFICIAL WARNING: [RED] Cyclone Warning Red Alert" in bounded_ctx

        # Updating state without new alerts keeps existing safety context active for the same location
        updated = service.update_state(
            conv_id,
            "What about tomorrow's temperature?",
            "Tomorrow will remain turbulent with heavy rain.",
            t2
        )
        assert updated.safety_critical_context is not None
        assert updated.safety_critical_context["severity"] == "RED"


@pytest.mark.asyncio
class TestSkyZenIntegrationStatePipeline:
    """Integration tests validating the end-to-end chat service with conversation state."""

    async def test_end_to_end_clarification_and_followup(self):
        """Verifies end-to-end ambiguous request -> clarification -> resolved follow-up."""
        chat_service = ChatIntegrationService()
        conv_id = "e2e-state-test-1"

        # 1. Ambiguous query with no location
        resp1 = await chat_service.handle_chat_request(
            message="What is the weather like there?",
            conversation_id=conv_id,
            location_name=""
        )
        assert resp1["intent"] == "CLARIFICATION_NEEDED"
        assert resp1["conversation_state"] is not None
        assert resp1["conversation_state"]["clarification_state"]["needed"] is True

        # 2. User responds with city name
        resp2 = await chat_service.handle_chat_request(
            message="Coimbatore",
            conversation_id=conv_id
        )
        assert resp2["conversation_state"]["active_location"] == "Coimbatore"
        assert resp2["conversation_state"]["clarification_state"]["needed"] is False

        # 3. Follow-up query
        resp3 = await chat_service.handle_chat_request(
            message="And will it rain tomorrow?",
            conversation_id=conv_id
        )
        assert resp3["conversation_state"]["active_location"] == "Coimbatore"
        assert resp3["conversation_state"]["turn_type"] == "follow_up"
