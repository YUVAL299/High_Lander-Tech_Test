from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from app.domain.models import GameSession


class InMemorySessionStore:
    """Process-local store. Session objects are shared, not copied, so callers
    must hold ``lock(session_id)`` while mutating them."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get(self, session_id: str) -> GameSession | None:
        return self._sessions.get(session_id)

    async def save(self, session: GameSession) -> None:
        self._sessions[session.id] = session

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)

    @asynccontextmanager
    async def lock(self, session_id: str) -> AsyncIterator[None]:
        async with self._locks[session_id]:
            yield

    async def purge_idle(self, older_than: datetime) -> int:
        idle = [
            sid
            for sid, s in self._sessions.items()
            if max((p.last_seen_at for p in s.players.values()), default=s.created_at) < older_than
        ]
        for sid in idle:
            await self.delete(sid)
        return len(idle)

    def __len__(self) -> int:
        return len(self._sessions)
