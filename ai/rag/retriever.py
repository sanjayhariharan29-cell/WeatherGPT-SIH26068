"""Knowledge Retrieval Engine for WeatherGPT RAG.

Provides deterministic, metadata-aware semantic keyword retrieval over authoritative
meteorological documents, with source whitelisting, low-relevance suppression,
deduplication, and language filtering.
"""

import math
import re
from typing import Dict, List, Optional, Set
from ai.rag.chunker import chunk_document
from ai.rag.corpus import AUTHORITATIVE_DOCUMENTS
from ai.rag.schema import KnowledgeChunk, KnowledgeDocument, RetrievedChunk

SOURCE_WHITELIST: Set[str] = {
    "India Meteorological Department (IMD)",
    "National Disaster Management Authority (NDMA)",
    "Tamil Nadu SDMA (TNSDMA)",
    "Ministry of Earth Sciences (MoES)",
    "State Disaster Management Authority",
}


def _tokenize(text: str) -> List[str]:
    """Tokenizes text into lowercase alphanumeric and Unicode script tokens."""
    # Preserves English, Tamil, and Hindi script tokens
    return [t.lower() for t in re.findall(r"[\w\u0B80-\u0BFF\u0900-\u097F]+", text) if len(t) > 1]


class KnowledgeRetriever:
    """Deterministic, provider-neutral retriever over authoritative meteorological documents."""

    def __init__(self, documents: Optional[List[KnowledgeDocument]] = None):
        self.chunks: List[KnowledgeChunk] = []
        self._idf: Dict[str, float] = {}

        # Ingest default authoritative documents
        docs = documents if documents is not None else AUTHORITATIVE_DOCUMENTS
        for doc in docs:
            self.add_document(doc)

    def add_document(self, doc: KnowledgeDocument) -> None:
        """Chunks and indexes an authoritative KnowledgeDocument."""
        if doc.source not in SOURCE_WHITELIST and "IMD" not in doc.source and "NDMA" not in doc.source:
            # Enforce source whitelist guardrail
            return

        doc_chunks = chunk_document(doc)
        for chunk in doc_chunks:
            self.add_chunk(chunk)

    def add_chunk(self, chunk: KnowledgeChunk) -> None:
        """Indexes an individual KnowledgeChunk."""
        self.chunks.append(chunk)
        self._recompute_idf()

    def _recompute_idf(self) -> None:
        """Computes inverse document frequencies across indexed chunks."""
        total_chunks = len(self.chunks)
        if total_chunks == 0:
            self._idf = {}
            return

        doc_freqs: Dict[str, int] = {}
        for chk in self.chunks:
            tokens = set(_tokenize(f"{chk.title} {chk.heading} {chk.content} {chk.topic}"))
            for t in tokens:
                doc_freqs[t] = doc_freqs.get(t, 0) + 1

        self._idf = {
            t: math.log((total_chunks - df + 0.5) / (df + 0.5) + 1.0)
            for t, df in doc_freqs.items()
        }

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        topic: Optional[str] = None,
        language: Optional[str] = None,
        min_score: float = 0.15
    ) -> List[RetrievedChunk]:
        """Retrieves top-k relevant knowledge chunks with deterministic relevance scoring."""
        if not self.chunks or not query.strip():
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored_results: List[RetrievedChunk] = []
        seen_chunk_ids: Set[str] = set()

        for chunk in self.chunks:
            # Language filter (if specified)
            if language and chunk.language != language:
                # Allow Tamil queries to match 'ta' chunks, English queries to match 'en' chunks
                continue

            # Topic filter (if specified)
            if topic and chunk.topic != topic:
                continue

            content_tokens = _tokenize(chunk.content)
            heading_tokens = set(_tokenize(chunk.heading))
            title_tokens = set(_tokenize(chunk.title))
            topic_tokens = set(_tokenize(chunk.topic))

            matched_terms: List[str] = []
            score = 0.0

            for q_term in query_tokens:
                term_idf = self._idf.get(q_term, 1.0)
                term_count = content_tokens.count(q_term)

                if term_count > 0:
                    matched_terms.append(q_term)
                    # Base TF-IDF score component
                    tf = term_count / (term_count + 1.2)
                    score += tf * term_idf

                # Heading / title / topic prominence bonus
                if q_term in heading_tokens:
                    score += 1.5 * term_idf
                    if q_term not in matched_terms:
                        matched_terms.append(q_term)
                if q_term in title_tokens:
                    score += 1.0 * term_idf
                if q_term in topic_tokens:
                    score += 1.2 * term_idf

            # Normalize score to 0.0 - 1.0 range
            if score > 0.0:
                norm_score = min(1.0, round(score / (len(query_tokens) * 2.5 + 0.001), 3))
                if norm_score >= min_score and chunk.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk.chunk_id)
                    scored_results.append(
                        RetrievedChunk(
                            chunk=chunk,
                            relevance_score=norm_score,
                            matched_terms=matched_terms
                        )
                    )

        # Sort descending by relevance score
        scored_results.sort(key=lambda r: r.relevance_score, reverse=True)
        return scored_results[:top_k]


# Global singleton instance for pipeline access
_default_retriever: Optional[KnowledgeRetriever] = None


def get_knowledge_retriever() -> KnowledgeRetriever:
    """Returns the global default KnowledgeRetriever instance."""
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = KnowledgeRetriever()
    return _default_retriever
