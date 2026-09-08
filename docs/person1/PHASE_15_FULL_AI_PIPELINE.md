# WeatherGPT SIH26068 — Phase 15: Full AI Pipeline Integration
## Unified, Coherent AI Brain & End-to-End Safety Architecture

---

### 1. Canonical Entrypoint

WeatherGPT establishes a single canonical entrypoint for all meteorological reasoning and natural language intelligence:

```python
WeatherGPTPipeline.process_query(
    message: str,
    weather: Optional[WeatherRecord] = None,
    forecast: Optional[List[ForecastItem]] = None,
    active_alerts: Optional[List[OfficialAlert]] = None,
    secondary_weather: Optional[WeatherRecord] = None,
    persona: Optional[PersonaEnum] = None,
    target_language: Optional[str] = None,
    context_summary: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]
```

To accommodate standard convention across pipelines, `WeatherGPTPipeline.run` is defined as a canonical alias pointing directly to `WeatherGPTPipeline.process_query`.

Backend consumers (`AIService.process_chat` and `ChatIntegrationService.process_chat_query`) integrate directly with this canonical method, ensuring that no alternative, parallel, or competing reasoning engines exist.

---

### 2. Complete Pipeline Execution Flow

Every interaction converges into one deterministic and grounded execution pipeline:

```
                  USER INPUT (Text / Voice Transcript / API Request)
                                      ↓
                                [INPUT ADAPTERS]
                  (FastAPI ChatRequest / VoiceSessionAudio / CLI)
                                      ↓
                     [CONVERSATION MEMORY & RESOLUTION]
                 (Extracts prior location & temporal context)
                                      ↓
                               [PHASE 2 NLU]
             (Intent classification, entity extraction, lang/persona)
                                      ↓
                     [NORMALIZED WEATHER DATA BOUNDARY]
          (Fresh WeatherRecord, ForecastItems, OfficialAlerts from IMD/Open-Meteo)
                                      ↓
                         [PHASE 3 WEATHER REASONER]
         (Freshness, consistency, source agreement, deterministic risk)
                                      ↓
                         [PHASE 4 HAZARD DETECTION]
           (IMD-calibrated cyclone, extreme rain, heatwave, gale wind)
                                      ↓
                              [PHASE 6 RAG]
          (Supporting meteorological terminology & safety guidance)
                                      ↓
                         [PHASE 7 ADVISORY ENGINE]
           (Persona-specific actionable guidance: farmer, fisherman, etc.)
                                      ↓
                            [GROUNDED CONTEXT]
              (Frozen verified facts, alerts, hazards, advisories)
                                      ↓
                            [PHASE 5/8 LLM ENGINE]
           (Grounded natural language generation in En, Ta, Hi, Tanglish, Hinglish)
                                      ↓
                         [PHASE 9 RESPONSE VALIDATOR]
            (Anti-hallucination, numerical verification, warning guard)
                                      ↓
                  [DETERMINISTIC FALLBACK IF REJECTED / ERROR]
                                      ↓
                            [FINAL AI RESPONSE]
                                      ↓
                      [VOICE TTS OUTPUT (if requested)]
```

---

### 3. Input Adapters

Three input modalities feed into the exact same pipeline:
1. **Text Input (`ChatRequest`)**: Sent via FastAPI `/chat/completions` or `/api/v1/chat`.
2. **Voice Transcript (`VoiceAudioRequest` / `VoiceSession`)**: Processed by Phase 12 Speech-to-Text (STT) into text, which is then routed directly to the NLU without skipping any reasoning or validation stages.
3. **Internal API / Benchmark Scenarios**: Direct program calls passing structured requests for evaluation and automated integration testing.

---

### 4. Conversation Memory & Context Resolution

- **Boundary**: Memory produces *resolved conversational context* (e.g., location, date reference, prior topic). It **never defines current weather truth**.
- **Behavior**:
  - Follow-up queries such as *"What about tomorrow evening?"* resolve to `location="Coimbatore"`, `date="tomorrow"`, `time="evening"`.
  - The pipeline immediately retrieves **fresh weather observations and forecasts** for the resolved entity.
  - Multi-turn ambiguities fall back to clarification or last verified location without fabricating weather values.

---

### 5. NLU (Query Understanding)

Phase 2 NLU serves as the sole authoritative parser:
- **Language Detection**: Identifies English, Tamil, Hindi, Tanglish, and Hinglish.
- **Intent Categorization**: Categorizes queries into `current_weather`, `temperature`, `rain_forecast`, `weather_alert`, `outdoor_decision`, `air_quality`, `severe_weather_alert`, etc.
- **Entity Extraction**: Authoritatively extracts city/district names, dates (e.g., today, tomorrow, this weekend), time periods (morning, evening), and persona markers.

