from app.config import Settings
from app.providers.base import Provider


def create_provider(settings: Settings) -> Provider:
    if settings.provider == "local":
        from app.providers.local import LocalProvider

        return LocalProvider(dim=settings.embedding_dim)
    from app.providers.gemini import GeminiProvider

    return GeminiProvider(settings)
