from __future__ import annotations

from typing import Any

from campus_voice.models.schemas import Coordinate, DestinationSummary
from campus_voice.services.routing.google_routes_provider import GoogleRoutesProvider


def test_requests_walking_routes_with_google_units(monkeypatch) -> None:
    request_payload: dict[str, Any] = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {
                "routes": [
                    {
                        "duration": "30s",
                        "legs": [
                            {
                                "steps": [
                                    {
                                        "navigationInstruction": {
                                            "instructions": "Walk east"
                                        },
                                        "distanceMeters": 25,
                                        "startLocation": {
                                            "latLng": {
                                                "latitude": 7.4818,
                                                "longitude": 5.7419,
                                            }
                                        },
                                        "endLocation": {
                                            "latLng": {
                                                "latitude": 7.4820,
                                                "longitude": 5.7421,
                                            }
                                        },
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def post(self, url: str, headers: dict[str, str], json: dict[str, Any]):
            request_payload.update(json)
            return FakeResponse()

    monkeypatch.setattr(
        "campus_voice.services.routing.google_routes_provider.httpx.Client",
        FakeClient,
    )

    provider = GoogleRoutesProvider(api_key="test-key", units="metric")
    result = provider.build_route(
        origin=Coordinate(latitude=7.4818, longitude=5.7419),
        destination=DestinationSummary(id=1, name="ETF 750"),
        destination_coordinate=Coordinate(latitude=7.4820, longitude=5.7421),
    )

    assert request_payload["travelMode"] == "WALK"
    assert request_payload["units"] == "METRIC"
    assert result.steps[0].instruction == "Walk east"
