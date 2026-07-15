"""
/v1/tts — Text-to-Speech endpoints.
"""

from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from campus_voice.core.logging import get_logger
from campus_voice.models.schemas import SynthesizeRequest

logger = get_logger(__name__)

router = APIRouter(prefix="/tts", tags=["Text-to-Speech"])

_MIME_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
}


@router.post(
    "/synthesize",
    summary="Synthesize text to speech",
    response_description="Audio file (WAV or MP3)",
    responses={
        200: {
            "content": {
                "audio/wav": {"schema": {"type": "string", "format": "binary"}},
                "audio/mpeg": {"schema": {"type": "string", "format": "binary"}},
            },
            "description": "Synthesized audio stream",
        }
    },
    status_code=status.HTTP_200_OK,
)
async def synthesize(
    request: Request,
    body: SynthesizeRequest,
) -> Response:
    """
    Convert text to speech audio.

    Returns raw audio bytes with the appropriate `Content-Type` header.
    The mobile client can play the response directly.

    ```json
    {
      "text": "Hello, welcome to Campus Voice!",
      "voice": "af_heart",
      "speed": 1.0,
      "format": "wav"
    }
    ```
    """
    logger.info(
        "tts.synthesize.request",
        text_length=len(body.text),
        voice=body.voice,
        speed=body.speed,
        format=body.format,
    )

    tts = request.app.state.tts

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            partial(
                tts.synthesize,
                body.text,
                voice=body.voice,
                speed=body.speed,
                output_format=body.format,
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("tts.synthesize.error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech synthesis failed. See server logs for details.",
        ) from exc

    mime = _MIME_TYPES.get(result.format, "application/octet-stream")

    logger.info(
        "tts.synthesize.done",
        duration_s=result.duration_seconds,
        audio_bytes=len(result.audio_bytes),
        format=result.format,
    )

    return Response(
        content=result.audio_bytes,
        media_type=mime,
        headers={
            "X-Audio-Duration": str(result.duration_seconds),
            "X-Audio-Sample-Rate": str(result.sample_rate),
            "Content-Disposition": f'attachment; filename="speech.{result.format}"',
        },
    )
