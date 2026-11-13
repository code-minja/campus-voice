"""Tests for AAUA geofenced route preview generation."""

from __future__ import annotations

import pytest

from campus_voice.core.config import Settings
from campus_voice.data.locations import LOCATIONS
from campus_voice.models.schemas import Coordinate, RouteRequest, RouteStep
from campus_voice.services.routing.google_routes_provider import (
    GoogleRoutesProvider,
    RouteBuildResult,
)
from campus_voice.services.routing.mock_provider import MockRoutingProvider
from campus_voice.services.routing.service import (
    DestinationNotFoundError,
    OriginOutsideCampusError,
    RoutingService,
    _build_provider,
)


def _service() -> RoutingService:
    return RoutingService(
        provider=MockRoutingProvider(),
        settings=Settings(allow_simulated_origin=True, _env_file=None),
    )


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
    assert route.geofence.enabled is True
    assert route.geofence.bounds.south <= route.origin.latitude <= route.geofence.bounds.north
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


def test_only_map_file_destinations_are_routable() -> None:
    with pytest.raises(DestinationNotFoundError):
        _service().build_route(
            RouteRequest(
                origin=Coordinate(latitude=7.4818, longitude=5.7419),
                destination_name="AAUA Main Gate",
            )
        )


def test_fence_cannot_be_disabled_and_covers_all_catalog_locations() -> None:
    service = RoutingService(
        provider=MockRoutingProvider(),
        settings=Settings(
            allow_simulated_origin=True,
            campus_geofence_enabled=False,
            campus_geofence_radius_meters=2500,
            _env_file=None,
        ),
    )

    assert all(
        service._is_inside_campus(
            Coordinate(
                latitude=location["latitude"],
                longitude=location["longitude"],
            )
        )
        for location in LOCATIONS.values()
    )
    with pytest.raises(OriginOutsideCampusError):
        service.build_route(
            RouteRequest(
                origin=Coordinate(latitude=7.486, longitude=5.748411),
                destination_name="ETF750",
            )
        )


def test_rejects_route_waypoints_outside_aaua_geofence() -> None:
    class OutsideRouteProvider:
        def build_route(self, **kwargs):
            outside = Coordinate(latitude=7.486, longitude=5.748411)
            return RouteBuildResult(
                steps=[
                    RouteStep(
                        instruction="Walk beyond the campus",
                        distance_meters=100,
                        waypoint=outside,
                    )
                ],
                duration_seconds=80,
                route_preview=[
                    kwargs["origin"],
                    outside,
                ],
            )

    service = RoutingService(
        provider=OutsideRouteProvider(),
        settings=Settings(_env_file=None),
    )
    with pytest.raises(OriginOutsideCampusError, match="Calculated route leaves"):
        service.build_route(
            RouteRequest(
                origin=Coordinate(latitude=7.481843, longitude=5.741945),
                destination_name="ETF750",
            )
        )


def test_real_google_routing_is_the_default_and_simulation_is_disabled() -> None:
    settings = Settings(_env_file=None)

    assert settings.routing_provider == "google_routes"
    assert settings.allow_simulated_origin is False
    assert isinstance(_build_provider(settings), GoogleRoutesProvider)


def test_rejects_simulated_origin_by_default() -> None:
    service = RoutingService(
        provider=MockRoutingProvider(),
        settings=Settings(_env_file=None),
    )

    with pytest.raises(OriginOutsideCampusError, match="Simulated origins are disabled"):
        service.build_route(
            RouteRequest(
                simulate_origin=Coordinate(latitude=7.4818, longitude=5.7419),
                destination_name="ETF750",
            )
        )


def test_routing_provider_errors_are_not_replaced_with_mock_routes() -> None:
    class FailingProvider:
        def build_route(self, **kwargs):
            raise RuntimeError("Google Routes is unavailable")

    service = RoutingService(
        provider=FailingProvider(),
        settings=Settings(campus_geofence_enabled=False, _env_file=None),
    )

    with pytest.raises(RuntimeError, match="Google Routes is unavailable"):
        service.build_route(
            RouteRequest(
                origin=Coordinate(latitude=7.4818, longitude=5.7419),
                destination_name="ETF750",
            )
        )


def test_google_provider_is_used_instead_of_curated_library_route() -> None:
    class TrackingProvider:
        called = False

        def build_route(self, **kwargs):
            self.called = True
            return RouteBuildResult(
                steps=[
                    RouteStep(
                        instruction="Google route step",
                        distance_meters=25,
                        waypoint=Coordinate(latitude=7.4819, longitude=5.7420),
                    )
                ],
                duration_seconds=20,
            )

    provider = TrackingProvider()
    service = RoutingService(
        provider=provider,
        settings=Settings(_env_file=None),
    )
    route = service.build_route(
        RouteRequest(
            origin=Coordinate(latitude=7.481843, longitude=5.741945),
            destination_name="University Library",
        )
    )

    assert provider.called is True
    assert route.steps[0].instruction == "Google route step"
