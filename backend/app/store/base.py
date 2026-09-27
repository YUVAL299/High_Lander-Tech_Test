"""Session persistence abstraction.

The in-memory implementation is enough for a single backend process. To run
several replicas, implement this protocol on Redis (sessions as JSON,
``lock`` as a Redis lock / WATCH on ``GameSession.version``); nothing above
this layer needs to change.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from app.domain.models import GameSession


class SessionStore(Protocol):
    async def get(self, session_id: str) -> GameSession | None: ...

    async def save(self, session: GameSession) -> None: ...

    async def delete(self, session_id: str) -> None: ...

    def lock(self, session_id: str) -> AbstractAsyncContextManager[None]:
        """Serialises read-modify-write cycles on one session."""
        ...

    async def purge_idle(self, older_than: datetime) -> int:
        """Delete sessions with no activity since ``older_than``; returns how many."""
        ...
