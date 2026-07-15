"""Dijkstra's shortest path algorithm implementation for walkway routing."""

from __future__ import annotations

import heapq
from typing import Any

from campus_voice.models.schemas import Coordinate
from campus_voice.services.routing.geo import distance_meters


def find_shortest_path(
    start: str,
    end: str,
    nodes: dict[str, Any],
    edges: dict[str, list[str]],
) -> list[str] | None:
    """
    Find the shortest path of node IDs from start to end using Dijkstra's algorithm.
    Returns list of node IDs, or None if no path exists.
    """
    if start not in nodes or end not in nodes:
        return None

    # Priority queue: (cumulative_distance_meters, current_node, path_so_far)
    queue: list[tuple[float, str, list[str]]] = [(0.0, start, [start])]
    visited: set[str] = set()

    while queue:
        dist, current, path = heapq.heappop(queue)

        if current in visited:
            continue
        visited.add(current)

        if current == end:
            return path

        for neighbor in edges.get(current, []):
            if neighbor in visited:
                continue

            current_coord = Coordinate(
                latitude=nodes[current]["latitude"],
                longitude=nodes[current]["longitude"],
            )
            neighbor_coord = Coordinate(
                latitude=nodes[neighbor]["latitude"],
                longitude=nodes[neighbor]["longitude"],
            )
            weight = distance_meters(current_coord, neighbor_coord)

            heapq.heappush(queue, (dist + weight, neighbor, path + [neighbor]))

    return None
