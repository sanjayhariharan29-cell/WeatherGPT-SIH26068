# Phase 13 — AI Conversation Memory & Context

**Role:** Person 1 (AI & Weather Intelligence Stack)  
**Status:** COMPLETE  
**Repository Branch:** `main`  
**Dependencies:** Phase 0–12 completed (NLU, Reasoner, Hazards, Advisory, LLM, Multilingual, Response Validation, Evaluation, FastAPI AI Integration, Voice AI)

---

## 1. Executive Summary

Phase 13 establishes safe short-term conversational context memory for WeatherGPT. It enables the conversational AI to seamlessly resolve natural multi-turn follow-up queries (e.g., *"What about evening?"*, *"Will it rain there tomorrow?"*, *"How about the wind?"*, *"Should I spray pesticide then?"*) without requiring the user to repetitively restate location, date, persona, or language context.

### The Cardinal Rule: Memory Context != Weather Truth
```
User Query ("What about evening?")
       │
       ▼
[ContextResolver] + [ConversationMemoryManager]
       │ (Inherits Location: Coimbatore, Date: Tomorrow, Time: Evening)
       ▼
Resolved Query Context
       │
       ▼
[WeatherManager.get_ai_weather_input()]  <-- LIVE, FRESH METEOROLOGICAL TELEMETRY
       │
       ▼
[WeatherReasoner] (Evaluates Fresh Sensor & Forecast Data)
       │
       ▼
[HazardDetectionEngine] (Calibrated against Live Physical Thresholds)
       │
       ▼
[AdvisoryEngine] (Persona Guidance for Farmer/Fisherman/Student)
       │
       ▼
[GroundedLLMGenerator] (Prompt contains Resolved Query + Structured Context Summary)
       │
       ▼
[ResponseValidator] (MANDATORY Phase 9 Anti-Hallucination Gate)
       │
       ▼
Validated Conversational Answer
```

Conversational memory stores **contextual metadata**, never stale observation values. Current meteorological conditions, forecast consensus, and severe weather warnings are **always** freshly ingested and verified.

---

## 2. Memory Types & Categorization

To avoid treating all memory equally, WeatherGPT partitions context into four distinct layers:

1. **Session Context:**
   - Primary location (`location_name`, `latitude`, `longitude`).
   - Temporal anchor (`date_context` e.g., "tomorrow", `time_context` e.g., "evening").
   - Active user persona (`persona` e.g., "farmer", "fisherman", "student").

2. **Conversational References:**
   - Spatial pronouns and deictic markers (`"there"`, `"that place"`, `"same location"`, `"அங்கே"`, `"वहाँ"`).
   - Temporal references (`"then"`, `"at that time"`).
   - Active meteorological topic (`active_topic` e.g., "rain", "wind", "cyclone", "temperature").

3. **User Preferences:**
   - Preferred response language (`language` e.g., "ta", "hi", "en").
   - Transliterated script mode (Tanglish, Hinglish).

4. **Recent Chat History:**
   - Bounded chronological queue of recent turns (`ConversationTurn`).
   - Limited strictly to the last 10 turns (prevents memory bloat and prompt token exhaustion).

---

## 3. Memory Schema & Models

Defined in [`ai/memory/models.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/memory/models.py):

### `ConversationContext`
```python
class ConversationContext(BaseModel):
    conversation_id: str
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    language: Optional[str] = None
    persona: Optional[str] = None
    date_context: Optional[str] = None
    time_context: Optional[str] = None
    last_intent: Optional[str] = None
    active_topic: Optional[str] = None
    recent_entities: Dict[str, Any] = Field(default_factory=dict)
    recent_locations: List[str] = Field(default_factory=list)
    turns: List[ConversationTurn] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    ttl_seconds: int = 1800  # 30-minute sliding TTL
```

### `ResolvedQueryContext`
```python
class ResolvedQueryContext(BaseModel):
    original_message: str
    resolved_message: str
    resolved_location: str
    resolved_date: Optional[str] = None
    resolved_time: Optional[str] = None
    resolved_persona: str = "general"
    resolved_language: str = "en"
    resolved_topic: Optional[str] = None
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    inherited_fields: List[str] = Field(default_factory=list)
    context_summary: str = ""
```

---

## 4. Reference Resolution & Entity Inheritance

Defined in [`ai/memory/resolver.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/memory/resolver.py):

