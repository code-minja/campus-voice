"""
/v1/locations — canonical campus location catalog.
"""

from __future__ import annotations

from fastapi import APIRouter

from campus_voice.data.locations import LOCATIONS
from campus_voice.models.schemas import (
    CampusLocation,
    CampusLocationsResponse,
    CampusRouteCondition,
)

router = APIRouter(tags=["Locations"])


@router.get(
    "/locations",
    response_model=CampusLocationsResponse,
    summary="List canonical campus locations",
)
def locations() -> CampusLocationsResponse:
    return CampusLocationsResponse(
        locations=[
            CampusLocation(
                id=location["id"],
                name=location["name"],
                latitude=location["latitude"],
                longitude=location["longitude"],
                aliases=list(location["aliases"]),
                route_conditions=[
                    CampusRouteCondition(
                        code=condition["code"],
                        label=condition["label"],
                        description=condition["description"],
                        severity=condition["severity"],
                        tags=list(condition["tags"]),
                    )
                    for condition in location["route_conditions"]
                ],
            )
            for location in LOCATIONS.values()
        ]
    )
