"""Routing application service."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from campus_voice.core.config import Settings, get_settings
from campus_voice.data.locations import (
    AAUA_CAMPUS_BOUNDS,
    AAUA_CAMPUS_CENTER,
    AAUA_CAMPUS_RADIUS_METERS,
    LOCATIONS,
    LocationRecord,
)
from campus_voice.models.schemas import (
    Coordinate,
    DestinationSummary,
    GeofenceStatus,
    RouteRequest,
    RouteResponse,
    RouteStep,
)
from campus_voice.services.routing.base import RoutingProvider
from campus_voice.services.routing.geo import distance_meters, bearing_degrees
from campus_voice.services.routing.google_routes_provider import GoogleRoutesProvider, RouteBuildResult
from campus_voice.services.routing.mock_provider import MockRoutingProvider


class DestinationNotFoundError(Exception):
    """Raised when a destination_id is not found."""


class OriginOutsideCampusError(Exception):
    """Raised when the route origin is outside the configured campus geofence."""


@dataclass(slots=True)
class RoutingService:
    """Coordinates location lookup and route generation."""

    provider: RoutingProvider
    settings: Settings

    def build_route(self, payload: RouteRequest) -> RouteResponse:
        origin = self._get_origin(payload)
        location = self._get_destination(payload)

        destination_coordinate = Coordinate(
            latitude=location["latitude"],
            longitude=location["longitude"],
        )
        destination = DestinationSummary(
            id=location["id"],
            name=location["name"],
            coordinate=destination_coordinate,
        )

        geofence = self._build_geofence_status(origin)
        if geofence.enabled and not geofence.inside:
            raise OriginOutsideCampusError(
                "Starting point is outside the AAUA campus geofence"
            )
        if not self._is_inside_campus(destination_coordinate):
            raise DestinationNotFoundError(
                "Destination is outside the AAUA campus geofence"
            )

        result = self.provider.build_route(
            origin=origin,
            destination=destination,
            destination_coordinate=destination_coordinate,
        )
        steps = result.steps
        route_points = [*(result.route_preview or []), *(step.waypoint for step in steps)]
        if any(not self._is_inside_campus(point) for point in route_points):
            raise OriginOutsideCampusError(
                "Calculated route leaves the AAUA campus geofence"
            )
        total_distance = round(sum(step.distance_meters for step in steps), 1)
        route_preview = result.route_preview or [origin, *(step.waypoint for step in steps)]

        return RouteResponse(
            origin=origin,
            destination=destination,
            geofence=geofence,
            route_preview=route_preview,
            steps=steps,
            total_distance_meters=total_distance,
            estimated_duration_seconds=result.duration_seconds or round(total_distance / 1.25),
            simulated=payload.simulate_origin is not None,
        )

    def _get_origin(self, payload: RouteRequest) -> Coordinate:
        if payload.simulate_origin is not None:
            if not self.settings.allow_simulated_origin:
                raise OriginOutsideCampusError("Simulated origins are disabled")
            return payload.simulate_origin
        if payload.origin is None:
            raise OriginOutsideCampusError("origin or simulate_origin is required")
        return payload.origin

    def _get_curated_route(
        self,
        origin: Coordinate,
        destination: DestinationSummary,
        destination_coordinate: Coordinate,
    ) -> RouteBuildResult | None:
        """Return curated walkway coordinates for key campus routes to ensure 100% road accuracy."""
        # 1. ETF 750 (approx 7.481843, 5.741945)
        is_origin_etf = abs(origin.latitude - 7.481843) < 0.0005 and abs(origin.longitude - 5.741945) < 0.0005
        # 2. Quadrangle GEY LT (approx 7.481250, 5.745900)
        is_origin_geylt = abs(origin.latitude - 7.481250) < 0.0005 and abs(origin.longitude - 5.745900) < 0.0005
        # 3. Faculty of Computing (approx 7.482180, 5.741410)
        is_origin_computing = abs(origin.latitude - 7.482180) < 0.0005 and abs(origin.longitude - 5.741410) < 0.0005
        # 4. Senate Building (approx 7.479234, 5.748411)
        is_origin_senate = abs(origin.latitude - 7.479234) < 0.0005 and abs(origin.longitude - 5.748411) < 0.0005
        # 5. AAUA Main Gate (approx 7.474640, 5.751330)
        is_origin_maingate = abs(origin.latitude - 7.474640) < 0.0005 and abs(origin.longitude - 5.751330) < 0.0005

        is_dest_library = destination.name.lower().find("library") != -1

        if not is_dest_library:
            return None

        # Helper to build steps automatically from waypoints
        def build_curated_steps(waypoints: list[Coordinate], instructions: list[str]) -> RouteBuildResult:
            steps = []
            for i in range(len(waypoints) - 1):
                start = waypoints[i]
                end = waypoints[i + 1]
                dist = round(distance_meters(start, end), 1)
                bearing = round(bearing_degrees(start, end), 1)
                steps.append(
                    RouteStep(
                        step_number=i + 1,
                        instruction=instructions[i].format(dist=dist),
                        distance_meters=dist,
                        heading_degrees=bearing,
                        waypoint=end,
                    )
                )
            return RouteBuildResult(
                steps=steps,
                duration_seconds=round(sum(s.distance_meters for s in steps) / 1.25),
                route_preview=waypoints,
            )

        # Route 1: ETF 750 -> Library
        if is_origin_etf:
            waypoints = [
                origin,
                Coordinate(latitude=7.48150, longitude=5.74280),
                Coordinate(latitude=7.48090, longitude=5.74410),
                Coordinate(latitude=7.48110, longitude=5.74560),
                destination_coordinate,
            ]
            instructions = [
                "Start walking East on the main walkway for {dist} meters towards the relaxation center",
                "Turn right and walk past the Faculty of Law for {dist} meters",
                "Turn left and walk past the Faculty of Science for {dist} meters",
                "Continue straight along the Library walk and arrive at the Library entrance in {dist} meters",
            ]
            return build_curated_steps(waypoints, instructions)

        # Route 2: Quadrangle GEY LT -> Library
        if is_origin_geylt:
            waypoints = [
                origin,
                Coordinate(latitude=7.48120, longitude=5.74680),
                Coordinate(latitude=7.48115, longitude=5.74780),
                destination_coordinate,
            ]
            instructions = [
                "Start walking East from GEY LT towards the Science Lecture block for {dist} meters",
                "Continue straight along the paved Science walkway towards the Library lawn for {dist} meters",
                "Turn slightly right and proceed to the University Library entrance in {dist} meters",
            ]
            return build_curated_steps(waypoints, instructions)

        # Route 3: Faculty of Computing -> Library
        if is_origin_computing:
            waypoints = [
                origin,
                Coordinate(latitude=7.48184, longitude=5.74194),
                Coordinate(latitude=7.48150, longitude=5.74280),
                Coordinate(latitude=7.48090, longitude=5.74410),
                Coordinate(latitude=7.48110, longitude=5.74560),
                destination_coordinate,
            ]
            instructions = [
                "Head Southeast from the Faculty of Computing block towards ETF 750 for {dist} meters",
                "Pass ETF 750 and walk East on the main walkway for {dist} meters",
                "Turn right and walk past the Faculty of Law for {dist} meters",
                "Turn left and walk past the Faculty of Science for {dist} meters",
                "Continue straight along the Library walk and arrive at the Library entrance in {dist} meters",
            ]
            return build_curated_steps(waypoints, instructions)

        # Route 4: Senate Building -> Library
        if is_origin_senate:
            waypoints = [
                origin,
                Coordinate(latitude=7.47980, longitude=5.74850),
                Coordinate(latitude=7.48050, longitude=5.74860),
                destination_coordinate,
            ]
            instructions = [
                "Exit the Senate Building main lobby and walk North towards the administrative road for {dist} meters",
                "Cross the road and follow the paved pathway past the Senate car park for {dist} meters",
                "Head North along the Library lawn path and arrive at the Library entrance in {dist} meters",
            ]
            return build_curated_steps(waypoints, instructions)

        # Route 5: AAUA Main Gate -> Library
        if is_origin_maingate:
            waypoints = [
                origin,
                Coordinate(latitude=7.47650, longitude=5.75010),
                Coordinate(latitude=7.47880, longitude=5.74880),
                destination_coordinate,
            ]
            instructions = [
                "Enter through the AAUA Main Gate and walk Northwest along the main drive for {dist} meters",
                "Pass the Sport Complex roundabout and continue straight on the main road for {dist} meters",
                "Turn slightly right near the Senate junction and head North towards the Library for {dist} meters",
            ]
            return build_curated_steps(waypoints, instructions)

        return None

    @staticmethod
    def _build_geofence_status(origin: Coordinate) -> GeofenceStatus:
        center = Coordinate(
            latitude=AAUA_CAMPUS_CENTER["latitude"],
            longitude=AAUA_CAMPUS_CENTER["longitude"],
        )
        distance_from_center = round(distance_meters(origin, center), 1)
        radius = AAUA_CAMPUS_RADIUS_METERS
        return GeofenceStatus(
            enabled=True,
            inside=RoutingService._is_inside_campus(origin),
            center=center,
            radius_meters=radius,
            distance_from_center_meters=distance_from_center,
            bounds=AAUA_CAMPUS_BOUNDS,
        )

    @staticmethod
    def _is_inside_campus(point: Coordinate) -> bool:
        inside_bounds = (
            AAUA_CAMPUS_BOUNDS["south"]
            <= point.latitude
            <= AAUA_CAMPUS_BOUNDS["north"]
            and AAUA_CAMPUS_BOUNDS["west"]
            <= point.longitude
            <= AAUA_CAMPUS_BOUNDS["east"]
        )
        center = Coordinate(
            latitude=AAUA_CAMPUS_CENTER["latitude"],
            longitude=AAUA_CAMPUS_CENTER["longitude"],
        )
        return (
            inside_bounds
            and distance_meters(point, center) <= AAUA_CAMPUS_RADIUS_METERS
        )

    def _get_destination(self, payload: RouteRequest) -> LocationRecord:
        if payload.destination_id is not None:
            location = LOCATIONS.get(payload.destination_id)
            if location is None:
                raise DestinationNotFoundError(
                    f"Destination id {payload.destination_id} not found"
                )
            return location

        assert payload.destination_name is not None
        location = self._find_destination_by_name(payload.destination_name)
        if location is None:
            raise DestinationNotFoundError(
                f"Destination '{payload.destination_name}' not found"
            )
        return location

    @staticmethod
    def _find_destination_by_name(destination_name: str) -> LocationRecord | None:
        candidate_phrases = _candidate_phrases(destination_name)
        best_location: LocationRecord | None = None
        best_score = 0.0

        for location in LOCATIONS.values():
            names = (location["name"], *location["aliases"])
            for phrase in candidate_phrases:
                normalized = _normalize_name(phrase)
                compact_normalized = _compact_name(phrase)
                digits = _digits_only(phrase)
                for name in names:
                    candidate_normalized = _normalize_name(name)
                    candidate_compact = _compact_name(name)
                    candidate_digits = _digits_only(name)
                    score = _score_destination_match(
                        normalized,
                        compact_normalized,
                        digits,
                        candidate_normalized,
                        candidate_compact,
                        candidate_digits,
                    )
                    if score > best_score:
                        best_score = score
                        best_location = location

        return best_location if best_score >= 0.78 else None


def build_default_routing_service() -> RoutingService:
    """Build the service with the configured provider (Google Routes by default)."""
    settings = get_settings()
    provider = _build_provider(settings)
    return RoutingService(provider=provider, settings=settings)


def _build_provider(settings: Settings) -> RoutingProvider:
    if settings.routing_provider == "google_routes":
        return GoogleRoutesProvider(
            api_key=settings.google_maps_api_key,
            language_code=settings.google_routes_language_code,
            units=settings.google_routes_units,
        )

    if settings.routing_provider == "mock":
        return MockRoutingProvider()

    raise ValueError(f"Unsupported routing provider: {settings.routing_provider}")


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


def _candidate_phrases(name: str) -> list[str]:
    base = _normalize_name(name)
    stripped = _strip_navigation_prefix(base)
    after_to = base.split(" to ")[-1].strip() if " to " in base else ""
    candidates = [base, stripped, after_to]
    return [candidate for candidate in dict.fromkeys(candidate for candidate in candidates if candidate)]


def _strip_navigation_prefix(text: str) -> str:
    prefixes = (
        "take me to ",
        "i am going to ",
        "i'm going to ",
        "go to ",
        "navigate to ",
        "bring me to ",
        "head to ",
        "walk me to ",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _compact_name(name: str) -> str:
    return _normalize_name(name).replace(" ", "")


def _digits_only(name: str) -> str:
    return "".join(ch for ch in name if ch.isdigit())


def _score_destination_match(
    normalized_input: str,
    compact_input: str,
    input_digits: str,
    candidate_normalized: str,
    candidate_compact: str,
    candidate_digits: str,
) -> float:
    if not normalized_input or not candidate_normalized:
        return 0.0

    if normalized_input == candidate_normalized:
        return 1.0
    if compact_input == candidate_compact:
        return 0.98
    if input_digits and input_digits == candidate_digits:
        return 0.97
    if input_digits and input_digits in candidate_compact:
        return 0.94
    if compact_input and (
        compact_input in candidate_compact or candidate_compact in compact_input
    ):
        return 0.92

    ratio = SequenceMatcher(None, compact_input, candidate_compact).ratio()
    input_tokens = set(normalized_input.split())
    candidate_tokens = set(candidate_normalized.split())
    if input_tokens and candidate_tokens:
        overlap = len(input_tokens & candidate_tokens) / len(input_tokens | candidate_tokens)
        ratio = max(ratio, overlap)

    return ratio