No secondary or unverified parser exists in voice or chat layers.

---

### 6. Weather Data Boundary

Core AI consumes strictly normalized domain objects:
- `WeatherRecord`: Standardized observation containing temperature, humidity, wind_speed, rain_probability, rainfall_amount_mm, source, observed_at, and retrieved_at.
- `ForecastItem`: Standardized interval forecast containing temporal labels, temperatures, precipitation probabilities, conditions, and wind speeds.
- `OfficialAlert`: Standardized meteorological warning containing severity, affected locations, validity window, and alert type.

The core AI engine has **zero dependencies** on raw IMD JSON, Open-Meteo JSON, SQL ORM models, or FastAPI HTTP request wrappers.

---

### 7. Weather Reasoner

All factual weather interpretation passes through Phase 3 `WeatherReasoner`:
- **Freshness Scoring**: Evaluates observation age against IMD standards (penalizing data older than 60-180 minutes).
- **Multi-Source Agreement**: Calculates divergence between primary (e.g., IMD) and secondary (e.g., Open-Meteo) weather readings.
- **Temporal Consistency**: Cross-checks observation trends with forecast data.
- **Deterministic Risk Rating**: Computes baseline severity levels (`low`, `medium`, `high`, `extreme`).

---

### 8. Hazard Detection

Hazard identification and severity classification are governed exclusively by Phase 4 deterministic rules:
- Calibrated directly against IMD warning thresholds (e.g., Heavy Rainfall >64.5mm, Extremely Heavy Rainfall >204.4mm, Gale Wind >62 km/h, Heatwave >40°C).
- The LLM is **never** permitted to originate or downgrade hazard classifications.

---

### 9. Meteorological Knowledge Grounding (RAG)

Phase 6 RAG retrieves curated meteorological definitions, hazard safety guidelines, and disaster response procedures:
- Provides context explaining terminology (e.g., what constitutes a "Depression" or "Squall").
- Supplies safety guidance checklists tailored for specific hazards.
- RAG knowledge **supports** generation; it **never replaces** live observations, forecasts, or official warnings.

---

### 10. Advisory & Decision Engine

Phase 7 converts verified weather intelligence into structured, role-specific action guidance:
- **Personas**: Tailored for `farmer`, `fisherman`, `commuter`, `student`, `traveller`, `disaster_response`, and `general`.
- **Structured Contracts**: Returns `priority` (`normal`, `caution`, `urgent`, `critical`), `action_summary`, and specific `precautions`.
- Generates structured guidance **before** LLM generation so the LLM communicates approved decisions rather than inventing recommendations.

---

### 11. Grounded Context

Before calling the language model, all verified data is assembled into an unalterable context bundle:
- User query and resolved conversational context.
- Observed temperature, humidity, wind, precipitation, and observation timestamps.
- Forecast periods and expected trends.
- Official active warnings and severity classifications.
- Identified hazards and structured advisory precautions.
- Supporting RAG knowledge chunks and source attributions.

---

### 12. Large Language Model (LLM) Integration

The LLM acts purely as an articulate communicator:
- Translates verified facts and advisories into fluent natural language.
- Bound strictly to the facts present in the grounded context.
- Fallback template generator is triggered automatically if the LLM fails, times out, or raises an exception.

---

### 13. Multilingual Generation

Generates accurate communications in English, Tamil, Hindi, Tanglish, and Hinglish:
- Preserves all numerical data, units (°C, mm, km/h), hazard classifications, and advisory steps.
- Uses culturally natural meteorological phrasing (e.g., *கனமழை*, *புயல் எச்சரிக்கை*, *भारी बारिश*, *अलर्ट*).
- Yields semantically identical decisions across all languages for equivalent meteorological conditions.

---

### 14. Response Validation & Safety Gate

Phase 9 `ResponseValidator` is the mandatory gate through which every generated response must pass:
- **Numerical Consistency Check**: Ensures temperatures, rain probabilities, and wind speeds mentioned in text do not hallucinate beyond grounded data.
- **Warning Preservation Check**: Guarantees that active official alerts are not omitted or downplayed.
- **Hazard Downgrade Prevention**: Blocks any attempt to claim conditions are safe during Red or Orange alert conditions.
- **Fallback Trigger**: Replaces invalid or hallucinated output with deterministic grounded fallback text.

---

