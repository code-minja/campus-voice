"""Routing provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from campus_voice.models.schemas import Coordinate, DestinationSummary, RouteStep


class RoutingProvider(ABC):
    """Abstract contract for navigation route providers."""

    @abstractmethod
    def build_route(
        self,
        origin: Coordinate,
        destination: DestinationSummary,
        destination_coordinate: Coordinate,
    ):
        """Build route steps (and duration, where available) from origin to destination."""
        raise NotImplementedError