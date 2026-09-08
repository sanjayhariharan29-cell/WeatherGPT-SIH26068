# WeatherGPT — Phase 5: LLM Integration & Grounded Response Layer
**SIH Problem Statement:** SIH26068 (Ministry of Earth Sciences / IMD, Theme: Disaster Management)  
**Developer:** Person 1 (AI / Weather Intelligence Developer)  
**Status:** Complete  
**Date:** 2026-09-08  

---

## 1. Overview & Architecture

Phase 5 establishes the **LLM Integration & Grounded Response Layer** (`ai/llm/`). 

In WeatherGPT, the Large Language Model is **never** the meteorological source of truth. It does not forecast the weather, invent missing numbers, or determine disaster warning levels. Instead, it operates strictly as an articulate natural-language generator bounded by verified intelligence assembled by the **Grounded Context Builder**.

```mermaid
graph TD
    Query[User Query] --> NLU[Phase 2 NLU]
    WeatherData[Normalized Weather Telemetry] --> Reasoner[Phase 3 Weather Reasoner]
    Reasoner --> Hazards[Phase 4 Hazard Detection]
    Hazards --> Alerts[Authoritative IMD Warnings]
    
    NLU & WeatherData & Reasoner & Hazards & Alerts --> GCB[Grounded Context Builder: ai/llm/context_builder.py]
    GCB --> Prompt[Structured Grounded Prompt & Fact Payload]
    Prompt --> LLM[LLM Provider: Gemini / Mock]
    LLM --> Guard[Grounding Safety Guard: ai/llm/grounding_guard.py]
    
    Guard -- Passed Grounding Check --> Answer[Grounded Natural Language Response]
    Guard -- Hallucination / Contradiction Detected --> Fallback[Deterministic Grounded Template Fallback]
    LLM -- Timeout / Exception / Failure --> Fallback
```

---

## 2. Provider Abstraction & Configuration

### Provider Neutrality (`ai/llm/provider.py`)
- `BaseLLMProvider`: Abstract interface defining `generate_text(system_prompt: str, user_prompt: str) -> Optional[str]`.
- `GeminiLLMProvider`: Production provider utilizing Google Generative AI (`gemini-1.5-flash`).
- `MockLLMProvider`: Deterministic mock provider supporting automated testing, timeout simulation (`simulate_timeout=True`), provider failure simulation (`should_fail=True`), and hallucination injection.

### Configuration (`ai/config/settings.py` & `.env.example`)
Configurable via environment variables without hardcoded credentials:
- `WEATHERGPT_LLM_PROVIDER`: `"gemini"` / `"mock"`
- `WEATHERGPT_LLM_MODEL`: `"gemini-1.5-flash"`
- `WEATHERGPT_LLM_TIMEOUT`: `10.0` seconds
- `WEATHERGPT_LLM_TEMPERATURE`: `0.2` (low variance for maximum factual grounding)

---

## 3. Grounded Context Builder (`ai/llm/context_builder.py`)

The Grounded Context Builder synthesizes domain intelligence into a deterministic, strictly segregated fact payload (`GroundedContext`):
1. **Observed Facts:** Location, coordinates, timestamps (`observed_at`, `retrieved_at`), source attribution (`IMD`), and validated metrics (`temperature_c`, `rain_probability_pct`, `rainfall_amount_mm`, `wind_speed_kmh`, `weather_condition`).
2. **Short-Term Forecast Facts:** Hourly/period forecasts with explicit target timestamps (`forecast_target_time`).
3. **Official IMD Warnings:** Active alerts (`OfficialAlert`) with urgency, severity, validity window, and affected districts.
4. **AI-Detected Hazards:** Phase 4 evaluated hazards with machine-readable evidence (`evidence: List[str]`) and temporal scope (`"current"`, `"forecast"`, `"both"`).
5. **Data Quality & Consistency:** Freshness status, elapsed age, completeness flags, source agreement, and the **Forecast Consistency Score** ($0\text{–}100$).
6. **User Request & Intent:** Untrusted user message, intent, detected language/script, and target persona.

---

## 4. Grounding Rules & Prompt Injection Defense

### System Instruction Constraints (`ai/llm/prompts.py`)
1. **Sole Source of Truth:** The LLM must draw exclusively from supplied facts.
2. **Official Warning Supremacy:** Official IMD warnings have absolute priority. The LLM must prominently state them and can never cancel, downplay, or contradict an active alert, even if local skies appear sunny.
3. **Prompt Injection Defense:** The user input is explicitly marked as untrusted. Requests to "ignore warnings", "say it's safe", or "override IMD alerts" are rejected, and safety constraints are strictly maintained.
4. **Missing Data Honesty:** Any missing metric is explicitly tagged as `"UNAVAILABLE"`. The LLM states that data is unavailable and never coerces missing values to $0$, "safe", or "clear".
5. **Consistency Score Semantics:** The score is explained as an application-level data quality metric, never as a scientific probability of rainfall.

