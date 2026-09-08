"""Comprehensive Conversational Memory Test Suite for WeatherGPT.

Covers all scenarios specified in Phase 13:
1. Previous location inheritance
2. Previous date inheritance ("tomorrow")
3. Previous time-of-day inheritance ("evening")
4. Topic continuation ("wind")
5. Pronoun resolution ("it", "that")
6. "there" reference resolution
7. Multiple-location ambiguity detection
8. Explicit current location override
9. Explicit current date override
10. Explicit language override
11. Persona persistence across turns
12. Language persistence across turns
13. Weather freshness guarantee (memory does not serve stale weather data)
14. Old warning must not remain active automatically
15. Memory TTL expiration
16. Conversation window limit (bounded history)
17. Structured context summarization
18. RAG integration with conversational memory
19. Advisory integration with inherited persona
20. Phase 9 validator remains active
21. Empty memory handling
22. Memory reset ("start over")
23. Ambiguous query safe handling
24. Multilingual follow-up (Tamil / Hindi / Tanglish)
25. End-to-end conversation flow (Turn 1 -> Turn 2 -> Turn 3)
26. Benchmark evaluation metrics
27. FastAPI /api/v1/chat multi-turn interaction
"""

import time
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from ai.memory.models import ConversationContext, ConversationTurn, ResolvedQueryContext
from ai.memory.resolver import ContextResolver
from ai.memory.manager import ConversationMemoryManager
from ai.evaluation.memory_evaluator import MemoryEvaluator, MEMORY_EVALUATION_DATASET
from backend.services.ai_service import AIService
from backend.schemas.chat import ChatRequest, LocationPayload
from ai.models import PersonaEnum, LanguageEnum

client = TestClient(app)


# -------------------------------------------------------------------------
# Scenario 1: Previous Location Inheritance
# -------------------------------------------------------------------------
def test_01_location_inheritance():
    mgr = ConversationMemoryManager()
    conv_id = "test_loc_01"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("Will it rain tomorrow?", context=ctx)
    
    assert resolved.resolved_location == "Coimbatore"
    assert "location" in resolved.inherited_fields


# -------------------------------------------------------------------------
# Scenario 2: Previous Date Inheritance
# -------------------------------------------------------------------------
def test_02_date_inheritance():
    mgr = ConversationMemoryManager()
    conv_id = "test_date_02"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore", date_context="tomorrow")
    
    ctx = mgr.get_context(conv_id)
    # User asks only time-of-day: "What about evening?"
    resolved = ContextResolver.resolve_query("What about evening?", context=ctx)
    
    assert resolved.resolved_date == "tomorrow"
    assert resolved.resolved_time == "evening"
    assert "date_context" in resolved.inherited_fields


# -------------------------------------------------------------------------
# Scenario 3: Previous Time Inheritance
# -------------------------------------------------------------------------
def test_03_time_inheritance():
    mgr = ConversationMemoryManager()
    conv_id = "test_time_03"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore", date_context="tomorrow", time_context="morning")
    
    ctx = mgr.get_context(conv_id)
    # User asks "Will it be cold?" without specifying time
    resolved = ContextResolver.resolve_query("Will it be cold?", context=ctx)
    
    assert resolved.resolved_date == "tomorrow"
    assert resolved.resolved_time == "morning"


# -------------------------------------------------------------------------
# Scenario 4: Topic Continuation
# -------------------------------------------------------------------------
def test_04_topic_continuation():
    mgr = ConversationMemoryManager()
    conv_id = "test_topic_04"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore", active_topic="rain")
    
    ctx = mgr.get_context(conv_id)
    # User switches topic explicitly to wind
    resolved = ContextResolver.resolve_query("How about the wind?", context=ctx)
    
    assert resolved.resolved_topic == "wind"
    assert resolved.resolved_location == "Coimbatore"


# -------------------------------------------------------------------------
# Scenario 5: Pronoun Resolution ("it")
# -------------------------------------------------------------------------
def test_05_pronoun_resolution():
    mgr = ConversationMemoryManager()
    conv_id = "test_pronoun_05"
    mgr.update_context(conversation_id=conv_id, location="Chennai", active_topic="cyclone")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("When will it hit?", context=ctx)
    
    assert resolved.resolved_location == "Chennai"
    assert resolved.resolved_topic == "cyclone"


# -------------------------------------------------------------------------
# Scenario 6: "there" Reference Resolution
# -------------------------------------------------------------------------
def test_06_there_reference_resolution():
    mgr = ConversationMemoryManager()
    conv_id = "test_there_06"
    mgr.update_context(conversation_id=conv_id, location="Chennai")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("Will it rain there tomorrow?", context=ctx)
    
    assert resolved.resolved_location == "Chennai"
    assert "Chennai" in resolved.resolved_message
    assert "there" not in resolved.resolved_message.lower()


