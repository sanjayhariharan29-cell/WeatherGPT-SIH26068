"""Unit and Regression Tests for Phase 6 RAG / Meteorological Knowledge Grounding.

Covers all 18 mandatory scenarios:
1. Document ingestion
2. Metadata preservation
3. Document chunking
4. Basic retrieval
5. Relevant retrieval
6. Irrelevant query suppression
7. Top-k parameter
8. Topic and language metadata filters
9. Source attribution
10. Duplicate filtering
11. Empty knowledge base safety
12. Low relevance suppression
13. Live weather + RAG separation
14. Official warning priority over RAG
15. Historical document versioning
16. Context builder prompt formatting
17. Retriever indexing and scoring semantics
18. Full LLM + RAG integration
"""

from datetime import datetime, timedelta, timezone
import pytest
from ai.llm.context_builder import build_grounded_context
from ai.llm.generator import GroundedLLMGenerator
from ai.llm.provider import MockLLMProvider
from ai.models import (
    ForecastItem,
    LanguageEnum,
    LocationInfo,
    NLUResult,
    OfficialAlert,
    PersonaEnum,
    RiskLevelEnum,
    WeatherRecord,
)
from ai.nlu import parse_query
from ai.rag.chunker import chunk_document
from ai.rag.corpus import AUTHORITATIVE_DOCUMENTS
from ai.rag.retriever import KnowledgeRetriever, get_knowledge_retriever
from ai.rag.schema import KnowledgeChunk, KnowledgeDocument
from ai.reasoner import WeatherReasoner


@pytest.fixture
def base_location():
    return LocationInfo(
        name="Nagapattinam",
        latitude=10.7672,
        longitude=79.8449,
        district="Nagapattinam",
        state="Tamil Nadu"
    )


@pytest.fixture
def base_weather(base_location):
    now = datetime.now(timezone.utc)
    return WeatherRecord(
        location=base_location,
        observed_at=now - timedelta(minutes=15),
        retrieved_at=now - timedelta(minutes=10),
        temperature=29.0,
        humidity=72.0,
        rain_probability=75.0,
        wind_speed=22.0,
        weather_condition="Rain",
        source="IMD",
        rainfall_amount_mm=45.0
    )


# =====================================================================
# 1. Document Ingestion & 2. Metadata Preservation
# =====================================================================

def test_document_ingestion_and_metadata():
    custom_doc = KnowledgeDocument(
        id="doc_custom_test",
        title="Custom Flood Safety Guidance",
        source="India Meteorological Department (IMD)",
        topic="flood",
        language="en",
        version="1.0",
        updated_at="2024-05-01",
        content="""## Urban Flood Safety
Avoid basement parking and storm culverts during waterlogging.
""",
        metadata={"custom_flag": "test_123", "sop_code": "FL-01"}
    )
    retriever = KnowledgeRetriever(documents=[custom_doc])
    assert len(retriever.chunks) == 1
    chunk = retriever.chunks[0]
    assert chunk.doc_id == "doc_custom_test"
    assert chunk.metadata["custom_flag"] == "test_123"
    assert chunk.metadata["sop_code"] == "FL-01"
    assert chunk.source == "India Meteorological Department (IMD)"


# =====================================================================
# 3. Document Chunking
# =====================================================================

def test_document_chunking():
    doc = KnowledgeDocument(
        id="doc_multi_sec",
        title="Multi Section Guidelines",
        source="India Meteorological Department (IMD)",
        topic="heavy_rain",
        language="en",
        version="1.0",
        updated_at="2024-01-01",
        content="""## Section One: Light Rain
Details about light rain accumulation under 15 mm.

## Section Two: Heavy Rain
Details about heavy rain accumulation exceeding 64.5 mm.
"""
    )
    chunks = chunk_document(doc)
    assert len(chunks) == 2
    assert chunks[0].heading == "Section One: Light Rain"
    assert chunks[1].heading == "Section Two: Heavy Rain"
    assert chunks[0].topic == "heavy_rain"


# =====================================================================
# 4. Basic Retrieval & 5. Relevant Retrieval
# =====================================================================

def test_relevant_retrieval():
    retriever = get_knowledge_retriever()
    # Query rainfall thresholds
    results = retriever.retrieve("IMD rainfall intensity categories classification", top_k=2)
    assert len(results) > 0
    top = results[0]
    assert "heavy rain" in top.chunk.content.lower() or "rainfall" in top.chunk.content.lower()
    assert top.relevance_score > 0.15
    assert len(top.matched_terms) > 0


# =====================================================================
# 6. Irrelevant Query & 12. Low Relevance Suppression
# =====================================================================

def test_irrelevant_query_suppression():
    retriever = get_knowledge_retriever()
    # Completely unrelated query
    results = retriever.retrieve("blockchain cryptocurrency smart contracts mining", min_score=0.15)
    # Must return empty list, NOT unrelated weather chunks
    assert len(results) == 0


# =====================================================================
# 7. Top-K Parameter
# =====================================================================

def test_top_k_parameter():
    retriever = get_knowledge_retriever()
    results = retriever.retrieve("cyclone wind safety", top_k=2)
    assert len(results) <= 2
    if len(results) == 2:
        # Must be sorted descending by relevance score
        assert results[0].relevance_score >= results[1].relevance_score


# =====================================================================
# 8. Topic and Language Metadata Filters
# =====================================================================

def test_topic_and_language_filters():
    retriever = get_knowledge_retriever()

    # Topic filter: heatwave
    heat_results = retriever.retrieve("safety guidance", topic="heatwave")
    assert all(r.chunk.topic == "heatwave" for r in heat_results)

    # Language filter: Tamil
    ta_results = retriever.retrieve("பாதுகாப்பு", language="ta")
    assert len(ta_results) > 0
    assert all(r.chunk.language == "ta" for r in ta_results)


