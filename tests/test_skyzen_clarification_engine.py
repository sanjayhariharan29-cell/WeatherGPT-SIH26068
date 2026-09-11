"""Comprehensive tests for SkyZen Intelligent Clarification Engine.

Validates:
1. Marine area clarification ("Can I go to sea?" -> "Which area are you planning to fish in?")
2. Fishing query location clarification ("Can I go fishing tomorrow?" -> "Which area are you planning to fish in?")
3. Intent resumption (answering "Near Rameswaram." resumes marine weather analysis under fishing_decision)
4. College commute direct answer when context exists vs minimal clarification when missing
5. Structured missing-information model coverage (location, date, time, activity, destination, ambiguous location, insufficient marine area, insufficient safety context)
6. Natural, conversational prompts (strictly no technical jargon e.g. 'Enter latitude and longitude')
7. Multilingual clarification support across English, Tamil, and Hindi
"""

import pytest
from typing import Dict, Any

from ai.clarification import (
    clarification_engine,
    MissingInformationType,
    MissingInformation,
    CLARIFICATION_PROMPTS,
)
from ai.memory.models import (
    ConversationState,
    ClarificationState,
    TurnTypeEnum,
)
from ai.memory.state_service import ConversationStateService
from ai.nlu import parse_query
from ai.models import IntentEnum


@pytest.fixture
def state_service() -> ConversationStateService:
    """Provides a fresh instance of ConversationStateService."""
    return ConversationStateService(ttl_seconds=300, max_turns=10)


class TestIntelligentClarificationEngineUnit:
    """Unit tests for the IntelligentClarificationEngine evaluator and prompt generator."""

    def test_insufficient_marine_area_detection(self):
        """Validates 'Can I go to sea?' triggers INSUFFICIENT_MARINE_AREA without guessing."""
        query = "Can I go to sea?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-marine-1")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st)
        assert missing is not None
        assert missing.missing_type == MissingInformationType.INSUFFICIENT_MARINE_AREA
        assert missing.field == "marine_area"
        assert missing.severity == "safety_critical"
        assert missing.prompt == "Which area are you planning to fish in?"
        assert missing.intent_to_resume == IntentEnum.FISHING_DECISION.value

    def test_fishing_tomorrow_missing_location(self):
        """Validates 'Can I go fishing tomorrow?' triggers marine area clarification."""
        query = "Can I go fishing tomorrow?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-marine-2")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st)
        assert missing is not None
        assert missing.missing_type == MissingInformationType.INSUFFICIENT_MARINE_AREA
        assert missing.prompt == "Which area are you planning to fish in?"
        assert missing.intent_to_resume == IntentEnum.FISHING_DECISION.value

    def test_college_commute_direct_answer_when_context_exists(self):
        """Validates 'Can I go to college?' needs NO clarification when location and context exist."""
        query = "Can I go to college?"
        nlu = parse_query(query)
        st = ConversationState(
            conversation_id="test-college-1",
            active_location="Coimbatore",
            active_activity="college",
            active_destination="college"
        )

        missing = clarification_engine.evaluate_clarification_needed(
            query, nlu, st, explicit_location="Coimbatore"
        )
        assert missing is None  # Directly answers without redundant questions

    def test_college_commute_missing_location(self):
        """Validates 'Can I go to college?' asks for location when no location context exists."""
        query = "Can I go to college?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-college-2")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st)
        assert missing is not None
        assert missing.missing_type == MissingInformationType.MISSING_LOCATION
        assert "Where are you planning to go?" in missing.prompt
        assert missing.intent_to_resume == IntentEnum.COLLEGE_COMMUTE.value

    def test_travel_missing_destination(self):
        """Validates travel decision with missing destination."""
        query = "Can I travel today?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-travel-1")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st)
        assert missing is not None
        assert missing.missing_type == MissingInformationType.MISSING_DESTINATION
        assert missing.prompt == "Where are you heading to?"

    def test_farming_missing_date(self):
        """Validates farming spraying query with location but missing date."""
        query = "Can I spray pesticides in Madurai?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-farm-1", active_location="Madurai")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st, explicit_location="Madurai")
        assert missing is not None
        assert missing.missing_type == MissingInformationType.MISSING_DATE
        assert missing.prompt == "Which day or date are you planning for?"

    def test_insufficient_safety_context(self):
        """Validates bare 'Is it safe?' with no context triggers safety context clarification."""
        query = "Is it safe?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-safe-1")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st)
        assert missing is not None
        assert missing.missing_type == MissingInformationType.INSUFFICIENT_SAFETY_CONTEXT
        assert missing.prompt == "Which location and activity would you like me to check safety for?"

    def test_no_technical_jargon_in_prompts(self):
        """Verifies clarification prompts NEVER ask for raw coordinates or technical jargon."""
        forbidden = ["latitude", "longitude", "coordinates", "gps", "iso-8601", "decimal", "geohash"]
        for m_type, prompts in CLARIFICATION_PROMPTS.items():
            for lang, prompt_str in prompts.items():
                lower = prompt_str.lower()
                for f in forbidden:
                    assert f not in lower, f"Forbidden technical jargon '{f}' found in {m_type} [{lang}]: '{prompt_str}'"


