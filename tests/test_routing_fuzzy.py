"""Fuzzy destination matching tests."""

from __future__ import annotations

from campus_voice.core.config import Settings
from campus_voice.models.schemas import Coordinate, RouteRequest
from campus_voice.services.routing.mock_provider import MockRoutingProvider
from campus_voice.services.routing.service import RoutingService


def _service() -> RoutingService:
    return RoutingService(
        provider=MockRoutingProvider(),
        settings=Settings(allow_simulated_origin=True),
    )


def test_matches_spoken_etf_750_variants() -> None:
    service = _service()
    route = service.build_route(
        RouteRequest(
            simulate_origin=Coordinate(
                latitude=7.481843099892803,
                longitude=5.741945337431659,
            ),
            destination_name="Take me to E,T,F 750",
        )
    )

    assert route.destination.name == "ETF 750"


def test_matches_typo_variant_itf750() -> None:
    service = _service()
    route = service.build_route(
        RouteRequest(
            simulate_origin=Coordinate(
                latitude=7.481843099892803,
                longitude=5.741945337431659,
            ),
            destination_name="ITF750",
        )
    )

    assert route.destination.name == "ETF 750"


def test_matches_digit_only_variant_750() -> None:
    service = _service()
    route = service.build_route(
        RouteRequest(
            simulate_origin=Coordinate(
                latitude=7.481843099892803,
                longitude=5.741945337431659,
            ),
            destination_name="750",
        )
    )

    assert route.destination.name == "ETF 750"
