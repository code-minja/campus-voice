"""Small geospatial helpers for campus routing."""

from __future__ import annotations

from math import asin, atan2, cos, degrees, radians, sin, sqrt

from campus_voice.models.schemas import Coordinate

EARTH_RADIUS_METERS = 6_371_000


def distance_meters(a: Coordinate, b: Coordinate) -> float:
    """Return haversine distance between two coordinates."""
    lat1 = radians(a.latitude)
    lat2 = radians(b.latitude)
    d_lat = radians(b.latitude - a.latitude)
    d_lon = radians(b.longitude - a.longitude)

    value = (
        sin(d_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * asin(sqrt(value))


def bearing_degrees(a: Coordinate, b: Coordinate) -> float:
    """Return initial bearing from coordinate a to b."""
    lat1 = radians(a.latitude)
    lat2 = radians(b.latitude)
    d_lon = radians(b.longitude - a.longitude)

    y = sin(d_lon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(d_lon)
    return (degrees(atan2(y, x)) + 360) % 360


def cardinal_direction(bearing: float) -> str:
    """Convert bearing degrees into a human-friendly cardinal direction."""
    directions = (
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    )
    index = round(bearing / 45) % len(directions)
    return directions[index]


def interpolate(a: Coordinate, b: Coordinate, ratio: float) -> Coordinate:
    """Return a point between coordinates a and b."""
    return Coordinate(
        latitude=a.latitude + ((b.latitude - a.latitude) * ratio),
        longitude=a.longitude + ((b.longitude - a.longitude) * ratio),
    )


def decode_polyline(encoded: str) -> list[Coordinate]:
    """Decode an encoded polyline string into coordinates."""
    points: list[Coordinate] = []
    index = 0
    latitude = 0
    longitude = 0

    while index < len(encoded):
        shift = 0
        result = 0
        while True:
            if index >= len(encoded):
                return points
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break

        delta_lat = ~(result >> 1) if result & 1 else result >> 1

        shift = 0
        result = 0
        while True:
            if index >= len(encoded):
                return points
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break

        delta_lng = ~(result >> 1) if result & 1 else result >> 1
        latitude += delta_lat
        longitude += delta_lng
        points.append(
            Coordinate(
                latitude=latitude / 1e5,
                longitude=longitude / 1e5,
            )
        )

    return points
