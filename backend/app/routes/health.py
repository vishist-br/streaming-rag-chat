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
    return HealthResponse(
        status="ok",
        provider=s.provider,
        generation_model=s.active_models["generation"],
        embedding_model=s.active_models["embedding"],
    )
