"""FastAPI dependencies: shared objects created once in main.lifespan."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.db import Pool
from app.providers.base import Provider


def get_pool(request: Request) -> Pool:
    return cast(Pool, request.app.state.pool)


def get_provider(request: Request) -> Provider:
    return cast(Provider, request.app.state.provider)


PoolDep = Annotated[Pool, Depends(get_pool)]
ProviderDep = Annotated[Provider, Depends(get_provider)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
