"""
Application lifespan — models load ONCE at startup, not per request.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from campus_voice.core.config import get_settings
from campus_voice.core.logging import configure_logging, get_logger
from campus_voice.services.stt_service import STTService
from campus_voice.services.tts_service import TTSService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Load ML models on startup; release on shutdown.
    Models are stored in app.state so routes can access them via Request.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info("campus_voice.startup", version=settings.app_version)

    # ── Load STT ──────────────────────────────────────────────────────────
    logger.info("loading_stt_model", model=settings.whisper_model_size)
    stt_service = STTService(settings)
    stt_service.load()
    app.state.stt = stt_service
    logger.info("stt_model_ready")

    # ── Load TTS ──────────────────────────────────────────────────────────
    logger.info("loading_tts_model")
    tts_service = TTSService(settings)
    tts_service.load()
    app.state.tts = tts_service
    logger.info("tts_model_ready")

    # Start startup prefetch in the background
    import threading
    def run_startup_prefetch(tts):
        from campus_voice.api.v1.routes.navigation import clean_tts_pronunciation
        from campus_voice.data.locations import LOCATIONS

        logger.info("tts.startup_prefetch.start")
        phrases = [
            "Hi! I'm CampusVoice. Where would you like to go?",
            "Where would you like to go?",
            "Please repeat your destination.",
            "Please say yes to begin navigation, or cancel to go back.",
        ]
        for loc in LOCATIONS.values():
            name = loc["name"]
            phrases += [
                f"I heard {name}. Say yes to continue or no to try again.",
                f"Great. Opening route preview for {name}.",
                f"Please say yes to confirm {name}, or no to try again.",
                f"Route preview ready for {name}.",
                f"Starting voice-only navigation to {name}.",
                f"You have arrived at your destination, {name}.",
                f"You are off route. Recalculating a path to {name}.",
            ]
        phrases = [clean_tts_pronunciation(p) for p in phrases]

        for phrase in phrases:
            try:
                tts.synthesize(phrase, background=True)
            except Exception:
                pass
        logger.info("tts.startup_prefetch.complete", count=len(phrases))

    threading.Thread(target=run_startup_prefetch, args=(tts_service,), daemon=True).start()

    yield  # ← app is running

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("campus_voice.shutdown")
    stt_service.unload()
    tts_service.unload()
