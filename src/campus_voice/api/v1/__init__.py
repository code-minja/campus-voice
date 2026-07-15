"""
Aggregate all v1 routes into a single router.
"""

from fastapi import APIRouter

from campus_voice.api.v1.routes import health, locations, navigation, stt, tts

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(locations.router)
router.include_router(stt.router)
router.include_router(tts.router)
router.include_router(navigation.router)
