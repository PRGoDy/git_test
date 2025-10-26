from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from .routers import audit, auth as auth_router, catalog, console, requests, sessions, users

logger = logging.getLogger("access_hub")
settings = get_settings()

app = FastAPI(title=settings.app_name, openapi_url=f"{settings.api_prefix}/openapi.json")


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


api = FastAPI()

api.include_router(auth_router.router)
api.include_router(users.router)
api.include_router(catalog.router)
api.include_router(requests.router)
api.include_router(sessions.router)
api.include_router(console.router)
api.include_router(audit.router)


app.mount(settings.api_prefix, api)


@app.get("/healthz")
async def healthcheck() -> dict:
    return {"status": "ok"}
