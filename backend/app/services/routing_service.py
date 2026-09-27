"""Routing with graceful degradation.

If the routing engine is down the game should stay playable, so we fall back
to a straight line to the goal. The ReroutePolicy periodically retries the real
router while a fallback route is in use.
"""

from __future__ import annotations

import logging

from app.domain.geo import LatLng, haversine_m
from app.domain.models import Route, RouteSource
from app.routing.base import RoutingError, RoutingProvider

log = logging.getLogger(__name__)

WALKING_SPEED_MPS = 1.4


def straight_line_route(origin: LatLng, destination: LatLng) -> Route:
    distance = haversine_m(origin, destination)
    return Route(
        points=[origin, destination],
        distance_m=distance,
        duration_s=distance / WALKING_SPEED_MPS,
        source=RouteSource.STRAIGHT_LINE,
    )


class RoutingService:
    def __init__(self, provider: RoutingProvider) -> None:
        self._provider = provider

    async def route(self, origin: LatLng, destination: LatLng) -> Route:
        try:
            return await self._provider.route(origin, destination)
        except RoutingError as exc:
            log.warning("routing failed, using straight-line fallback: %s", exc)
            return straight_line_route(origin, destination)

    async def snap(self, point: LatLng) -> LatLng | None:
        try:
            return await self._provider.snap(point)
        except RoutingError as exc:
            log.warning("snap failed: %s", exc)
            return None
