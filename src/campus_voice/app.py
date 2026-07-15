"""
Application factory — keeps main.py minimal.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from campus_voice.api.v1 import router as v1_router
from campus_voice.core.config import get_settings
from campus_voice.core.lifespan import lifespan


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Campus Voice — AI voice assistant backend.\n\n"
            "Endpoints:\n"
            "- `POST /v1/stt/transcribe` — Audio → Text (faster-whisper)\n"
            "- `POST /v1/tts/synthesize` — Text → Audio (Kokoro 82M)\n"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred.", "type": type(exc).__name__},
        )

    # ── Routes ───────────────────────────────────────────────────────────────
    app.include_router(v1_router)

    return app
