"""Tests for AAUA geofenced route preview generation."""

from __future__ import annotations

import pytest

from campus_voice.core.config import Settings
from campus_voice.models.schemas import Coordinate, RouteRequest
from campus_voice.services.routing.mock_provider import MockRoutingProvider
from campus_voice.services.routing.service import (
    OriginOutsideCampusError,
    RoutingService,
)


def _service() -> RoutingService:
    return RoutingService(provider=MockRoutingProvider(), settings=Settings())


def test_builds_simulated_route_to_etf_750_by_name() -> None:
    route = _service().build_route(
        RouteRequest(
            simulate_origin=Coordinate(
                latitude=7.481843099892803,
                longitude=5.741945337431659,
            ),
            destination_name="ETF750",
        )
    )

    assert route.simulated is True
    assert route.geofence.inside is True
    assert route.destination.name == "ETF 750"
    assert route.destination.coordinate is not None
    assert route.route_preview[0] == route.origin
    assert route.route_preview[-1] == route.destination.coordinate
    assert len(route.steps) == 1


def test_rejects_origin_outside_aaua_geofence() -> None:
    with pytest.raises(OriginOutsideCampusError):
        _service().build_route(
            RouteRequest(
                origin=Coordinate(latitude=6.5248, longitude=3.3798),
                destination_name="ETF750",
            )
        )
