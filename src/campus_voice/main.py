"""
Entry point for uvicorn.

Run locally:
    uv run uvicorn campus_voice.main:app --reload --port 8000

Or via the helper script:
    uv run python -m campus_voice.main
"""

import uvicorn

from campus_voice.app import create_app
from campus_voice.core.config import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "campus_voice.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,   # keep 1 — models are not fork-safe
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
