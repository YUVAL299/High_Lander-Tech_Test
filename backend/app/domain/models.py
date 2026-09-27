"""Core game entities and the session state machine.

Everything here is synchronous and free of I/O so it can be unit tested in
isolation; the service layer is responsible for persistence, routing calls and
broadcasting the events these methods return.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.geo import LatLng, haversine_m


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class SessionStatus(StrEnum):
    ACTIVE = "active"
    FINISHED = "finished"


class RouteSource(StrEnum):
    OSRM = "osrm"
    STRAIGHT_LINE = "straight_line"  # fallback when the routing engine is unavailable


@dataclass(slots=True)
class Route:
    points: list[LatLng]
    distance_m: float
    duration_s: float
    source: RouteSource
    computed_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Player:
    id: str
    name: str
    position: LatLng
    last_seen_at: datetime = field(default_factory=utcnow)
    route: Route | None = None
    reroute_count: int = 0
    reached_goal_at: datetime | None = None


@dataclass(slots=True)
class GameSession:
    id: str
    goal: LatLng
    reach_radius_m: float
    status: SessionStatus = SessionStatus.ACTIVE
    players: dict[str, Player] = field(default_factory=dict)
    winner_id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None
    # Bumped on every mutation; used for optimistic concurrency in shared stores.
    version: int = 0

    def add_player(self, player: Player) -> None:
        self.players[player.id] = player
        self.version += 1

    def remove_player(self, player_id: str) -> None:
        if self.players.pop(player_id, None) is not None:
            self.version += 1

    def distance_to_goal_m(self, player_id: str) -> float:
        return haversine_m(self.players[player_id].position, self.goal)

    def move_player(self, player_id: str, position: LatLng, now: datetime | None = None) -> bool:
        """Record a new position. Returns True if this move wins the game.

        The first player to come within ``reach_radius_m`` of the goal wins and
        the session finishes; later arrivals (or moves after the game ended)
        never change the winner.
        """
        now = now or utcnow()
        player = self.players[player_id]
        player.position = position
        player.last_seen_at = now
        self.version += 1

        if self.status is not SessionStatus.ACTIVE:
            return False
        if haversine_m(position, self.goal) > self.reach_radius_m:
            return False

        player.reached_goal_at = now
        self.winner_id = player_id
        self.status = SessionStatus.FINISHED
        self.finished_at = now
        return True
