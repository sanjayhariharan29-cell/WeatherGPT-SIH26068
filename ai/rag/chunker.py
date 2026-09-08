"""Document Chunking Engine for WeatherGPT RAG.

Splits authoritative meteorological documents into semantic, header-aware chunks
while preserving document metadata, hierarchy, and context integrity.
"""

import re
from typing import List
from ai.rag.schema import KnowledgeChunk, KnowledgeDocument


def chunk_document(doc: KnowledgeDocument, max_chunk_chars: int = 800) -> List[KnowledgeChunk]:
    """Splits a KnowledgeDocument into deterministic, header-aware chunks."""
    chunks: List[KnowledgeChunk] = []
    text = doc.content.strip()

    # Split on markdown headings: ## or ###
    sections = re.split(r"(?=(?:^|\n)#{2,3}\s+)", text)
    chunk_index = 0

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # Extract heading if present
        heading_match = re.match(r"^#{2,3}\s+(.+?)(?:\n|$)", sec)
        if heading_match:
            heading = heading_match.group(1).strip()
            body = sec[heading_match.end():].strip()
        else:
            heading = doc.title
            body = sec

        # If body is within max_chunk_chars, emit as a single chunk
        if len(body) <= max_chunk_chars:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{doc.id}_chk_{chunk_index}",
                    doc_id=doc.id,
                    title=doc.title,
                    heading=heading,
                    content=body,
                    topic=doc.topic,
                    source=doc.source,
                    language=doc.language,
                    authority_level=doc.authority_level,
                    metadata=dict(doc.metadata)
                )
            )
            chunk_index += 1
        else:
            # Further split large section by double newlines / paragraphs
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            current_buffer = []
            current_len = 0

            for p in paragraphs:
                if current_len + len(p) > max_chunk_chars and current_buffer:
                    sub_content = "\n\n".join(current_buffer)
                    chunks.append(
                        KnowledgeChunk(
                            chunk_id=f"{doc.id}_chk_{chunk_index}",
                            doc_id=doc.id,
                            title=doc.title,
                            heading=heading,
                            content=sub_content,
                            topic=doc.topic,
                            source=doc.source,
                            language=doc.language,
                            authority_level=doc.authority_level,
                            metadata=dict(doc.metadata)
                        )
                    )
                    chunk_index += 1
                    current_buffer = [p]
                    current_len = len(p)
                else:
                    current_buffer.append(p)
                    current_len += len(p)

            if current_buffer:
                sub_content = "\n\n".join(current_buffer)
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"{doc.id}_chk_{chunk_index}",
                        doc_id=doc.id,
                        title=doc.title,
                        heading=heading,
                        content=sub_content,
                        topic=doc.topic,
                        source=doc.source,
                        language=doc.language,
                        authority_level=doc.authority_level,
                        metadata=dict(doc.metadata)
                    )
                )
                chunk_index += 1

    return chunks