### 4.1 Pronoun & Deictic Resolution
- Recognizes references across English (`"there"`, `"that place"`, `"same place"`), Tamil (`"அங்கே"`, `"அங்க"`), and Hindi (`"वहाँ"`, `"वहां"`).
- Reconstructs enriched query strings for downstream modules while maintaining traceable provenance.

### 4.2 Temporal Inheritance
- If a query specifies only time-of-day (*"What about evening?"*), the date context (*"tomorrow"*) is automatically inherited.
- If a query specifies a new date (*"How about today?"*), it overrides the previous date while maintaining location and persona.

### 4.3 Topic Continuation & Switching
- If the user asks *"What about wind?"*, the location and temporal context carry forward, but the active topic updates to `"wind"`, preventing rain-specific assumptions from sticking.

### 4.4 Ambiguity Detection
- If multiple distinct cities were discussed recently (e.g., Coimbatore and Chennai), and the user says *"Will it rain there?"*:
  - The system **refuses to guess**.
  - Sets `is_ambiguous = True` with `ambiguity_reason = "Multiple locations discussed (Coimbatore, Chennai). Please specify which location."`
  - Returns a clear clarification question to the user.

---

## 5. Priority Hierarchy (Step 15)

When resolving query intent and parameters, WeatherGPT enforces strict precedence:
```
1. EXPLICIT CURRENT USER INPUT      (e.g., user types "in Madurai" or "in Hindi")
   ↓
2. CURRENT RETRIEVED WEATHER DATA   (Live sensor telemetry from WeatherManager)
   ↓
3. CURRENT OFFICIAL WARNINGS        (Active IMD CAP alerts)
   ↓
4. CURRENT NLU INTERPRETATION       (Phase 2 intent & entity parse)
   ↓
5. RECENT CONVERSATION CONTEXT      (Inherited location, date, persona, language)
   ↓
6. DEFAULTS                         (Coimbatore, today, general, English)
```

Memory **never** overrides explicit user instructions or fresh physical observations.

---

## 6. Freshness & Safety Guarantees

### 6.1 Weather Freshness Guarantee (Step 16)
- Historical observations mentioned in earlier turns are never returned as current truth.
- Every follow-up turn triggers live observation retrieval from `WeatherManager`.

### 6.2 Official Warning Freshness (Step 17)
- Official alerts are strictly evaluated in real-time.
- If a Red Warning existed 10 minutes ago but has since expired, memory does not falsely report it as active.
- Conversely, an active official warning cannot be forgotten or softened by conversational follow-ups.

---

## 7. TTL, Expiration & Bounded History

- **Sliding Window TTL:** Default context lifetime is **1800 seconds (30 minutes)**. Contexts inactive beyond this duration expire and reset automatically.
- **Bounded History Queue:** Bounded to the last **10 turns** (`max_turns = 10`), preventing unbounded memory growth.
- **Memory Cleanup:** `cleanup_expired()` periodically flushes stale sessions.

---

## 8. Compact Structured Summarization (Step 20 & 21)

Instead of feeding raw, noisy multi-turn transcripts to the LLM (which consumes excessive context tokens and risks hallucination), the system compiles a compact structured summary:
```
--- 8. SHORT-TERM CONVERSATIONAL CONTEXT ---
Recent Context: Location: Coimbatore | Date: tomorrow | Time: evening | Topic: rain | Persona: farmer | InheritedFromHistory: location, date_context, persona
[NOTICE: Context resolves conversational references only; live meteorological truth strictly comes from sections 1-4 above.]
```

This guarantees that the LLM understands conversational continuity while remaining strictly bounded by live meteorological truth.

---

## 9. Conversation Reset (Step 29)

