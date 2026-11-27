"""FastAPI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import current_user_id
from app.config import Settings, get_settings
from app.routes import chat, profile
from app.runtime import open_runtime


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_runtime(settings) as runtime:
            app.state.runtime = runtime
            yield

    app = FastAPI(title="The Grove API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health(s: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
        return {"status": "ok", "env": s.app_env, "adapters": s.adapter_modes()}

    @app.get("/me")
    def me(user_id: Annotated[str, Depends(current_user_id)]) -> dict[str, str]:
        return {"user_id": user_id}

    app.include_router(chat.router)
    app.include_router(profile.router)

    if settings.storage_backend == "local":
        settings.local_storage_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/media", StaticFiles(directory=settings.local_storage_dir), name="media")

    return app
