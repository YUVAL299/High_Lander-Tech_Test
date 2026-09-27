"""Wire format for REST responses and WebSocket messages.

Coordinates are sent as ``{"lat": .., "lng": ..}`` objects, except route
geometry which uses compact ``[lat, lng]`` pairs (what Leaflet expects).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from app.domain.geo import LatLng
from app.domain.models import GameSession, Player, Route, RouteSource, SessionStatus


class Position(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    def to_domain(self) -> LatLng:
        return LatLng(self.lat, self.lng)

    @classmethod
    def from_domain(cls, p: LatLng) -> Position:
        return cls(lat=p.lat, lng=p.lng)


PlayerName = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[\w .\-']+$")]


class CreateSessionRequest(BaseModel):
    position: Position
    name: PlayerName | None = None


class RouteView(BaseModel):
    points: list[tuple[float, float]]
    distance_m: float
    duration_s: float
    source: RouteSource

    @classmethod
    def from_domain(cls, r: Route) -> RouteView:
        return cls(
            points=[(p.lat, p.lng) for p in r.points],
            distance_m=round(r.distance_m, 1),
            duration_s=round(r.duration_s, 1),
            source=r.source,
        )


class PlayerView(BaseModel):
    id: str
    name: str
    position: Position
    distance_to_goal_m: float
    remaining_route_m: float
    reroute_count: int
    reached_goal_at: datetime | None
    route: RouteView | None


class SessionView(BaseModel):
    id: str
    status: SessionStatus
    goal: Position
    reach_radius_m: float
    winner_id: str | None
    created_at: datetime
    finished_at: datetime | None
    players: list[PlayerView]


class SessionCreated(BaseModel):
    """The new session plus *your* player id (used to open the WebSocket)."""

    player_id: str
    session: SessionView


def player_view(session: GameSession, player: Player) -> PlayerView:
    return PlayerView(
        id=player.id,
        name=player.name,
        position=Position.from_domain(player.position),
        distance_to_goal_m=round(session.distance_to_goal_m(player.id), 1),
        remaining_route_m=round(session.remaining_route_m(player.id), 1),
        reroute_count=player.reroute_count,
        reached_goal_at=player.reached_goal_at,
        route=RouteView.from_domain(player.route) if player.route else None,
    )


# ---- WebSocket: client -> server ------------------------------------------------


class PositionUpdateMsg(BaseModel):
    type: Literal["position.update"]
    payload: Position


class PingMsg(BaseModel):
    type: Literal["ping"]


ClientMessage = Annotated[PositionUpdateMsg | PingMsg, Field(discriminator="type")]
client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


# ---- WebSocket: server -> client ------------------------------------------------


def message(type_: str, payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
    body = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return {"type": type_, "payload": body}
