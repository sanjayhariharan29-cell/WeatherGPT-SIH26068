"""Weather Knowledge & RAG Package for WeatherGPT.

Exposes the authoritative meteorological document corpus, document chunker,
deterministic semantic keyword retriever, and domain safety guidance.
"""

from ai.rag.chunker import chunk_document
from ai.rag.corpus import AUTHORITATIVE_DOCUMENTS
from ai.rag.knowledge_base import SAFETY_KNOWLEDGE_CORPUS, retrieve_safety_guidance
from ai.rag.retriever import KnowledgeRetriever, get_knowledge_retriever
from ai.rag.schema import KnowledgeChunk, KnowledgeDocument, RetrievedChunk

__all__ = [
    "KnowledgeDocument",
    "KnowledgeChunk",
    "RetrievedChunk",
    "chunk_document",
    "AUTHORITATIVE_DOCUMENTS",
    "KnowledgeRetriever",
    "get_knowledge_retriever",
    "SAFETY_KNOWLEDGE_CORPUS",
    "retrieve_safety_guidance",
]
