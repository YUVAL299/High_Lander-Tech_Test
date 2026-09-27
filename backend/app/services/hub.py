"""Tracks live WebSocket connections and fans events out to them.

This in-process hub only reaches clients connected to *this* backend replica.
For horizontal scaling, publish events to a Redis channel per session and have
every replica's hub forward them to its local sockets.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Connection(Protocol):
    async def send_json(self, data: Any) -> None: ...


class ConnectionHub:
    def __init__(self) -> None:
        self._rooms: defaultdict[str, dict[str, Connection]] = defaultdict(dict)

    def connect(self, session_id: str, player_id: str, conn: Connection) -> Connection | None:
        """Register a connection; returns the one it replaced (e.g. a stale tab)."""
        previous = self._rooms[session_id].get(player_id)
        self._rooms[session_id][player_id] = conn
        return previous

    def disconnect(self, session_id: str, player_id: str, conn: Connection) -> bool:
        """Unregister, unless the player already reconnected on a newer socket."""
        room = self._rooms.get(session_id)
        if not room or room.get(player_id) is not conn:
            return False
        del room[player_id]
        if not room:
            del self._rooms[session_id]
        return True

    def is_connected(self, session_id: str, player_id: str) -> bool:
        return player_id in self._rooms.get(session_id, {})

    async def send(self, session_id: str, player_id: str, message: dict[str, Any]) -> None:
        conn = self._rooms.get(session_id, {}).get(player_id)
        if conn is not None:
            await self._safe_send(conn, message)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        conns = list(self._rooms.get(session_id, {}).values())
        await asyncio.gather(*(self._safe_send(c, message) for c in conns))

    @staticmethod
    async def _safe_send(conn: Connection, message: dict[str, Any]) -> None:
        # One broken socket must not stop the broadcast to everyone else;
        # its own receive loop will notice and clean it up.
        try:
            await conn.send_json(message)
        except Exception as exc:  # noqa: BLE001
            log.debug("dropping message to closed connection: %s", exc)
