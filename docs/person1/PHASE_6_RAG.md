# WeatherGPT — Phase 6: RAG / Meteorological Knowledge Grounding
**SIH Problem Statement:** SIH26068 (Ministry of Earth Sciences / IMD, Theme: Disaster Management)  
**Developer:** Person 1 (AI / Weather Intelligence Developer)  
**Status:** Complete  
**Date:** 2026-09-08  

---

## 1. Purpose & Objectives

Phase 6 establishes the **Meteorological Knowledge Retrieval-Augmented Generation (RAG)** layer (`ai/rag/`) for WeatherGPT.

The primary objective is to supply **stable, authoritative meteorological background knowledge and disaster safety protocols** to ground the conversational AI without ever compromising live weather telemetry or overriding official weather alerts.

### What RAG Is For:
- Explaining meteorological terminology (e.g., *Depression*, *Deep Depression*, *Very Severe Cyclonic Storm*).
- Explaining hazard definitions and criteria (e.g., IMD rainfall thresholds from *Very Heavy* to *Extremely Heavy*).
- Explaining color-coded warning stages (e.g., *Green*, *Yellow*, *Orange*, *Red* alert definitions).
- Providing standard operating safety procedures (e.g., NDMA cyclone, flood, and lightning safety SOPs like the *30-30 Rule*).
- Explaining project-defined evaluation criteria and meteorological concepts.

### What RAG Is NOT For:
- **RAG is NOT the source of live weather values.**
- **RAG must NEVER be queried to answer:** *"What is the temperature right now in Chennai?"* or *"Will it rain in Madurai this afternoon?"*
- Live conditions, hourly/daily forecasts, and active warnings are retrieved strictly from the **Weather Data Layer**, **Weather Reasoner**, and **Official Warning Sources (IMD)**.

---

## 2. Knowledge Boundary & Hierarchy of Truth

To prevent hallucination, stale reporting, and safety compromises, WeatherGPT enforces a strict **Hierarchy of Truth**:

$$\textbf{OFFICIAL LIVE WARNING} > \textbf{LIVE WEATHER DATA} > \textbf{DETERMINISTIC HAZARD LOGIC} > \textbf{STATIC RAG KNOWLEDGE}$$

1. **Official Live IMD Warnings:** Highest authority. If IMD issues a Red Alert for cyclone landfall, static documents cannot soften or dismiss it.
2. **Live Telemetry & Forecasts:** Real-time sensor and numerical weather observations.
3. **Deterministic Hazard Logic:** Phase 4 calibrated safety thresholds applied to active telemetry.
4. **Static RAG Knowledge:** Educational, terminological, and advisory background information. A static document stating *"Conditions in coastal areas are generally pleasant in October"* can never override active cyclone telemetry.

---

## 3. Authoritative Source Policy & Whitelist

To eliminate unverified web scraping and unreliable crowd-sourced guidance, WeatherGPT accepts only verified, authoritative knowledge sources.

### Whitelisted Sources (`SOURCE_WHITELIST` in `ai/rag/retriever.py`):
- `IMD`: India Meteorological Department (Ministry of Earth Sciences, Govt. of India).
- `NDMA`: National Disaster Management Authority (Govt. of India).
- `TNSDMA`: Tamil Nadu State Disaster Management Authority.
- `MoES`: Ministry of Earth Sciences.
- `PROJECT`: Internal project methodologies and developer documentation.

### Curated Knowledge Base (`ai/rag/corpus.py`):
- **IMD Rainfall Classification:** Deterministic millimetre thresholds ($<2.5\text{ mm}$ to $>204.4\text{ mm}$).
- **IMD Color-Coded Warning System:** Green (No Warning), Yellow (Be Updated), Orange (Be Prepared), Red (Take Action).
- **IMD Cyclone Classification & 4-Stage Warning:** Pre-Cyclone Watch, Cyclone Alert (48h), Cyclone Warning (24h), Landfall Outlook (12h).
- **IMD Heatwave & Coldwave Criteria:** Departure from normal and absolute temperature thresholds ($+4.5^\circ\text{C}$, $40^\circ\text{C}/45^\circ\text{C}$).
- **NDMA Cyclone Safety Guidelines:** Pre-cyclone preparation, during-cyclone lockdown, post-cyclone electrical safety.
- **NDMA Flood Safety & Precautions:** Avoiding moving water, safe drinking water, electrical isolation.
- **NDMA Lightning Safety & 30-30 Rule:** Flash-to-bang timing, indoor shelter protocols.
- **Multilingual Support (Tamil / தமிழ்):** IMD எச்சரிக்கை வண்ண குறியீடுகள் (Color codes) and NDMA புயல் பாதுகாப்பு வழிகாட்டுதல்கள் (Cyclone safety).

