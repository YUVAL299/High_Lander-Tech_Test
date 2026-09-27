"""Places the goal somewhere reachable near the player."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from app.domain.geo import LatLng, haversine_m, random_point_in_ring
from app.services.routing_service import RoutingService

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GoalConfig:
    min_distance_m: float = 200.0
    max_distance_m: float = 800.0
    max_attempts: int = 5


class GoalGenerator:
    def __init__(
        self, routing: RoutingService, config: GoalConfig, rng: random.Random | None = None
    ) -> None:
        self._routing = routing
        self._config = config
        self._rng = rng or random.Random()

    async def generate(self, origin: LatLng) -> LatLng:
        """A random point in the configured ring, snapped onto a walkable road.

        Snapping can move the point (e.g. a sample in the middle of a lake or a
        park), so the snapped point is re-checked against the ring. If routing
        is unavailable we accept the raw sample so the game can still start.
        """
        cfg = self._config
        sample = origin
        for attempt in range(1, cfg.max_attempts + 1):
            sample = random_point_in_ring(origin, cfg.min_distance_m, cfg.max_distance_m, self._rng)
            snapped = await self._routing.snap(sample)
            if snapped is None:
                log.info("goal: routing unavailable, using unsnapped point")
                return sample
            if cfg.min_distance_m <= haversine_m(origin, snapped) <= cfg.max_distance_m:
                return snapped
            log.debug("goal: snapped point outside ring on attempt %d, retrying", attempt)
        log.info("goal: no snapped point within ring after %d attempts", cfg.max_attempts)
        return sample
