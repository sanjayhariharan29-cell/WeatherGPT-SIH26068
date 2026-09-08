# WeatherGPT — Phase 1: AI Foundation Architecture
**SIH Problem Statement:** SIH26068 (Ministry of Earth Sciences / IMD, Theme: Disaster Management)  
**Developer:** Person 1 (AI / Weather Intelligence Developer)  
**Status:** Complete  
**Date:** 2026-09-08  

---

## 1. Overview & Objective

Phase 1 formalizes, modularizes, and stabilizes the WeatherGPT AI intelligence layer (`ai/`). Rather than rebuilding working components from scratch, Phase 1 established:
1. Centralized, typed configuration (`ai/config/settings.py`).
2. Pluggable LLM provider abstraction (`BaseLLMProvider`, `GeminiLLMProvider`, `MockLLMProvider`).
3. Safe environment variable management (`.env.example`).
4. Stable typed models (`ai/models.py`).
5. Verified safety boundaries (no hallucinations, official warning priority).
6. Clean integration boundary documentation for Person 2 (FastAPI backend).

---

## 2. Directory & Module Architecture

```text
ai/
├── __init__.py                # Clean unified exports for the AI layer
├── config/                    # Phase 1: Configuration management
│   ├── __init__.py
│   └── settings.py            # AIConfig, LLMConfig, MeteorologicalThresholds
├── models.py                  # Pydantic v2 schemas (WeatherRecord, Alerts, Advisories, etc.)
├── nlu/                       # Multilingual NLU
│   ├── __init__.py            # parse_query()
│   ├── language.py            # Script & phonetic Tanglish language detection
│   ├── intent.py              # Canonical intent classification
│   └── entities.py            # Location, date, time, persona, and variable extraction
├── reasoner/                  # Core Meteorological Reasoner
│   ├── __init__.py
│   ├── freshness.py           # Observation age & staleness validation
│   ├── hazard.py              # IMD hazard detection (rain, wind, cyclone, heat)
│   ├── agreement.py           # Multi-source agreement & Forecast Consistency Score
│   └── reasoner.py            # WeatherReasoner.evaluate() orchestration
├── decision/                  # Persona Decision Engine
│   ├── __init__.py
│   └── decision_engine.py     # Actionable advisories (Student, Farmer, Fisherman, General)
├── rag/                       # Domain Knowledge Grounding
│   ├── __init__.py
│   └── knowledge_base.py      # Official IMD/NDMA disaster & weather safety protocols
├── llm/                       # LLM Grounded Generation Layer
│   ├── __init__.py
│   ├── provider.py            # Phase 1: Provider abstraction (Base, Gemini, Mock)
│   ├── prompts.py             # Grounded prompt builder enforcing rules
│   └── generator.py           # GroundedLLMGenerator with deterministic fallback
├── validator/                 # Anti-Hallucination Response Validator
│   ├── __init__.py
│   └── response_validator.py  # Fact verification & warning integrity check
└── pipeline.py                # WeatherGPTPipeline end-to-end orchestrator
```

---

## 3. Configuration Management (`ai/config/`)

All AI settings are centralized in `ai/config/settings.py` and read from standard environment variables with sensible defaults:

* `WEATHERGPT_LLM_PROVIDER`: `gemini` (default), `mock`, or `custom`.
* `WEATHERGPT_LLM_MODEL`: `gemini-1.5-flash` (default).
* `GEMINI_API_KEY` / `GOOGLE_API_KEY`: API key for generative services (never hard-coded).
* `MeteorologicalThresholds`:
  * Freshness: Fresh < 60m, Acceptable 60–180m, Stale > 180m.
  * Precipitation: Heavy rain $\ge 80\%$ or $\ge 64.5\text{ mm}$, Moderate $\ge 60\%$.
  * Wind: Gale/Cyclonic $\ge 62\text{ km/h}$, Strong $\ge 40\text{ km/h}$.
  * Temperature: Heatwave $\ge 40^\circ\text{C}$.

---

## 4. Provider Abstraction (`ai/llm/provider.py`)

To prevent tight coupling to a single commercial SDK, an abstract interface was introduced:
* `BaseLLMProvider`: ABC with `generate_text(system_prompt, user_prompt) -> Optional[str]`.
* `GeminiLLMProvider`: Encapsulates Google Gemini calls with error handling.
* `MockLLMProvider`: Encapsulates deterministic responses for offline testing and demos.
* `GroundedLLMGenerator`: Delegates text generation to the active provider. If the provider is unavailable or fails, it automatically engages the deterministic grounded generator to guarantee 100% service uptime.

---

## 5. Person 2 Integration Boundary

Person 1 produces the intelligence layer. Person 2 produces the FastAPI backend and frontend.

### Conceptual Contract for Person 2:
Person 2 imports `WeatherGPTPipeline` directly from `ai`:

```python
from ai import WeatherGPTPipeline, WeatherRecord, ForecastItem, OfficialAlert, PersonaEnum

pipeline = WeatherGPTPipeline()

# Inside FastAPI route POST /api/v1/chat:
result = pipeline.process_query(
    message=user_message,
    weather=primary_weather_record,      # Produced by Person 2's IMDAdapter
    forecast=forecast_items,             # Produced by Person 2's IMDAdapter
    active_alerts=active_alerts,         # Produced by Person 2's IMDAdapter
    secondary_weather=secondary_record,  # Optional: Open-Meteo
    persona=user_persona,                # Optional: from user profile / query
    conversation_id=conversation_id
)
```

### Response Payload Received by Person 2:
```json
{
  "conversation_id": "abc123",
  "answer": "நாளை காலை மழைக்கான வாய்ப்பு அதிகமாக உள்ளது...",
  "language": "ta",
  "intent": "rain_forecast",
  "location": "Coimbatore",
  "persona": "student",
  "risk": {
    "level": "medium",
    "consistency": "high",
    "consistency_score": 85
  },
  "source": "IMD",
  "data_timestamp": "2026-09-08T10:00:00+00:00",
  "validation": {
    "passed": true,
    "issues": []
  }
}
```

---

## 6. Safety & Anti-Hallucination Grounding Rules

1. **LLM Is Not Meteorological Truth:** The LLM only personalizes and explains verified data.
2. **Authoritative Warning Priority:** Active IMD alerts can never be contradicted or omitted.
3. **Traceability:** Sources (`IMD`) and update age are explicitly included in generated advisories.
4. **Institutional Boundaries:** WeatherGPT never declares school or college closures; it advises checking official administrative notices.
5. **Data Quality Representation:** The consistency metric is labelled as `Forecast Consistency Score`, not a scientific probability.

---

## 7. Test Verification & Results

Command run:
```powershell
python -m pytest -v
```
Results:
* **Total Tests:** 22 (17 baseline + 5 new Phase 1 foundation tests)
* **Passed:** 22 (100%)
* **Execution Time:** ~0.16s