---

## 4. Document & Chunk Architecture

### Schema (`ai/rag/schema.py`)
- `KnowledgeDocument`: Represents an authoritative source file with strict metadata:
  - `doc_id`: Unique identifier (e.g., `imd_rainfall_classification_2024`).
  - `title`: Human-readable document title.
  - `source`: Authority acronym (e.g., `IMD`, `NDMA`).
  - `source_type`: Category (`official_meteorological`, `government_safety`, `project_methodology`).
  - `topic`: Domain taxonomy (`rainfall`, `cyclone`, `heatwave`, `flood`, `safety_general`).
  - `language`: BCP-47 / ISO code (`en`, `ta`, `hi`).
  - `version`: Version or edition string (e.g., `2024.1`).
  - `authority_level`: Confidence tier (`authoritative`, `advisory`, `internal`).
  - `updated_at`: ISO timestamp of publication/revision.
  - `content`: Raw markdown content.
- `KnowledgeChunk`: Discrete atomic unit of knowledge:
  - `chunk_id`, `doc_id`, `heading`, `text`, `metadata`, `keywords`.
- `RetrievedChunk`: Retrieved output package:
  - `chunk`: Underlying `KnowledgeChunk`.
  - `relevance_score`: Float between $0.0$ and $1.0$.
  - `is_authoritative`: Boolean indicating official agency backing.

### Chunking Engine (`ai/rag/chunker.py`)
- Header-aware markdown splitting (`#`, `##`, `###`).
- Preserves full section context and retains document-level metadata into chunk metadata.
- Applies clean line folding and removes excessive whitespace.

---

## 5. Retrieval Engine & Relevance Semantics

### Provider-Neutral Architecture (`ai/rag/retriever.py`)
The `KnowledgeRetriever` provides an in-memory, zero-external-dependency retrieval engine designed for deterministic, reproducible execution:
- **Tokenization & Stopword Elimination:** Removes common fillers while preserving meteorological numbers and technical acronyms.
- **Lexical BM25 / TF-IDF Scoring:** Computes query-to-chunk term overlap, normalized across chunk length.
- **Heading & Topic Boosting:** Matches in chunk headings and topic tags receive significant relevance multipliers ($1.8\times$ to $2.0\times$).
- **Authority Prioritization:** Authoritative sources (`IMD`, `NDMA`) receive an authority boost ($1.15\times$).

### Strict Relevance Semantics
> [!IMPORTANT]
> The `relevance_score` returned by the retriever represents **lexical and semantic retrieval relevance** ($0.0\text{--}1.0$).
> It does **NOT** indicate:
> - Factual truth probability
> - Meteorological forecast certainty
> - Rain probability or confidence in current weather observations.

### Guardrails & Safety Thresholds
1. **Source Whitelist Verification:** Rejects documents from unverified sources.
2. **Low-Relevance Suppression:** Queries with relevance scores below `min_relevance_threshold` (default `0.10`) return an empty result list (`NO_RELEVANT_KNOWLEDGE`).
3. **Deduplication:** Near-identical content chunks are filtered out before ranking.
4. **Top-K Limiting:** Caps retrieved contexts to top $k$ relevant chunks (default $3$).
5. **Metadata Filtering:** Supports explicit filtering by `topic`, `language`, and `min_authority`.

---

## 6. Live Weather + RAG Separation

When presenting context to the Large Language Model in `ai/llm/context_builder.py`, live weather telemetry and static RAG knowledge are strictly partitioned into distinct sections:

