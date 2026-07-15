"""
/v1/route — Navigation endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Request, BackgroundTasks

import re
from typing import Any
from campus_voice.models.schemas import RouteRequest, RouteResponse, RouteStep
from campus_voice.services.routing.service import (
    DestinationNotFoundError,
    OriginOutsideCampusError,
    build_default_routing_service,
)

router = APIRouter(tags=["Navigation"])
routing_service = build_default_routing_service()


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


def prefetch_route_steps_tts(tts_service: Any, steps: list[RouteStep], destination_name: str) -> None:
    """Background task to pre-synthesize and disk-cache TTS for all route events to remove speech latency."""
    phrases = []
    # 1. Cleaned step instructions
    for step in steps:
        phrases.append(clean_accessibility_instruction(step.instruction))
    # 2. General route flow prompts
    phrases.append(f"Route preview ready for {destination_name}. Say yes to begin navigation, or cancel to go back.")
    phrases.append(f"Starting navigation to {destination_name}.")
    # 3. Arrival and rerouting prompts
    phrases.append(f"You have arrived at your destination, {destination_name}")
    phrases.append(f"Rerouting... Recalculating path to {destination_name}")

    for phrase in phrases:
        try:
            tts_service.synthesize(phrase)
        except Exception:
            pass


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
            dest_name = payload.destination_name or response.destination.name
            background_tasks.add_task(
                prefetch_route_steps_tts,
                tts_service,
                response.steps,
                dest_name
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