### 15. Fallback Strategy

A multi-tiered deterministic fallback guarantees uninterrupted, safe operation:
1. **LLM Exception / Provider Outage**: Pipeline immediately invokes `_generate_fallback()` using structured rule templates.
2. **Validator Rejection (Hallucination / Omission)**: Pipeline discards LLM output and substitutes the deterministic grounded advisory.
3. **Missing Weather Data**: Pipeline returns a transparent "data currently unavailable" message without fabricating hypothetical values.
4. **STT Audio Failure**: Returns a clean transcript error and suggests text input.
5. **TTS Audio Failure**: Preserves and returns validated text response without system crash.

---

### 16. Unified AI Response Contract

Every invocation of `WeatherGPTPipeline.process_query` returns a standardized dictionary:

```json
{
  "answer": "Coimbatore-ல் தற்போதைய வெப்பநிலை 26°C, மழை வாய்ப்பு 75%...",
  "intent": "rain_forecast",
  "entities": {"location": "Coimbatore", "time": "tomorrow"},
  "location": "Coimbatore",
  "weather": {
    "temperature": 26.0,
    "humidity": 85.0,
    "rain_probability": 75.0,
    "wind_speed": 20.0,
    "weather_condition": "Moderate Rain",
    "source": "IMD"
  },
  "weather_summary": "Coimbatore: 26.0°C, Moderate Rain (source: IMD)",
  "forecast_count": 1,
  "warnings": ["Official Red Alert: Heavy Rain"],
  "alerts": [...],
  "hazards": ["heavy_rainfall"],
  "risk": {"level": "high", "score": 75.0},
  "advisory": {
    "priority": "high",
    "type": "farm_activity_caution",
    "action_summary": "கனமழை எதிர்பார்க்கப்படுவதால்...",
    "precautions": ["..."]
  },
  "sources": ["IMD"],
  "data_quality": {"freshness_score": 0.95, "source_agreement": 1.0},
  "validation": {"is_valid": true, "status": "approved"},
  "safety_telemetry": {
    "warning_present": true,
    "hazard_present": true,
    "advisory_priority": "high",
    "validation_status": "approved",
    "fallback_used": false
  },
  "fallback_used": false,
  "stage_latencies_ms": {
    "nlu_ms": 0.12,
    "reasoner_ms": 0.05,
    "advisory_ms": 0.03,
    "rag_ms": 0.15,
    "llm_ms": 0.09,
    "validator_ms": 0.18,
    "total_pipeline_ms": 0.65
  },
  "request_id": "req-12345"
}
```

---

### 17. Source Authority Hierarchy

In any case of conflict or divergence, authority is resolved by strict precedence:
1. **OFFICIAL LIVE WARNINGS** (IMD Red / Orange / Yellow Alerts) — Absolute Priority.
2. **FRESH VERIFIED WEATHER DATA** (Direct observations with verified timestamps).
3. **DETERMINISTIC WEATHER REASONER** (Calibrated physical thresholds & agreement).
4. **DETERMINISTIC HAZARD DETECTION** (IMD classification rules).
5. **STRUCTURED ADVISORY DECISIONS** (Approved persona precaution rules).
6. **RAG KNOWLEDGE** (Supporting background meteorological concepts).
7. **LLM LANGUAGE GENERATION** (Natural language phrasing only).
8. **CONVERSATION MEMORY** (Conversational entity resolution only; never current weather truth).

---

### 18. Text / Voice Consistency

Voice queries undergo STT transcription and enter the canonical pipeline.
- Both text and voice pipelines generate identical `intent`, `location`, `risk_level`, `hazards`, `advisory_priority`, and `precautions` when presented with equivalent queries.
- Differences are restricted exclusively to audio input/output processing.

---

### 19. Conversation Flow & Memory Safety

- When a user asks *"Is it safe to go out?"* followed by *"What about in Chennai?"*, the pipeline updates the active location to Chennai, invalidates prior localized weather data, and pulls fresh weather records.
- Memory stores prior dialogue states but does not cache weather observations across conversational sessions.

---

### 20. Severe Weather End-to-End Safety Flow

Under extreme conditions (e.g., Cyclone Red Alert with 95 km/h winds and 220mm rainfall):
- Reasoner flags `EXTREME` risk.
- Hazard detector identifies `CYCLONE`, `EXTREMELY_HEAVY_RAINFALL`, and `GALE_WIND`.
- Advisory engine produces immediate emergency life-safety instructions (e.g., *"Do not venture out; seek elevated concrete shelter"*).
- Grounded context enforces warning prominence.
- Validator rejects any response lacking alert disclosures.