```
================================================================================
WEATHERGPT GROUNDED METEOROLOGICAL CONTEXT
================================================================================
...
--- 1. ACTIVE OFFICIAL WEATHER WARNINGS (HIGHEST PRIORITY) ---
WARNING: Red Alert (Cyclone Warning) issued by IMD.

--- 2. VERIFIED REAL-TIME OBSERVATIONS (LIVE WEATHER TELEMETRY) ---
Location: Chennai
Temperature: 31.0°C | Rainfall: 68.0 mm
...
--- 7. STATIC METEOROLOGICAL REFERENCE KNOWLEDGE (RAG STATIC CORPUS) ---
[REFERENCE ONLY: The following static background knowledge explains meteorological
terminology, alert color codes, and safety protocols. It is NOT live weather data
and must NEVER be cited as current observations.]

[REF 1] Heavy to Very Heavy Rainfall (Source: IMD | Version: 2024.1)
Heavy Rain: 64.5 to 115.5 mm in 24 hours. Very Heavy Rain: 115.6 to 204.4 mm.
```

In the LLM system prompt (`ai/llm/prompts.py`), rule #9 explicitly directs:
> *"Treat static reference knowledge as conceptual/educational background. Never present static documentation numbers as live observations."*

Furthermore, the fast-path **Grounding Safety Guard** (`ai/llm/grounding_guard.py`) whitelists numeric metrics mentioned in reference knowledge (such as threshold numbers $64.5\text{ mm}$ or $115.5\text{ mm}$) so valid meteorological citations do not trigger spurious hallucination fallbacks.

---

## 7. Multilingual Readiness

The schema and corpus are built with first-class multilingual metadata:
- Knowledge documents declare their language (`en`, `ta`, `hi`).
- Retrieval supports filtering by language or defaulting to English when queries are in English or transliterated Tanglish.
- Initial Tamil corpus covers color codes and cyclone safety, establishing seamless readiness for Phase 8 multilingual generation.

---

## 8. Test Verification & Coverage

14 dedicated automated tests in `tests/test_ai_rag_depth.py` validate all Phase 6 operational requirements without requiring external network calls:

| Test Name | Validated Capability | Result |
| :--- | :--- | :--- |
| `test_document_ingestion_and_metadata` | Ingestion, metadata preservation, authority level | **PASSED** |
| `test_document_chunking` | Header-aware chunking, parent metadata inheritance | **PASSED** |
| `test_relevant_retrieval` | Keyword and semantic query matching (rainfall thresholds) | **PASSED** |
| `test_irrelevant_query_suppression` | Suppression of unrelated queries (cricket, stocks) | **PASSED** |
| `test_top_k_parameter` | Strict enforcement of retrieval count limit ($k=2$) | **PASSED** |
| `test_topic_and_language_filters` | Topic (`cyclone`) and language (`ta`) filtering | **PASSED** |
| `test_source_attribution` | Source attribution (`IMD`, `NDMA`) preservation | **PASSED** |
| `test_duplicate_filtering` | Identical chunk deduplication | **PASSED** |
| `test_empty_knowledge_base` | Graceful zero-chunk fallback (`NO_RELEVANT_KNOWLEDGE`) | **PASSED** |
| `test_live_weather_plus_rag_separation` | Strict section partitioning in `GroundedContext` | **PASSED** |
| `test_official_warning_priority_over_rag` | Official alert precedence over static calm guidelines | **PASSED** |
| `test_historical_document_versioning` | Timestamp, version, and date retention | **PASSED** |
| `test_retriever_scoring_semantics` | Score semantics verification (relevance $\neq$ probability) | **PASSED** |
| `test_full_llm_plus_rag_integration` | End-to-end LLM generation grounded with live + RAG | **PASSED** |

**Full Regression Test Suite:** **120 / 120 tests passing** across the repository.

---

## 9. Boundaries & Exclusions

- **Person 2 Integration Boundary:** Person 2 owns database persistence of user conversations, external weather API polling, and GIS map layers. Person 1 provides the in-memory RAG retriever and grounded context generation layer.
- **Phase 7 Functionality Excluded:** No persona-specific decision engines, agricultural crop calendars, or fisherman voyage recommendations were implemented. Phase 7 will be built strictly in the next phase.
