"""
/v1/route — Navigation endpoint.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from campus_voice.core.logging import get_logger
from campus_voice.models.schemas import RouteRequest, RouteResponse, RouteStep
from campus_voice.services.routing.service import (
    DestinationNotFoundError,
    OriginOutsideCampusError,
    build_default_routing_service,
)

router = APIRouter(tags=["Navigation"])
routing_service = build_default_routing_service()
logger = get_logger(__name__)


def clean_accessibility_instruction(instruction: str) -> str:
    text = instruction
    text = re.sub(r"\bHead SouthEast\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead SouthWest\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead NorthEast\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead NorthWest\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead North\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead South\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead East\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead West\b", "Start walking", text, flags=re.IGNORECASE)
    text = re.sub(r"\bHead\b", "Walk", text, flags=re.IGNORECASE)

    def repl(match):
        meters = float(match.group(1))
        footsteps = max(1, round(meters / 0.75))
        return f"{footsteps} footsteps"

    text = re.sub(r"(\d+(?:\.\d+)?)\s*(?:meters|meter|m)\b", repl, text, flags=re.IGNORECASE)
    return text


def clean_tts_pronunciation(text: str) -> str:
    text = re.sub(r"\bAAUA\b", "A A U A", text, flags=re.IGNORECASE)
    text = re.sub(r"\bETF\s*750\b", "E T F seven fifty", text, flags=re.IGNORECASE)
    text = re.sub(r"\bETF\b", "E T F", text, flags=re.IGNORECASE)
    text = re.sub(r"\bOBJ\b", "O B J", text, flags=re.IGNORECASE)
    text = re.sub(r"\bLT\s*A\b", "L T A", text, flags=re.IGNORECASE)
    text = re.sub(r"\bLT\b", "L T", text, flags=re.IGNORECASE)
    return re.sub(r"\bRC\b", "R C", text, flags=re.IGNORECASE)


def prefetch_route_steps_tts(tts_service: Any, steps: list[RouteStep], destination_name: str) -> None:
    """Background task to pre-synthesize and disk-cache TTS for all route events to remove speech latency."""
    phrases = [
        clean_tts_pronunciation(clean_accessibility_instruction(step.instruction))
        for step in steps
    ]
    phrases.extend(
        clean_tts_pronunciation(phrase)
        for phrase in (
            f"Starting voice-only navigation to {destination_name}.",
            f"You have arrived at your destination, {destination_name}.",
            f"You are off route. Recalculating a path to {destination_name}.",
        )
    )

    for phrase in phrases:
        try:
            tts_service.synthesize(phrase, background=True)
        except Exception as exc:
            logger.warning(
                "navigation.tts_prefetch_failed",
                error=str(exc),
                text=phrase[:80],
            )


@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Build walking route to a destination",
    status_code=status.HTTP_200_OK,
)
def route(payload: RouteRequest, request: Request, background_tasks: BackgroundTasks) -> RouteResponse:
    """Compute turn-by-turn walking route from origin to destination."""
    try:
        response = routing_service.build_route(payload)

        # Trigger background prefetch for TTS audio files
        tts_service = getattr(request.app.state, "tts", None)
        if tts_service:
            background_tasks.add_task(
                prefetch_route_steps_tts,
                tts_service,
                response.steps,
                response.destination.name,
            )

        return response
    except DestinationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OriginOutsideCampusError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
