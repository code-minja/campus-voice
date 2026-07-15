"""
Health-check endpoints for liveness and readiness probes.
"""

from fastapi import APIRouter, Request

from campus_voice.core.config import get_settings
from campus_voice.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(request: Request) -> HealthResponse:
    """
    Returns the health status of the API and its loaded services.
    Use this as a readiness probe in Docker / Kubernetes.
    """
    settings = get_settings()

    stt_status = "ready" if getattr(request.app.state, "stt", None) is not None else "not_loaded"
    tts_status = "ready" if getattr(request.app.state, "tts", None) is not None else "not_loaded"

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        services={"stt": stt_status, "tts": tts_status},
    )


@router.get("/", include_in_schema=False)
async def root() -> dict:
    return {"message": "Campus Voice API", "docs": "/docs"}
