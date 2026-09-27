"""Small, dependency-free geodesy helpers.

Distances use the haversine formula on a spherical Earth, which is accurate to
well under a metre at the scales this game works at (a few kilometres).
Point-to-polyline math uses a local equirectangular projection centred on the
query point, which is plenty accurate for the same reason.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True, slots=True)
class LatLng:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"latitude out of range: {self.lat}")
        if not (-180.0 <= self.lng <= 180.0):
            raise ValueError(f"longitude out of range: {self.lng}")


def haversine_m(a: LatLng, b: LatLng) -> float:
    """Great-circle distance between two points, in metres."""
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = phi2 - phi1
    dlmb = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def destination_point(origin: LatLng, bearing_deg: float, distance_m: float) -> LatLng:
    """The point reached by travelling ``distance_m`` from ``origin`` on ``bearing_deg``."""
    delta = distance_m / EARTH_RADIUS_M
    theta = math.radians(bearing_deg)
    phi1 = math.radians(origin.lat)
    lmb1 = math.radians(origin.lng)

    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lmb2 = lmb1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    lng = (math.degrees(lmb2) + 540.0) % 360.0 - 180.0
    return LatLng(math.degrees(phi2), lng)


def random_point_in_ring(
    origin: LatLng, min_radius_m: float, max_radius_m: float, rng: random.Random | None = None
) -> LatLng:
    """A point uniformly distributed (by area) in the ring between the two radii."""
    if not 0 <= min_radius_m <= max_radius_m:
        raise ValueError("expected 0 <= min_radius_m <= max_radius_m")
    rng = rng or random.Random()
    # Sampling r = sqrt(U) over the squared radii gives a uniform area density;
    # sampling r uniformly would bunch points up near the centre.
    r = math.sqrt(rng.uniform(min_radius_m**2, max_radius_m**2))
    return destination_point(origin, rng.uniform(0.0, 360.0), r)


def _to_local_xy(origin: LatLng, p: LatLng) -> tuple[float, float]:
    """Project ``p`` to metres on a plane tangent at ``origin``."""
    x = math.radians(p.lng - origin.lng) * EARTH_RADIUS_M * math.cos(math.radians(origin.lat))
    y = math.radians(p.lat - origin.lat) * EARTH_RADIUS_M
    return x, y


@dataclass(frozen=True, slots=True)
class PolylineProjection:
    """Where a point lands when snapped onto a polyline."""

    distance_m: float  # perpendicular distance from the point to the polyline
    segment_index: int  # index i of the closest segment (points[i] -> points[i + 1])
    fraction: float  # 0..1 position along that segment
    point: LatLng  # the snapped point on the polyline


def project_onto_polyline(p: LatLng, points: list[LatLng]) -> PolylineProjection:
    """Closest point on the polyline to ``p``."""
    if not points:
        raise ValueError("polyline must have at least one point")
    if len(points) == 1:
        return PolylineProjection(haversine_m(p, points[0]), 0, 0.0, points[0])

    best: PolylineProjection | None = None
    for i in range(len(points) - 1):
        ax, ay = _to_local_xy(p, points[i])
        bx, by = _to_local_xy(p, points[i + 1])
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        # Point p is the origin (0, 0) of the local plane.
        t = 0.0 if seg_len_sq == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg_len_sq))
        cx, cy = ax + t * dx, ay + t * dy
        dist = math.hypot(cx, cy)
        if best is None or dist < best.distance_m:
            a, b = points[i], points[i + 1]
            snapped = LatLng(a.lat + t * (b.lat - a.lat), a.lng + t * (b.lng - a.lng))
            best = PolylineProjection(dist, i, t, snapped)
    assert best is not None
    return best


def polyline_length_m(points: list[LatLng]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(points, points[1:], strict=False))


def trim_polyline_from(p: LatLng, points: list[LatLng]) -> list[LatLng]:
    """The remainder of the polyline, starting from where ``p`` projects onto it."""
    if len(points) < 2:
        return list(points)
    proj = project_onto_polyline(p, points)
    return [proj.point, *points[proj.segment_index + 1 :]]