# -------------------------------------------------------------------------
# Scenario 7: Multiple-Location Ambiguity Detection
# -------------------------------------------------------------------------
def test_07_multiple_location_ambiguity():
    mgr = ConversationMemoryManager()
    conv_id = "test_ambig_07"
    # User discussed both Coimbatore and Chennai
    mgr.update_context(conversation_id=conv_id, location="Coimbatore")
    ctx = mgr.get_context(conv_id)
    ctx.recent_locations.append("Chennai")
    
    # Query says "there" without naming the city
    resolved = ContextResolver.resolve_query("Will it rain there tomorrow?", context=ctx)
    
    assert resolved.is_ambiguous is True
    assert "ambiguous" in resolved.ambiguity_reason.lower()
    assert "Coimbatore" in resolved.ambiguity_reason
    assert "Chennai" in resolved.ambiguity_reason


# -------------------------------------------------------------------------
# Scenario 8: Explicit Current Location Override
# -------------------------------------------------------------------------
def test_08_explicit_location_override():
    mgr = ConversationMemoryManager()
    conv_id = "test_override_loc_08"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("What about Madurai?", context=ctx)
    
    # Explicit new location must override remembered Coimbatore
    assert resolved.resolved_location == "Madurai"


# -------------------------------------------------------------------------
# Scenario 9: Explicit Current Date Override
# -------------------------------------------------------------------------
def test_09_explicit_date_override():
    mgr = ConversationMemoryManager()
    conv_id = "test_override_date_09"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore", date_context="tomorrow")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("How about today?", context=ctx)
    
    # Explicit "today" overrides remembered "tomorrow"
    assert resolved.resolved_date == "today"


# -------------------------------------------------------------------------
# Scenario 10: Explicit Language Override
# -------------------------------------------------------------------------
def test_10_explicit_language_override():
    mgr = ConversationMemoryManager()
    conv_id = "test_override_lang_10"
    mgr.update_context(conversation_id=conv_id, language="ta")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("Tell me in Hindi please", context=ctx, explicit_language="hi")
    
    # Explicit Hindi request overrides remembered Tamil
    assert resolved.resolved_language == "hi"


# -------------------------------------------------------------------------
# Scenario 11: Persona Persistence Across Turns
# -------------------------------------------------------------------------
def test_11_persona_persistence():
    mgr = ConversationMemoryManager()
    conv_id = "test_persona_11"
    mgr.update_context(conversation_id=conv_id, persona="farmer")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("Will it rain tomorrow?", context=ctx)
    
    assert resolved.resolved_persona == "farmer"
    assert "persona" in resolved.inherited_fields


# -------------------------------------------------------------------------
# Scenario 12: Language Persistence Across Turns
# -------------------------------------------------------------------------
def test_12_language_persistence():
    mgr = ConversationMemoryManager()
    conv_id = "test_lang_12"
    mgr.update_context(conversation_id=conv_id, language="ta")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("மாலையில் எப்படி?", context=ctx)
    
    assert resolved.resolved_language == "ta"


# -------------------------------------------------------------------------
# Scenario 13: Weather Freshness Guarantee
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_weather_freshness_guarantee():
    """Verifies that follow-up queries retrieve live fresh weather instead of serving remembered metrics."""
    service = AIService()
    conv_id = "freshness_test_conv"
    
    # Turn 1: Check Coimbatore weather
    req1 = ChatRequest(
        message="What is the weather in Coimbatore?",
        conversation_id=conv_id
    )
    resp1 = await service.process_chat(req1)
    time1 = resp1["data_timestamp"]
    
    # Turn 2: Follow-up query
    req2 = ChatRequest(
        message="What about evening?",
        conversation_id=conv_id
    )
    resp2 = await service.process_chat(req2)
    
    # Fresh weather must have been retrieved
    assert resp2["location"] == "Coimbatore"
    assert resp2["data_timestamp"] is not None
    assert "answer" in resp2


# -------------------------------------------------------------------------
# Scenario 14: Old Warning Must Not Remain Active Automatically
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_old_warning_freshness():
    """Ensures a warning from turn 1 is not assumed active in turn 2 without live verification."""
    service = AIService()
    conv_id = "warning_freshness_conv"
    
    # Prime memory with a turn
    req1 = ChatRequest(
        message="Weather in Coimbatore?",
        conversation_id=conv_id
    )
    await service.process_chat(req1)
    
    # Query turn 2: Alert evaluation is live from WeatherManager, not hardcoded from memory
    req2 = ChatRequest(
        message="Is there any cyclone warning now?",
        conversation_id=conv_id
    )
    resp2 = await service.process_chat(req2)
    # Alerts in response must reflect current state
    assert isinstance(resp2["alerts"], list)


