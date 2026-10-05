"""All tunables in one place, loaded from environment variables (or a .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql://rag:rag@localhost:5432/rag"
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Providers -----------------------------------------------------------
    provider: Literal["gemini", "ollama", "local"] = "gemini"
    gemini_api_key: str = ""
    generation_model: str = "gemini-3.8-flash"
    # Cheaper model for the short "plumbing" calls: query rewrite and rerank.
    fast_model: str = "gemini-3.5-flash-lite"
    embedding_model: str = "gemini-embedding-2"
    # Ollama: real open models running on your own machine, no API key or cost.
    ollama_base_url: str = "http://localhost:11434"
    ollama_generation_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"  # 768 dimensions
    # Must match vector(768) in schema.sql. Changing it means re-creating the column.
    embedding_dim: int = 768

    # --- Ingestion -----------------------------------------------------------
    chunk_target_tokens: int = 400
    chunk_overlap_tokens: int = 60
    embed_batch_size: int = 32
    max_upload_bytes: int = 10 * 1024 * 1024

    # --- Retrieval -----------------------------------------------------------
    vector_k: int = 20  # candidates from pgvector
    fulltext_k: int = 20  # candidates from Postgres full-text search
    rrf_k: int = 60  # RRF constant from the original paper
    rerank_candidates: int = 20  # fused candidates sent to the reranker
    final_k: int = 5  # chunks that reach the prompt

    # --- Guardrails ----------------------------------------------------------
    max_question_chars: int = 2000
    max_history_messages: int = 8
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    # --- Cost estimation (USD per 1M tokens; update when prices change) ------
    price_generation_input: float = 0.75
    price_generation_output: float = 3.75
    price_fast_input: float = 0.30
    price_fast_output: float = 2.50
    price_embedding_input: float = 0.20

    @property
    def active_models(self) -> dict[str, str]:
        """The model names actually in use for the configured provider."""
        if self.provider == "ollama":
            return {
                "generation": self.ollama_generation_model,
                "fast": self.ollama_generation_model,
                "embedding": self.ollama_embedding_model,
            }
        if self.provider == "local":
            return {
                "generation": "offline-extractive",
                "fast": "none",
                "embedding": "hashed-bag-of-words",
            }
        return {
            "generation": self.generation_model,
            "fast": self.fast_model,
            "embedding": self.embedding_model,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
