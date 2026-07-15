"""
/v1/stt — Speech-to-Text endpoints.
"""

from __future__ import annotations

import asyncio
from functools import partial

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from campus_voice.core.logging import get_logger
from campus_voice.models.schemas import (
    TranscribeResponse,
    TranscriptionCorrection,
    TranscriptionSegment,
)
from campus_voice.services.text_processing.stt_postprocessor import STTPostProcessor

logger = get_logger(__name__)

router = APIRouter(prefix="/stt", tags=["Speech-to-Text"])
post_processor = STTPostProcessor()

_MAX_AUDIO_MB = 25
_MAX_BYTES = _MAX_AUDIO_MB * 1024 * 1024


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio to text",
    status_code=status.HTTP_200_OK,
)
async def transcribe(
    request: Request,
    file: UploadFile = File(..., description="Audio file (wav, mp3, ogg, flac, m4a)"),
    language: str | None = Form(
        default=None,
        description="BCP-47 language hint (e.g. 'en', 'yo'). Omit for auto-detect.",
    ),
    task: str = Form(
        default="transcribe",
        pattern="^(transcribe|translate)$",
        description="'transcribe' keeps source language; 'translate' → English.",
    ),
) -> TranscribeResponse:
    """
    Upload an audio file and receive the transcribed text.

    - **file**: Any audio format supported by libsndfile (wav, mp3, ogg, flac).
    - **language**: Optional language hint; auto-detected when omitted.
    - **task**: `transcribe` (default) or `translate` (output forced to English).
    """
    # ── Validate size ────────────────────────────────────────────────────────
    audio_bytes = await file.read()
    if len(audio_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds {_MAX_AUDIO_MB} MB limit.",
        )
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    logger.info(
        "stt.transcribe.request",
        filename=file.filename,
        content_type=file.content_type,
        size_bytes=len(audio_bytes),
        language=language,
        task=task,
    )

    stt = request.app.state.stt

    # Run in thread pool — transcription is CPU-bound
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            partial(stt.transcribe, audio_bytes, language=language, task=task),
        )
    except Exception as exc:
        logger.error("stt.transcribe.error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. See server logs for details.",
        ) from exc

    logger.info(
        "stt.transcribe.done",
        language=result.language,
        probability=result.language_probability,
        text_length=len(result.text),
    )

    processed = post_processor.process(result.text)

    return TranscribeResponse(
        text=processed.text,
        raw_text=processed.raw_text if processed.post_processed else None,
        post_processed=processed.post_processed,
        corrections=[
            TranscriptionCorrection(
                kind=correction.kind,
                original=correction.original,
                replacement=correction.replacement,
                confidence=correction.confidence,
            )
            for correction in processed.corrections
        ],
        language=result.language,
        language_probability=result.language_probability,
        segments=[TranscriptionSegment(**s) for s in result.segments],
    )
