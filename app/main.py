"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

import app.models  # noqa: F401
from app.database import Base, engine
from app.routers.admin import router as admin_router
from app.routers.bootstrap import router as bootstrap_router
from app.routers.credentials import (
    router as credentials_router,
)
from app.routers.credentials import (
    services_router,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize database schema on startup.

    Yields
    ------
    None
        Runs the application lifespan.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Agent Key", lifespan=lifespan)
app.include_router(bootstrap_router)
app.include_router(admin_router)
app.include_router(credentials_router)
app.include_router(services_router)
