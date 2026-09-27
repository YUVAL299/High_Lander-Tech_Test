"""Orchestrates a game: sessions, players, routing and broadcasting events.

Concurrency model: every read-modify-write on a session happens under the
store's per-session lock, so concurrent position updates from several players
are applied one at a time and the first to reach the goal wins deterministically.
Slow routing calls are made *outside* the lock so one player's reroute never
blocks another player's movement.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from app.domain.geo import LatLng, haversine_m, polyline_length_m, trim_polyline_from
from app.domain.models import (
    GameSession,
    Player,
    RouteSource,
    SessionStatus,
    new_id,
    utcnow,
)
from app.domain.rules import ReroutePolicy, RerouteReason
from app.schemas import (
    JoinedSession,
    Position,
    RouteView,
    SessionView,
    message,
    player_view,
)
from app.services.goal_generator import GoalGenerator
from app.services.hub import ConnectionHub
from app.services.routing_service import RoutingService, straight_line_route
from app.store.base import SessionStore

log = logging.getLogger(__name__)


class SessionNotFound(Exception):
    pass


class PlayerNotFound(Exception):
    pass


class SessionFinished(Exception):
    pass


class GameService:
    def __init__(
        self,
        store: SessionStore,
        hub: ConnectionHub,
        routing: RoutingService,
        goals: GoalGenerator,
        policy: ReroutePolicy,
        reach_radius_m: float,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._store = store
        self._hub = hub
        self._routing = routing
        self._goals = goals
        self._policy = policy
        self._reach_radius_m = reach_radius_m
        self._clock = clock
        self._routing_in_flight: set[tuple[str, str]] = set()

    # ---- queries ----------------------------------------------------------------

    async def get_view(self, session_id: str) -> SessionView:
        return self._view(await self._require_session(session_id))

    # ---- commands ---------------------------------------------------------------

    async def create_session(self, position: LatLng, name: str | None) -> JoinedSession:
        goal = await self._goals.generate(position)
        session = GameSession(id=new_id(), goal=goal, reach_radius_m=self._reach_radius_m)
        player = await self._new_player(session, position, name)
        session.add_player(player)
        await self._store.save(session)
        log.info(
            "session created",
            extra={"session_id": session.id, "goal_distance_m": haversine_m(position, goal)},
        )
        return JoinedSession(player_id=player.id, session=self._view(session))

    async def join_session(
        self, session_id: str, position: LatLng, name: str | None
    ) -> JoinedSession:
        session = await self._require_session(session_id)
        # Route outside the lock (slow I/O); the goal never changes, so it stays valid.
        player = await self._new_player(session, position, name)
        async with self._store.lock(session_id):
            session = await self._require_session(session_id)
            if session.status is not SessionStatus.ACTIVE:
                raise SessionFinished(session_id)
            session.add_player(player)
            await self._store.save(session)
            view = self._view(session)
        joined = next(p for p in view.players if p.id == player.id)
        await self._hub.broadcast(session_id, message("player.joined", joined))
        return JoinedSession(player_id=player.id, session=view)

    async def update_position(self, session_id: str, player_id: str, position: LatLng) -> None:
        now = self._clock()
        events: list[dict] = []
        reroute: RerouteReason | None = None

        async with self._store.lock(session_id):
            session = await self._require_session(session_id)
            player = self._require_player(session, player_id)
            won = session.move_player(player_id, position, now)

            if session.status is SessionStatus.ACTIVE:
                reroute = self._policy.reason_to_reroute(player.route, position, now)
                if (
                    reroute is None
                    and player.route
                    and player.route.source is RouteSource.STRAIGHT_LINE
                ):
                    # Keep the fallback line anchored to the player; keep its timestamp
                    # so the policy still knows when to retry the real router.
                    fresh = straight_line_route(position, session.goal)
                    player.route = replace(fresh, computed_at=player.route.computed_at)
                key = (session_id, player_id)
                if reroute and key in self._routing_in_flight:
                    reroute = None
                if reroute:
                    self._routing_in_flight.add(key)

            await self._store.save(session)
            events.append(
                message(
                    "player.moved",
                    {
                        "player_id": player_id,
                        "position": Position.from_domain(position).model_dump(),
                        "distance_to_goal_m": round(session.distance_to_goal_m(player_id), 1),
                        "remaining_route_m": round(self._remaining_route_m(player), 1),
                    },
                )
            )
            if won:
                elapsed = (now - session.created_at).total_seconds()
                log.info("goal reached", extra={"session_id": session_id, "player_id": player_id})
                events.append(
                    message(
                        "goal.reached",
                        {
                            "player_id": player_id,
                            "name": player.name,
                            "elapsed_s": round(elapsed, 1),
                            "session": self._view(session).model_dump(mode="json"),
                        },
                    )
                )
            goal = session.goal

        for event in events:
            await self._hub.broadcast(session_id, event)

        if reroute:
            await self._reroute(session_id, player_id, position, goal, reroute)

    async def touch(self, session_id: str, player_id: str) -> None:
        """Keep-alive from an idle but connected player."""
        async with self._store.lock(session_id):
            session = await self._require_session(session_id)
            self._require_player(session, player_id).last_seen_at = self._clock()

    async def broadcast_presence(self, session_id: str, player_id: str, connected: bool) -> None:
        await self._hub.broadcast(
            session_id,
            message("player.presence", {"player_id": player_id, "connected": connected}),
        )

    async def purge_idle(self, older_than: datetime) -> int:
        return await self._store.purge_idle(older_than)

    # ---- internals ----------------------------------------------------------------

    async def _reroute(
        self,
        session_id: str,
        player_id: str,
        origin: LatLng,
        goal: LatLng,
        reason: RerouteReason,
    ) -> None:
        key = (session_id, player_id)
        try:
            route = await self._routing.route(origin, goal)
        finally:
            self._routing_in_flight.discard(key)

        async with self._store.lock(session_id):
            session = await self._store.get(session_id)
            if session is None or player_id not in session.players:
                return
            if session.status is not SessionStatus.ACTIVE:
                return
            player = session.players[player_id]
            player.route = route
            if reason is not RerouteReason.NO_ROUTE:
                player.reroute_count += 1
            await self._store.save(session)
            count = player.reroute_count

        log.info(
            "route updated",
            extra={"session_id": session_id, "player_id": player_id, "reason": reason.value},
        )
        await self._hub.broadcast(
            session_id,
            message(
                "route.updated",
                {
                    "player_id": player_id,
                    "reason": reason.value,
                    "reroute_count": count,
                    "route": RouteView.from_domain(route).model_dump(mode="json"),
                },
            ),
        )

    async def _new_player(self, session: GameSession, position: LatLng, name: str | None) -> Player:
        route = await self._routing.route(position, session.goal)
        return Player(
            id=new_id(),
            name=name or f"Player {len(session.players) + 1}",
            position=position,
            route=route,
            last_seen_at=self._clock(),
        )

    @staticmethod
    def _remaining_route_m(player: Player) -> float:
        route = player.route
        if route is None or route.source is RouteSource.STRAIGHT_LINE:
            return route.distance_m if route else 0.0
        return polyline_length_m(trim_polyline_from(player.position, route.points))

    def _view(self, session: GameSession) -> SessionView:
        return SessionView(
            id=session.id,
            status=session.status,
            goal=Position.from_domain(session.goal),
            reach_radius_m=session.reach_radius_m,
            winner_id=session.winner_id,
            created_at=session.created_at,
            finished_at=session.finished_at,
            players=[
                player_view(session, p, self._hub.is_connected(session.id, p.id))
                for p in session.players.values()
            ],
        )

    async def _require_session(self, session_id: str) -> GameSession:
        session = await self._store.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session

    @staticmethod
    def _require_player(session: GameSession, player_id: str) -> Player:
        player = session.players.get(player_id)
        if player is None:
            raise PlayerNotFound(player_id)
        return player
