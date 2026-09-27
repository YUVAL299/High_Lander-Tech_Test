"""Real-time channel for one player in one session.

Protocol (JSON text frames, ``{"type": ..., "payload": ...}``):

client -> server
  position.update  {lat, lng}
  ping

server -> client
  session.state    full SessionView (sent on connect)
  player.moved     {player_id, position, distance_to_goal_m, remaining_route_m}
  route.updated    {player_id, reason, reroute_count, route}
  goal.reached     {player_id, name, elapsed_s, session}
  player.joined    PlayerView
  player.presence  {player_id, connected}
  pong
  error            {message}
"""

import contextlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.api.deps import get_game_ws, get_hub_ws
from app.schemas import PingMsg, PositionUpdateMsg, client_message_adapter, message
from app.services.game_service import GameService, PlayerNotFound, SessionNotFound
from app.services.hub import ConnectionHub

log = logging.getLogger(__name__)
router = APIRouter()

# Close codes in the 4000-4999 range are application-defined.
CLOSE_NOT_FOUND = 4404
CLOSE_REPLACED = 4409


@router.websocket("/ws/sessions/{session_id}")
async def session_socket(
    websocket: WebSocket,
    session_id: str,
    player_id: str,
    game: Annotated[GameService, Depends(get_game_ws)],
    hub: Annotated[ConnectionHub, Depends(get_hub_ws)],
) -> None:
    await websocket.accept()
    try:
        view = await game.get_view(session_id)
    except SessionNotFound:
        await websocket.close(CLOSE_NOT_FOUND, "session not found")
        return
    if all(p.id != player_id for p in view.players):
        await websocket.close(CLOSE_NOT_FOUND, "player not in session")
        return

    replaced = hub.connect(session_id, player_id, websocket)
    if replaced is not None:
        # Same player opened the game somewhere else; the newest tab wins.
        with contextlib.suppress(Exception):
            await replaced.close(CLOSE_REPLACED, "connected from another tab")  # type: ignore[attr-defined]
    await game.broadcast_presence(session_id, player_id, connected=True)
    await websocket.send_json(message("session.state", await game.get_view(session_id)))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = client_message_adapter.validate_json(raw)
            except ValidationError as exc:
                await websocket.send_json(message("error", {"message": _describe(exc)}))
                continue

            if isinstance(msg, PositionUpdateMsg):
                await game.update_position(session_id, player_id, msg.payload.to_domain())
            elif isinstance(msg, PingMsg):
                await game.touch(session_id, player_id)
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except (SessionNotFound, PlayerNotFound):
        await websocket.close(CLOSE_NOT_FOUND, "session expired")
    finally:
        if hub.disconnect(session_id, player_id, websocket):
            await game.broadcast_presence(session_id, player_id, connected=False)


def _describe(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first.get("loc", ()))
    return f"invalid message: {where} {first.get('msg', '')}".strip()