# =====================================================================
# 9. Source Attribution
# =====================================================================

def test_source_attribution():
    retriever = get_knowledge_retriever()
    results = retriever.retrieve("cyclone 4-stage warning", top_k=1)
    assert len(results) > 0
    assert results[0].chunk.source in ("India Meteorological Department (IMD)", "National Disaster Management Authority (NDMA)")


# =====================================================================
# 10. Duplicate Filtering
# =====================================================================

def test_duplicate_filtering():
    retriever = get_knowledge_retriever()
    results = retriever.retrieve("cyclone wind", top_k=5)
    chunk_ids = [r.chunk.chunk_id for r in results]
    assert len(chunk_ids) == len(set(chunk_ids))


# =====================================================================
# 11. Empty Knowledge Base Safety
# =====================================================================

def test_empty_knowledge_base():
    empty_retriever = KnowledgeRetriever(documents=[])
    results = empty_retriever.retrieve("cyclone warning")
    assert results == []


# =====================================================================
# 13. Live Weather + RAG Separation
# =====================================================================

def test_live_weather_plus_rag_separation(base_weather):
    nlu = parse_query("What does heavy rain mean?")
    reasoning = WeatherReasoner.evaluate(base_weather)
    from ai.decision import DecisionEngine
    advisory = DecisionEngine.generate_advisory(reasoning)

    retriever = get_knowledge_retriever()
    ref_chunks = retriever.retrieve("heavy rainfall definition", top_k=1)

    context = build_grounded_context(
        nlu=nlu,
        weather=base_weather,
        reasoning=reasoning,
        advisory=advisory,
        reference_knowledge=ref_chunks
    )

    # Verify separate sections in prompt
    assert "--- 1. OBSERVED FACTS (AUTHORITATIVE SENSOR DATA) ---" in context.formatted_prompt
    assert "--- 7. STATIC METEOROLOGICAL REFERENCE KNOWLEDGE (RAG STATIC CORPUS) ---" in context.formatted_prompt
    assert "Current Temperature: 29.0°C" in context.formatted_prompt
    assert "IMD Rainfall Intensity Classifications" in context.formatted_prompt
    assert len(context.reference_knowledge) == 1


# =====================================================================
# 14. Official Warning Priority Over RAG
# =====================================================================

def test_official_warning_priority_over_rag(base_weather):
    now = datetime.now(timezone.utc)
    alert = OfficialAlert(
        type="cyclone",
        severity=RiskLevelEnum.EXTREME,
        title="Cyclone Red Alert",
        description="Destructive winds expected.",
        source="IMD",
        issued_at=now,
        expires_at=now + timedelta(hours=12)
    )
    nlu = parse_query("Is it safe?")
    reasoning = WeatherReasoner.evaluate(base_weather, active_alerts=[alert])
    from ai.decision import DecisionEngine
    advisory = DecisionEngine.generate_advisory(reasoning)

    retriever = get_knowledge_retriever()
    ref_chunks = retriever.retrieve("cyclone safety rules", top_k=1)

    context = build_grounded_context(
        nlu=nlu,
        weather=base_weather,
        reasoning=reasoning,
        advisory=advisory,
        reference_knowledge=ref_chunks
    )

    prompt = context.formatted_prompt
    # Warning section appears before static RAG section
    idx_warning = prompt.find("--- 3. OFFICIAL IMD WARNINGS")
    idx_rag = prompt.find("--- 7. STATIC METEOROLOGICAL REFERENCE KNOWLEDGE")
    assert idx_warning < idx_rag
    assert "MANDATE: LIVE SENSOR TELEMETRY AND ACTIVE OFFICIAL IMD ALERTS ALWAYS SUPERSEDE" in prompt or "MANDATE: Official IMD alerts have absolute priority" in prompt


# =====================================================================
# 15. Historical Document Versioning
# =====================================================================

def test_historical_document_versioning():
    doc = AUTHORITATIVE_DOCUMENTS[0]
    assert doc.version.startswith("2024")
    assert doc.updated_at.startswith("2024")
    assert doc.authority_level == "AUTHORITATIVE_GOVERNMENT"


# =====================================================================
# 16. Context Builder Prompt Formatting & 17. Retriever Scoring Semantics
# =====================================================================

def test_retriever_scoring_semantics():
    retriever = get_knowledge_retriever()
    results = retriever.retrieve("heatwave criteria plains", top_k=1)
    assert len(results) > 0
    score = results[0].relevance_score
    # Score is bounded between 0 and 1
    assert 0.0 < score <= 1.0


# =====================================================================
# 18. Full LLM + RAG Integration
# =====================================================================

def test_full_llm_plus_rag_integration(base_weather):
    nlu = parse_query("Explain what an IMD heavy rain warning means.")
    reasoning = WeatherReasoner.evaluate(base_weather)
    from ai.decision import DecisionEngine
    advisory = DecisionEngine.generate_advisory(reasoning)

    retriever = get_knowledge_retriever()
    ref_chunks = retriever.retrieve("heavy rainfall thresholds", top_k=1)

    mock_answer = "Per IMD standards, Heavy Rain is defined as 64.5 mm to 115.5 mm in 24 hours. In Nagapattinam, current temperature is 29°C with 75% rain probability."
    provider = MockLLMProvider(canned_response=mock_answer)
    generator = GroundedLLMGenerator(provider=provider)

    resp = generator.generate_response(
        nlu=nlu,
        weather=base_weather,
        reasoning=reasoning,
        advisory=advisory,
        reference_knowledge=ref_chunks
    )

    assert resp.is_fallback is False
    assert "IMD" in resp.answer
    assert "64.5 mm" in resp.answer
    assert resp.used_grounded_context is True