Users can explicitly reset conversational memory using natural language triggers:
- English: `"start over"`, `"start a new topic"`, `"new topic"`, `"clear context"`, `"reset"`
- Tamil: `"புது தலைப்பு"`, `"மீண்டும் தொடங்கு"`
- Hindi: `"नए सिरे से"`, `"नया विषय"`

Upon detection, `memory_manager.reset_context(conversation_id)` clears all stored entities.

---

## 10. Evaluation Framework & Benchmark Metrics (Step 31 & 32)

Implemented in [`ai/evaluation/memory_evaluator.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/ai/evaluation/memory_evaluator.py):

| Metric | Measured Score | Target Threshold | Status |
|---|---|---|---|
| **Overall Pass Rate** | **100% (1.000)** | ≥ 85.0% | PASS |
| **Location Inheritance Accuracy** | **100% (1.000)** | ≥ 85.0% | PASS |
| **Temporal Inheritance Accuracy** | **100% (1.000)** | ≥ 85.0% | PASS |
| **Topic Continuation Accuracy** | **100% (1.000)** | ≥ 85.0% | PASS |
| **Ambiguity Detection Accuracy** | **100% (1.000)** | ≥ 85.0% | PASS |
| **Language Continuity Accuracy** | **100% (1.000)** | ≥ 85.0% | PASS |

---

## 11. Test Suite Verification

The comprehensive test suite [`tests/test_ai_memory_depth.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/tests/test_ai_memory_depth.py) validates 27 scenarios:
1. `test_01_location_inheritance`: Coimbatore carried to follow-up.
2. `test_02_date_inheritance`: "tomorrow" preserved when time is "evening".
3. `test_03_time_inheritance`: "morning" preserved across follow-up.
4. `test_04_topic_continuation`: rain switches cleanly to wind.
5. `test_05_pronoun_resolution`: "it" maps to cyclone topic.
6. `test_06_there_reference_resolution`: "there" resolves to Chennai.
7. `test_07_multiple_location_ambiguity`: flags ambiguity between Coimbatore and Chennai.
8. `test_08_explicit_location_override`: Madurai overrides Coimbatore.
9. `test_09_explicit_date_override`: "today" overrides "tomorrow".
10. `test_10_explicit_language_override`: Hindi overrides Tamil.
11. `test_11_persona_persistence`: Farmer persona carried forward.
12. `test_12_language_persistence`: Tamil dialogue continuity.
13. `test_13_weather_freshness_guarantee`: fresh observation retrieved on turn 2.
14. `test_14_old_warning_freshness`: live alert state takes precedence.
15. `test_15_memory_ttl_expiration`: TTL expiry removes stale context.
16. `test_16_bounded_history_window`: bounded to max turns.
17. `test_17_context_summarization`: compact summary generation.
18. `test_18_rag_integration_with_topic_memory`: RAG uses remembered topic.
19. `test_19_advisory_integration_with_persona_memory`: advisory uses remembered persona.
20. `test_20_validator_remains_active_on_followup`: Phase 9 validator enforces safety.
21. `test_21_empty_memory_handling`: safe fallback on new conversation.
22. `test_22_memory_reset_triggers`: "start over" clears memory.
23. `test_23_ambiguous_query_handling`: API returns clarification request.
24. `test_24_multilingual_followup_tamil_hindi`: multilingual follow-ups.
25. `test_25_end_to_end_conversation_flow`: 3-turn dialogue resolution.
26. `test_26_memory_benchmarking_metrics`: benchmark evaluation metrics.
27. `test_27_fastapi_chat_multi_turn`: live FastAPI `/api/v1/chat` endpoint multi-turn flow.

---

## 12. Limitations & Production Considerations

1. **In-Memory Storage:** The default `ConversationMemoryManager` uses thread-safe in-memory cache with TTL. In a multi-worker production cluster, a Redis-backed session adapter can replace or back the in-memory cache.
2. **Session Identification:** Memory relies on `conversation_id`. Clients that do not send a `conversation_id` receive single-turn processing without cross-request state leakage.

---

## 13. Next Phase

- **Phase 14:** Severe Weather End-to-End Safety Flow.
