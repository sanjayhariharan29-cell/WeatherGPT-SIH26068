"""RAG Schemas and Models for Meteorological Knowledge Grounding.

Defines document, chunk, and retrieval result schemas with comprehensive metadata,
strict provenance tracking, and explicit relevance score semantics.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """Authoritative source document model."""
    id: str
    title: str
    source: str
    source_type: str = Field(
        default="OFFICIAL_GUIDELINE",
        description="e.g. OFFICIAL_GUIDELINE, METEOROLOGICAL_STANDARD, SAFETY_PROTOCOL"
    )
    topic: str = Field(
        description="e.g. cyclone, heavy_rain, flood, thunderstorm, heatwave, coldwave, terminology"
    )
    language: str = Field(default="en", description="en, ta, hi")
    authority_level: str = Field(
        default="AUTHORITATIVE_GOVERNMENT",
        description="e.g. AUTHORITATIVE_GOVERNMENT, OFFICIAL_STANDARD"
    )
    version: str = "1.0"
    updated_at: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    """Deterministic, granular chunk for knowledge retrieval."""
    chunk_id: str
    doc_id: str
    title: str
    heading: str
    content: str
    topic: str
    source: str
    language: str = "en"
    authority_level: str = "AUTHORITATIVE_GOVERNMENT"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """Result of a knowledge retrieval query."""
    chunk: KnowledgeChunk
    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Retrieval relevance score (0.0 to 1.0). Indicates keyword/topic alignment, NOT factual certainty or weather probability."
    )
    matched_terms: List[str] = Field(default_factory=list)