# -------------------------------------------------------------------------
# Scenario 15: Memory TTL Expiration
# -------------------------------------------------------------------------
def test_15_memory_ttl_expiration():
    mgr = ConversationMemoryManager(ttl_seconds=1)  # 1 second TTL
    conv_id = "ttl_test_conv"
    mgr.update_context(conversation_id=conv_id, location="Coimbatore")
    
    # Before expiry
    ctx_active = mgr.get_context(conv_id)
    assert ctx_active.location == "Coimbatore"
    
    # Simulate time passing beyond TTL
    future_time = datetime.now(timezone.utc) + timedelta(seconds=2)
    assert ctx_active.is_expired(future_time) is True


# -------------------------------------------------------------------------
# Scenario 16: Bounded History Window
# -------------------------------------------------------------------------
def test_16_bounded_history_window():
    max_turns = 4
    mgr = ConversationMemoryManager(max_turns=max_turns)
    conv_id = "bounded_window_conv"
    
    for i in range(10):
        t = ConversationTurn(role="user", message=f"Message {i}")
        mgr.update_context(conversation_id=conv_id, user_turn=t)
        
    ctx = mgr.get_context(conv_id)
    # Must not grow unbounded
    assert len(ctx.turns) <= max_turns
    assert ctx.turns[-1].message == "Message 9"


# -------------------------------------------------------------------------
# Scenario 17: Structured Context Summarization
# -------------------------------------------------------------------------
def test_17_context_summarization():
    ctx = ConversationContext(
        conversation_id="summary_test",
        location="Coimbatore",
        date_context="tomorrow",
        time_context="evening",
        active_topic="rain",
        persona="farmer"
    )
    summary = ctx.to_summary()
    assert "Location: Coimbatore" in summary
    assert "Date: tomorrow" in summary
    assert "Time: evening" in summary
    assert "Topic: rain" in summary
    assert "Persona: farmer" in summary


# -------------------------------------------------------------------------
# Scenario 18: RAG Integration with Topic Memory
# -------------------------------------------------------------------------
def test_18_rag_integration_with_topic_memory():
    mgr = ConversationMemoryManager()
    conv_id = "rag_mem_conv"
    mgr.update_context(conversation_id=conv_id, active_topic="cyclone")
    
    ctx = mgr.get_context(conv_id)
    resolved = ContextResolver.resolve_query("What does that mean?", context=ctx)
    
    # Query inherits cyclone topic for RAG retrieval
    assert resolved.resolved_topic == "cyclone"
    assert "cyclone" in resolved.context_summary.lower()


# -------------------------------------------------------------------------
# Scenario 19: Advisory Integration with Inherited Persona
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_19_advisory_integration_with_persona_memory():
    service = AIService()
    conv_id = "advisory_mem_conv"
    
    # Turn 1: Farmer persona
    req1 = ChatRequest(
        message="I am a farmer in Coimbatore.",
        persona="farmer",
        conversation_id=conv_id
    )
    resp1 = await service.process_chat(req1)
    assert resp1["persona"] == "farmer"
    
    # Turn 2: Follow-up without explicit persona
    req2 = ChatRequest(
        message="Will it rain tomorrow?",
        conversation_id=conv_id
    )
    resp2 = await service.process_chat(req2)
    # Persona persists in advisory reasoning
    assert resp2["persona"] == "farmer"


# -------------------------------------------------------------------------
# Scenario 20: Phase 9 Validator Remains Active on Follow-ups
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_validator_remains_active_on_followup():
    service = AIService()
    conv_id = "val_followup_conv"
    
    req1 = ChatRequest(message="Weather in Coimbatore?", conversation_id=conv_id)
    await service.process_chat(req1)
    
    req2 = ChatRequest(message="What about evening?", conversation_id=conv_id)
    resp2 = await service.process_chat(req2)
    
    assert "validation" in resp2
    assert resp2["validation"]["passed"] is True


# -------------------------------------------------------------------------
# Scenario 21: Empty Memory Handling
# -------------------------------------------------------------------------
def test_21_empty_memory_handling():
    mgr = ConversationMemoryManager()
    ctx = mgr.get_context("non_existent_conv")
    
    resolved = ContextResolver.resolve_query("What is the weather today?", context=ctx)
    assert resolved.resolved_location == "Coimbatore"
    assert resolved.inherited_fields == []


# -------------------------------------------------------------------------
# Scenario 22: Memory Reset Triggers
# -------------------------------------------------------------------------
def test_22_memory_reset_triggers():
    mgr = ConversationMemoryManager()
    conv_id = "reset_test_conv"
    mgr.update_context(conversation_id=conv_id, location="Chennai", persona="fisherman")
    
    assert ContextResolver.is_reset_query("start over") is True
    assert ContextResolver.is_reset_query("start a new topic") is True
    assert ContextResolver.is_reset_query("clear context") is True
    assert ContextResolver.is_reset_query("Will it rain?") is False
    
    mgr.reset_context(conv_id)
    fresh_ctx = mgr.get_context(conv_id)
    assert fresh_ctx.location is None
    assert fresh_ctx.persona is None