---

### 21. Multi-Hazard Handling

When concurrent hazards occur simultaneously:
- All hazards are detected independently and aggregated without suppression.
- The highest hazard severity sets the overall risk level.
- Advisory rules merge precautions (e.g., marine safety for fisherman + flood safety for coastal commuter) without contradictions.

---

### 22. AI Pipeline Evaluation & Quality Benchmarks

The full-pipeline benchmark (`FullPipelineEvaluator`) executes an end-to-end evaluation covering 10 critical dimensions:

| Metric | Target | Measured Result | Status |
|---|---|---|---|
| Routing Accuracy | >= 90.0% | **90.0%** | PASS |
| Semantic Consistency | >= 90.0% | **100.0%** | PASS |
| Warning Preservation Rate | >= 95.0% | **100.0%** | PASS |
| Hazard Preservation Rate | >= 95.0% | **100.0%** | PASS |
| Advisory Preservation Rate | >= 90.0% | **100.0%** | PASS |
| Multilingual Consistency Rate | >= 90.0% | **100.0%** | PASS |
| Voice / Text Consistency Rate | >= 95.0% | **100.0%** | PASS |
| Validator Safety Rate | >= 95.0% | **100.0%** | PASS |
| Fallback Correctness Rate | >= 95.0% | **100.0%** | PASS |
| Memory Resolution Accuracy | >= 95.0% | **100.0%** | PASS |
| **Overall Pipeline Score** | **>= 90.0** | **99.0 / 100.0** | **EXCELLENT** |

---

### 23. Pipeline Latency & Performance

Deterministic execution stage latencies measured during end-to-end benchmark runs (local CPU, non-network provider mock):

| Pipeline Stage | Average Latency |
|---|---|
| NLU Query Understanding | ~0.15 ms |
| Weather Reasoner & Agreement | ~0.06 ms |
| Advisory & Decision Engine | ~0.04 ms |
| RAG Retrieval & Knowledge Filter | ~0.49 ms |
| LLM Generation (Deterministic Fallback / Mock) | ~0.12 ms |
| Response Validator & Guard | ~0.27 ms |
| **Total Pipeline Processing** | **~1.12 ms** |

*Note: Real cloud LLM providers (e.g., Gemini Flash / OpenAI) will introduce network latency (typically 300ms - 1200ms), which is completely decoupled from our sub-2ms deterministic reasoning and safety pipeline.*

---

### 24. End-to-End Test Suite

`tests/test_ai_full_pipeline.py` contains 39 tests covering all 36 required scenarios and verification criteria:
- Normal Weather (1-2), Forecast & Temporal Variations (3-5)
- Conversational Memory Follow-Up (6, 33)
- Multilingual Support (7-11: English, Tamil, Hindi, Tanglish, Hinglish)
- Persona Specialization (12-17: Farmer, Fisherman, Commuter, Student, Traveller, Disaster Response)
- Severe Weather & Hazards (18-24: Official Warnings, Cyclone, Heavy Rain, Severe Wind, Thunderstorm, Heatwave, Multi-Hazard)
- Data Quality & Edge Cases (25-27: Source Disagreement, Stale Data, Missing Data)
- Reliability & Safety (28-30: LLM Failure, Validator Rejection, Deterministic Fallback)
- Multimodal & Voice (31-32: Voice Query, Multilingual Voice)
- Conversational Dynamics (34-35: Language Switch, Location Switch)
- Full Backend Integration Flow (36: Backend AIService & ChatIntegrationService)
- Cross-Layer Invariant Checks (Temperature, Rain Probability, Location, Warning, Severity)
- Latency Profiling and Evaluator Benchmark Suite

---

### 25. Known Limitations

- **Dialect Variations**: Deep slang in mixed Tanglish/Hinglish may require expanded vocabulary lists.
- **External Network Latency**: Cloud LLM network latency varies with internet connectivity, though deterministic local fallback ensures sub-second safety under network interruption.

---

### 26. Person 2 Integration Boundary

- **FastAPI Endpoints**: Person 2's routes (`/chat/completions`, `/api/v1/chat`, `/api/v1/voice/query`) connect via `AIService` and `ChatIntegrationService` to `WeatherGPTPipeline.process_query`.
- **Database & Weather Ingestion**: Person 2 provides live `WeatherRecord` and `OfficialAlert` records. Core AI receives normalized domain objects and produces the unified AI response contract.

---

### 27. Next Phase

**Phase 16 — End-to-End System Testing & Acceptance**.
