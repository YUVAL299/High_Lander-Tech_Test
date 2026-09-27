"""The routing abstraction the rest of the app depends on."""

from __future__ import annotations

from typing import Protocol

from app.domain.geo import LatLng
from app.domain.models import Route


class RoutingError(Exception):
    """The routing engine couldn't produce a result (unreachable, no route, bad reply)."""


class RoutingProvider(Protocol):
    async def route(self, origin: LatLng, destination: LatLng) -> Route:
        """Shortest permissible route between two points. Raises RoutingError."""
        ...

    async def snap(self, point: LatLng) -> LatLng:
        """Nearest point on the routable network. Raises RoutingError."""
        ...

    async def aclose(self) -> None: ...
