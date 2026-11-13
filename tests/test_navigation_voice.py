"""Tests for preparing route instructions for the Kokoro voice model."""

from __future__ import annotations

from campus_voice.api.v1.routes.navigation import (
    clean_accessibility_instruction,
    clean_tts_pronunciation,
    prefetch_route_steps_tts,
)
from campus_voice.models.schemas import Coordinate, RouteStep


def test_route_instruction_is_cleaned_for_speech() -> None:
    instruction = clean_accessibility_instruction(
        "Head East for 15 meters toward ETF 750"
    )

    assert clean_tts_pronunciation(instruction) == (
        "Start walking for 20 footsteps toward E T F seven fifty"
    )


def test_tts_prefetch_uses_wav_and_canonical_destination_text() -> None:
    class FakeTTS:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def synthesize(self, text: str, *, output_format: str) -> None:
            self.calls.append((text, output_format))

    service = FakeTTS()
    step = RouteStep(
        instruction="Head East for 15 meters toward ETF 750",
        distance_meters=15,
        waypoint=Coordinate(latitude=7.4816, longitude=5.7421),
    )

    prefetch_route_steps_tts(service, [step], "ETF 750")

    assert service.calls[0] == (
        "Start walking for 20 footsteps toward E T F seven fifty",
        "wav",
    )
    assert (
        "You have arrived at your destination, E T F seven fifty.",
        "wav",
    ) in service.calls