---

## 5. Basic Grounding Safety Guard & Fallback Execution

`ai/llm/grounding_guard.py` performs deterministic fast-path response inspection before returning text to users:
- **Contradiction Guard:** Detects phrases like "weather is safe", "no danger", or "no warning" when an official high/extreme IMD alert is active.
- **Invented Warning Guard:** Flags claims of "Official Red Alert" or "IMD warning issued" when no official alert exists in ground truth.
- **Unsupported Number Guard:** Scans response metrics (e.g. `55°C`, `190 km/h`) against verified numbers in the context.

### Controlled Fallback (`GroundedLLMGenerator._generate_fallback`)
If an LLM times out, throws a connection exception, returns an empty string, or fails the grounding guard, the generator immediately switches to the deterministic grounded template fallback. The fallback:
- Highlights active IMD emergency alerts first.
- Accurately quotes verified observations or explicitly discloses missing variables.
- Embeds actionable persona precautions.
- Cites data sources, observation freshness, and consistency scores.
- Renders natively in English or Tamil/Tanglish.

---

## 6. Output Contract (`GroundedResponse`)

```json
{
  "answer": "In Nagapattinam, current temperature is 29°C with a 75% chance of rain. Carry an umbrella.",
  "grounded_facts": [
    "temperature_c: 29.0",
    "rain_probability_pct: 75.0",
    "wind_speed_kmh: 22.0"
  ],
  "warnings": [],
  "uncertainties": [],
  "sources": ["IMD"],
  "used_grounded_context": true,
  "is_fallback": false
}
```

---

## 7. Test Verification & Regression Results

All 100 tests pass across the repository:
```powershell
python -m pytest -v
======================= 100 passed, 1 warning in 5.61s =======================
```
Covering:
- **19 new Phase 5 LLM depth tests** in [`tests/test_ai_llm_depth.py`](file:///c:/Users/sanja/OneDrive/Desktop/WeatherGPT-SIH26068/tests/test_ai_llm_depth.py):
  1. `test_normal_grounded_response`
  2. `test_missing_temperature_handling`
  3. `test_missing_forecast_handling`
  4. `test_official_warning_prominence`
  5. `test_warning_plus_calm_observation_priority`
  6. `test_conflicting_sources_uncertainty`
  7. `test_stale_data_handling`
  8. `test_current_vs_future_forecast_scoping`
  9. `test_source_attribution_preserved`
  10. `test_unsupported_number_hallucination_triggers_fallback`
  11. `test_invented_warning_triggers_fallback`
  12. `test_prompt_injection_resistance`
  13. `test_provider_timeout_triggers_fallback`
  14. `test_provider_failure_triggers_fallback`
  15. `test_malformed_response_triggers_fallback`
  16. `test_deterministic_fallback_execution`
  17. `test_consistency_score_semantics`
  18. `test_empty_weather_data_safety`
  19. `test_full_ai_pipeline_integration`
- **19 Phase 4 Hazard calibration tests** in `tests/test_ai_hazard_depth.py`
- **10 Phase 3 Reasoner depth tests** in `tests/test_ai_reasoner_depth.py`
- **13 Phase 1 & 2 NLU depth tests** in `tests/test_ai_nlu_depth.py`
- **16 Core AI pipeline tests** in `tests/test_ai_core.py` and `tests/test_ai_foundation.py`
- **23 Backend FastAPI and database tests** from Person 2

---

## 8. Excluded Functionality (Phase Boundaries)

- **Phase 6 (RAG / Knowledge Grounding):** Vector database, embeddings, and external document retrieval are intentionally excluded.
- **Phase 7 (Advisory Engine):** Persona recommendation calibration stays in `ai/decision/`.
- **Phase 8 (Mature Multilingual AI):** Advanced Hindi transliteration expansion is preserved for Phase 8.
- **Phase 9 (Master Validator):** Complete cross-validation matrix belongs to Phase 9; Phase 5 implements only the essential fast-path Grounding Guard.

---

## 9. Next Recommended Phase

**Phase 6 — RAG / Meteorological Knowledge Grounding:** Ingestion and retrieval of IMD meteorological standard operating procedures (SOPs), disaster safety manuals, and cyclone protocol knowledge.
