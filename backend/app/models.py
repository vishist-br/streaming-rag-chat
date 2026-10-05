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
