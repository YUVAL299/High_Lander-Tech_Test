"""Test doubles shared across the suite."""

from __future__ import annotations

from app.domain.geo import LatLng, polyline_length_m
from app.domain.models import Route, RouteSource
from app.routing.base import RoutingError


class FakeRoutingProvider:
    """Routes via a fixed midpoint "corner" so routes aren't just straight lines."""

    def __init__(self, *, fail: bool = False, snap_offset: tuple[float, float] = (0, 0)) -> None:
        self.fail = fail
        self.snap_offset = snap_offset
        self.route_calls: list[tuple[LatLng, LatLng]] = []
        self.snap_calls: list[LatLng] = []

    async def route(self, origin: LatLng, destination: LatLng) -> Route:
        self.route_calls.append((origin, destination))
        if self.fail:
            raise RoutingError("fake failure")
        corner = LatLng(origin.lat, destination.lng)
        points = [origin, corner, destination]
        dist = polyline_length_m(points)
        return Route(points=points, distance_m=dist, duration_s=dist / 1.4, source=RouteSource.OSRM)

    async def snap(self, point: LatLng) -> LatLng:
        self.snap_calls.append(point)
        if self.fail:
            raise RoutingError("fake failure")
        return LatLng(point.lat + self.snap_offset[0], point.lng + self.snap_offset[1])

    async def aclose(self) -> None:
        pass