class TestClarificationIntentResumption:
    """Validates multi-turn intent resumption when user answers clarification."""

    def test_marine_query_resumption(self, state_service: ConversationStateService):
        """Acceptance Test:
        User: 'Can I go to sea?'
        SkyZen: 'Which area are you planning to fish in?'
        User: 'Near Rameswaram.'
        SkyZen: resumes fishing_decision and marine analysis with location='Rameswaram'.
        """
        conv_id = "test-resume-marine-1"
        st = state_service.get_state(conv_id)

        # Turn 1: User asks "Can I go to sea?"
        t1 = state_service.analyze_turn("Can I go to sea?", st)
        assert t1.turn_type == TurnTypeEnum.AMBIGUOUS_REQUEST
        assert t1.is_ambiguous is True
        assert t1.clarification.needed is True
        assert t1.clarification.missing_type == MissingInformationType.INSUFFICIENT_MARINE_AREA.value
        assert t1.clarification.prompt == "Which area are you planning to fish in?"
        assert t1.clarification.pending_intent == IntentEnum.FISHING_DECISION.value

        # Save state with clarification prompt
        st = state_service.update_state(
            conversation_id=conv_id,
            user_message="Can I go to sea?",
            assistant_message=t1.clarification.prompt,
            resolved_ctx=t1
        )
        assert st.turn_index == 1
        assert st.clarification_state.needed is True
        assert st.clarification_state.pending_intent == IntentEnum.FISHING_DECISION.value

        # Turn 2: User responds "Near Rameswaram."
        t2 = state_service.analyze_turn("Near Rameswaram.", st)
        assert t2.turn_type == TurnTypeEnum.CLARIFICATION_RESPONSE
        assert t2.is_ambiguous is False
        assert t2.clarification.needed is False
        # Resumes original intent:
        assert t2.resolved_intent == IntentEnum.FISHING_DECISION.value
        # Resolves location:
        assert t2.resolved_location == "Rameswaram"
        # Context is enriched:
        assert "Can I go to sea?" in t2.resolved_message
        assert "Rameswaram" in t2.resolved_message

        # State update fulfills clarification
        updated_st = state_service.update_state(
            conversation_id=conv_id,
            user_message="Near Rameswaram.",
            assistant_message="Wind speeds near Rameswaram are moderate at 12 knots. Wave heights under 1.5m; fishing is safe today.",
            resolved_ctx=t2
        )
        assert updated_st.turn_index == 2
        assert updated_st.active_location == "Rameswaram"
        assert updated_st.current_intent == IntentEnum.FISHING_DECISION.value
        assert updated_st.clarification_state.needed is False

    def test_college_commute_resumption(self, state_service: ConversationStateService):
        """Acceptance Test:
        User: 'Can I go to college?' (no initial location)
        SkyZen asks for location: 'Where are you planning to go? Please specify your district or city.'
        User: 'In Coimbatore'
        SkyZen resumes college_commute for Coimbatore.
        """
        conv_id = "test-resume-college-1"
        st = state_service.get_state(conv_id)

        # Turn 1
        t1 = state_service.analyze_turn("Can I go to college?", st)
        assert t1.turn_type == TurnTypeEnum.AMBIGUOUS_REQUEST
        assert t1.clarification.needed is True
        assert t1.clarification.pending_intent == IntentEnum.COLLEGE_COMMUTE.value

        st = state_service.update_state(
            conversation_id=conv_id,
            user_message="Can I go to college?",
            assistant_message=t1.clarification.prompt,
            resolved_ctx=t1
        )

        # Turn 2: User specifies city
        t2 = state_service.analyze_turn("In Coimbatore", st)
        assert t2.turn_type == TurnTypeEnum.CLARIFICATION_RESPONSE
        assert t2.resolved_location == "Coimbatore"
        assert t2.resolved_intent == IntentEnum.COLLEGE_COMMUTE.value
        assert t2.resolved_activity == "college"
        assert t2.is_ambiguous is False


class TestMultilingualClarificationPrompts:
    """Validates language-aware clarification prompts across Tamil and Hindi."""

    def test_tamil_marine_clarification(self):
        """Validates Tamil marine clarification prompt."""
        query = "நான் கடலுக்கு செல்லலாமா?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-ta-marine", preferred_language="ta")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st, language="ta")
        assert missing is not None
        assert missing.prompt == "நீங்கள் எந்தக் கடல் பகுதியில் மீன்பிடிக்கத் திட்டமிடுகிறீர்கள்?"

    def test_hindi_marine_clarification(self):
        """Validates Hindi marine clarification prompt."""
        query = "क्या मैं समुद्र में जा सकता हूँ?"
        nlu = parse_query(query)
        st = ConversationState(conversation_id="test-hi-marine", preferred_language="hi")

        missing = clarification_engine.evaluate_clarification_needed(query, nlu, st, language="hi")
        assert missing is not None
        assert missing.prompt == "आप किस क्षेत्र में मछली पकड़ने की योजना बना रहे हैं?"

    def test_tamil_location_clarification(self):
        """Validates Tamil location clarification prompt."""
        prompt = clarification_engine.get_prompt(MissingInformationType.MISSING_LOCATION, language="ta")
        assert "எங்கு செல்ல" in prompt

    def test_hindi_location_clarification(self):
        """Validates Hindi location clarification prompt."""
        prompt = clarification_engine.get_prompt(MissingInformationType.MISSING_LOCATION, language="hi")
        assert "कहाँ जाने" in prompt
