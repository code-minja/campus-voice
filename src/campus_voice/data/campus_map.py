"""Read mapped AAUA places from the supplied KMZ file."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


_KML_NAMESPACE = "{http://www.opengis.net/kml/2.2}"
_MAP_FILENAME = "AAUA Campus Map.kmz"


@dataclass(frozen=True, slots=True)
class CampusMapPoint:
    name: str
    latitude: float
    longitude: float


def _map_file_path() -> Path:
    source_tree_path = Path(__file__).resolve().parents[3] / _MAP_FILENAME
    packaged_path = Path(__file__).with_name(_MAP_FILENAME)
    for path in (source_tree_path, packaged_path):
        if path.is_file():
            return path
    raise FileNotFoundError(f"Required campus map file not found: {_MAP_FILENAME}")


@lru_cache(maxsize=1)
def load_campus_map_points() -> tuple[CampusMapPoint, ...]:
    """Return unique named Point placemarks with their unrounded KML coordinates."""
    map_path = _map_file_path()
    with ZipFile(map_path) as archive:
        try:
            kml_content = archive.read("doc.kml")
        except KeyError as exc:
            raise ValueError(f"{_MAP_FILENAME} does not contain doc.kml") from exc

    root = ElementTree.fromstring(kml_content)
    points: list[CampusMapPoint] = []
    seen_coordinates: set[tuple[float, float]] = set()

    for placemark in root.iter(f"{_KML_NAMESPACE}Placemark"):
        coordinate_element = placemark.find(
            f"{_KML_NAMESPACE}Point/{_KML_NAMESPACE}coordinates"
        )
        if coordinate_element is None or not coordinate_element.text:
            continue

        name_element = placemark.find(f"{_KML_NAMESPACE}name")
        name = (
            name_element.text.strip()
            if name_element is not None and name_element.text
            else ""
        )
        if not name:
            raise ValueError(f"Unnamed point found in {_MAP_FILENAME}")

        coordinate_values = coordinate_element.text.strip().split()[0].split(",")
        if len(coordinate_values) < 2:
            raise ValueError(f"Invalid coordinate for {name!r} in {_MAP_FILENAME}")

        longitude, latitude = map(float, coordinate_values[:2])
        if (
            not isfinite(latitude)
            or not isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError(f"Out-of-range coordinate for {name!r} in {_MAP_FILENAME}")

        coordinate = (latitude, longitude)
        if coordinate in seen_coordinates:
            continue
        seen_coordinates.add(coordinate)
        points.append(
            CampusMapPoint(
                name=name,
                latitude=latitude,
                longitude=longitude,
            )
        )

    if not points:
        raise ValueError(f"No named Point placemarks found in {_MAP_FILENAME}")
    return tuple(points)
