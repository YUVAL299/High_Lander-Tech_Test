"""Rules deciding when a player's route should be recomputed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.geo import LatLng, project_onto_polyline
from app.domain.models import Route, RouteSource


class RerouteReason(StrEnum):
    NO_ROUTE = "no_route"
    OFF_ROUTE = "off_route"
    RETRY_ROUTING = "retry_routing"  # last route was a straight-line fallback


@dataclass(frozen=True, slots=True)
class ReroutePolicy:
    """Recompute only when it matters, and never more often than ``min_interval_s``.

    Recomputing on every GPS tick would hammer the routing engine for no visible
    benefit, so while the player stays near their route we just trim the part
    they've already walked (see ``geo.trim_polyline_from``).
    """

    off_route_threshold_m: float = 25.0
    min_interval_s: float = 3.0
    fallback_retry_interval_s: float = 15.0

    def reason_to_reroute(
        self, route: Route | None, position: LatLng, now: datetime
    ) -> RerouteReason | None:
        if route is None:
            return RerouteReason.NO_ROUTE

        elapsed = (now - route.computed_at).total_seconds()
        if elapsed < self.min_interval_s:
            return None

        if route.source is RouteSource.STRAIGHT_LINE:
            # A straight line has no "off route"; just try the real router again
            # now and then in case it has recovered.
            if elapsed >= self.fallback_retry_interval_s:
                return RerouteReason.RETRY_ROUTING
            return None

        if project_onto_polyline(position, route.points).distance_m > self.off_route_threshold_m:
            return RerouteReason.OFF_ROUTE
        return None
