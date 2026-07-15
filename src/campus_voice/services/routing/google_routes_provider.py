"""Google Routes API provider for walking directions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from campus_voice.models.schemas import Coordinate, DestinationSummary, RouteStep
from campus_voice.services.routing.base import RoutingProvider
from campus_voice.services.routing.geo import decode_polyline


class GoogleRoutesError(RuntimeError):
    """Raised when Google Routes API rejects or fails a request."""


@dataclass(slots=True)
class RouteBuildResult:
    steps: list[RouteStep]
    duration_seconds: int
    route_preview: list[Coordinate] | None = None


@dataclass(slots=True)
class GoogleRoutesProvider(RoutingProvider):
    """Fetch walking directions from Google Routes API."""

    api_key: str
    language_code: str = "en-US"
    units: str = "METRIC"
    timeout_seconds: float = 10.0

    _endpoint: str = "https://routes.googleapis.com/directions/v2:computeRoutes"
    _field_mask: str = (
        "routes.duration,"
        "routes.distanceMeters,"
        "routes.polyline.encodedPolyline,"
        "routes.legs.steps.navigationInstruction,"
        "routes.legs.steps.distanceMeters,"
        "routes.legs.steps.polyline,"
        "routes.legs.steps.startLocation,"
        "routes.legs.steps.endLocation"
    )

    def build_route(
        self,
        origin: Coordinate,
        destination: DestinationSummary,
        destination_coordinate: Coordinate,
    ) -> RouteBuildResult:
        if not self.api_key.strip():
            raise GoogleRoutesError("Google Maps API key is not configured")

        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin.latitude,
                        "longitude": origin.longitude,
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination_coordinate.latitude,
                        "longitude": destination_coordinate.longitude,
                    }
                }
            },
            "travelMode": "DRIVE",
            "computeAlternativeRoutes": False,
            "languageCode": self.language_code,
            "units": self.units,
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                self._endpoint,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": self._field_mask,
                },
                json=payload,
            )

        if response.status_code >= 400:
            raise GoogleRoutesError(self._extract_error_message(response))

        data = response.json()
        routes = data.get("routes") or []
        if not routes:
            raise GoogleRoutesError("Google Routes API returned no routes")

        route = routes[0]
        route_steps = self._extract_steps(route)
        if not route_steps:
            raise GoogleRoutesError("Google Routes API returned no steps")

        duration_seconds = self._extract_duration_seconds(route)

        # Decode the full route polyline to get the actual high-resolution path
        route_preview = None
        encoded = route.get("polyline", {}).get("encodedPolyline")
        if isinstance(encoded, str) and encoded:
            route_preview = decode_polyline(encoded)

        return RouteBuildResult(
            steps=route_steps,
            duration_seconds=duration_seconds,
            route_preview=route_preview
        )

    @staticmethod
    def _extract_duration_seconds(route: dict[str, Any]) -> int:
        raw = route.get("duration")
        if isinstance(raw, str) and raw.endswith("s"):
            try:
                return round(float(raw[:-1]))
            except ValueError:
                pass
        return 0

    def _extract_steps(self, route: dict[str, Any]) -> list[RouteStep]:
        steps: list[RouteStep] = []
        legs = route.get("legs") or []

        for leg_index, leg in enumerate(legs, start=1):
            leg_steps = leg.get("steps") or []
            for step_index, step in enumerate(leg_steps, start=1):
                instruction = self._extract_instruction(step)
                distance_meters = float(step.get("distanceMeters") or 0)
                start_location = step.get("startLocation") or {}
                end_location = step.get("endLocation") or {}
                start_latlng = start_location.get("latLng") or end_location.get("latLng") or {}
                end_latlng = end_location.get("latLng") or start_latlng

                if not instruction.strip():
                    continue

                steps.append(
                    RouteStep(
                        step_number=len(steps) + 1,
                        instruction=instruction,
                        distance_meters=distance_meters,
                        heading_degrees=None,
                        waypoint=Coordinate(
                            latitude=float(end_latlng.get("latitude") or start_latlng.get("latitude") or 0),
                            longitude=float(end_latlng.get("longitude") or start_latlng.get("longitude") or 0),
                        ),
                    )
                )

            if leg_index == 1 and not leg_steps and route.get("polyline"):
                encoded = route.get("polyline", {}).get("encodedPolyline")
                if isinstance(encoded, str) and encoded:
                    decoded = decode_polyline(encoded)
                    if decoded:
                        steps.append(
                            RouteStep(
                                step_number=1,
                                instruction=f"Continue to {decoded[-1].latitude:.5f}, {decoded[-1].longitude:.5f}",
                                distance_meters=float(route.get("distanceMeters") or 0),
                                heading_degrees=None,
                                waypoint=decoded[-1],
                            )
                        )

        return steps

    @staticmethod
    def _extract_instruction(step: dict[str, Any]) -> str:
        instruction = step.get("navigationInstruction") or {}
        text = instruction.get("instructions")
        if isinstance(text, str) and text.strip():
            return text.strip()

        maneuver = instruction.get("maneuver")
        if isinstance(maneuver, str) and maneuver.strip():
            return maneuver.replace("_", " ").title()

        return ""

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                if isinstance(payload.get("error"), dict):
                    error = payload["error"]
                    message = error.get("message")
                    if isinstance(message, str) and message.strip():
                        return message.strip()
                message = payload.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
        except Exception:
            pass

        return f"Google Routes API request failed ({response.status_code})"