"""FastAPI application factory."""

from fastapi import FastAPI

import app.models  # noqa: F401
from app.routers.admin import router as admin_router
from app.routers.bootstrap import router as bootstrap_router
from app.routers.credentials import (
    router as credentials_router,
)
from app.routers.credentials import (
    services_router,
)

app = FastAPI(title="Agent Key")
app.include_router(bootstrap_router)
app.include_router(admin_router)
app.include_router(credentials_router)
app.include_router(services_router)
