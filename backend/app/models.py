"""Pydantic models for everything that crosses the HTTP boundary."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class IngestResult(BaseModel):
    document_id: UUID
    filename: str
    status: Literal["created", "updated", "unchanged"]
    num_chunks: int
    embedded_chunks: int  # chunks sent to the embedding API
    reused_chunks: int  # chunks whose embedding was reused via content hash
    embedding_tokens: int


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    num_chunks: int
    updated_at: datetime


type RetrievalMode = Literal["vector", "hybrid", "hybrid_rerank"]


class RetrievedChunk(BaseModel):
    id: int
    document: str
    section: str
    page: int | None
    content: str
    # 1-based position in each retriever's list; None if that retriever missed it.
    # Shown in the UI so you can see *why* a chunk was retrieved.
    vector_rank: int | None = None
    fulltext_rank: int | None = None
    flagged: bool = False  # looks like a prompt-injection attempt