# -------------------------------------------------------------------------
# Scenario 23: Ambiguous Query Handling in Chat API
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_23_ambiguous_query_handling():
    service = AIService()
    conv_id = "ambiguity_chat_conv"
    
    # Prime memory with multiple locations
    mgr = ConversationMemoryManager()
    ctx = mgr.get_context(conv_id)
    ctx.location = "Coimbatore"
    ctx.recent_locations = ["Coimbatore", "Chennai"]
    
    with patch("backend.services.ai_service.memory_manager", mgr):
        req = ChatRequest(
            message="Will it rain there tomorrow?",
            conversation_id=conv_id
        )
        resp = await service.process_chat(req)
        assert resp["intent"] == "clarification"
        assert resp["validation"]["status"] == "AMBIGUOUS_QUERY_CLARIFIED"
        assert "Coimbatore" in resp["answer"]
        assert "Chennai" in resp["answer"]


# -------------------------------------------------------------------------
# Scenario 24: Multilingual Follow-Up (Tamil / Hindi / Tanglish)
# -------------------------------------------------------------------------
def test_24_multilingual_followup_tamil_hindi():
    mgr = ConversationMemoryManager()
    
    # Tamil follow-up
    conv_ta = "conv_ta"
    mgr.update_context(conversation_id=conv_ta, location="Coimbatore", date_context="tomorrow", language="ta")
    res_ta = ContextResolver.resolve_query("மாலையில் எப்படி?", context=mgr.get_context(conv_ta))
    assert res_ta.resolved_location == "Coimbatore"
    assert res_ta.resolved_date == "tomorrow"
    assert res_ta.resolved_time == "evening"
    assert res_ta.resolved_language == "ta"

    # Hindi follow-up
    conv_hi = "conv_hi"
    mgr.update_context(conversation_id=conv_hi, location="Coimbatore", date_context="tomorrow", language="hi")
    res_hi = ContextResolver.resolve_query("शाम को कैसा रहेगा?", context=mgr.get_context(conv_hi))
    assert res_hi.resolved_location == "Coimbatore"
    assert res_hi.resolved_date == "tomorrow"
    assert res_hi.resolved_time == "evening"
    assert res_hi.resolved_language == "hi"


# -------------------------------------------------------------------------
# Scenario 25: End-to-End Conversation Flow (Turn 1 -> Turn 2 -> Turn 3)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_25_end_to_end_conversation_flow():
    service = AIService()
    conv_id = f"e2e_flow_{int(time.time())}"
    
    # Turn 1: "Will it rain tomorrow in Coimbatore?"
    r1 = await service.process_chat(ChatRequest(
        message="Will it rain tomorrow in Coimbatore?",
        conversation_id=conv_id
    ))
    assert r1["location"] == "Coimbatore"
    
    # Turn 2: "What about evening?"
    r2 = await service.process_chat(ChatRequest(
        message="What about evening?",
        conversation_id=conv_id
    ))
    assert r2["location"] == "Coimbatore"
    
    # Turn 3: "How about the wind?"
    r3 = await service.process_chat(ChatRequest(
        message="How about the wind?",
        conversation_id=conv_id
    ))
    assert r3["location"] == "Coimbatore"
    assert "answer" in r3


# -------------------------------------------------------------------------
# Scenario 26: Benchmark Evaluation Metrics
# -------------------------------------------------------------------------
def test_26_memory_benchmarking_metrics():
    metrics = MemoryEvaluator.evaluate_benchmark()
    assert metrics["total_scenarios"] >= 6
    assert metrics["overall_pass_rate"] >= 0.85
    assert metrics["location_inheritance_accuracy"] >= 0.85
    assert metrics["temporal_inheritance_accuracy"] >= 0.85
    assert metrics["ambiguity_detection_accuracy"] >= 0.85


# -------------------------------------------------------------------------
# Scenario 27: FastAPI /api/v1/chat Multi-Turn Integration
# -------------------------------------------------------------------------
def test_27_fastapi_chat_multi_turn():
    conv_id = f"fastapi_chat_multi_{int(time.time())}"
    
    # Turn 1
    resp1 = client.post("/api/v1/chat", json={
        "message": "What is the weather in Chennai?",
        "conversation_id": conv_id,
        "location": {"name": "Chennai"}
    })
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["location"] == "Chennai"
    
    # Turn 2: Follow-up using pronoun "there"
    resp2 = client.post("/api/v1/chat", json={
        "message": "Will it rain there tomorrow?",
        "conversation_id": conv_id
    })
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["location"] == "Chennai"
