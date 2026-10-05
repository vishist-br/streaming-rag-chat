from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    provider: str
    generation_model: str
    embedding_model: str


@router.get("/api/health")
async def health() -> HealthResponse:
    s = get_settings()
    local = s.provider == "local"
    return HealthResponse(
        status="ok",
        provider=s.provider,
        generation_model="offline-extractive" if local else s.generation_model,
        embedding_model="hashed-bag-of-words" if local else s.embedding_model,
    )
