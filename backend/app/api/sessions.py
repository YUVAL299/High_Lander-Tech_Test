from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_game
from app.schemas import CreateSessionRequest, SessionCreated, SessionView
from app.services.game_service import GameService, SessionNotFound

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

Game = Annotated[GameService, Depends(get_game)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionRequest, game: Game) -> SessionCreated:
    """Start a new game around the given position: places a goal and routes to it."""
    return await game.create_session(body.position.to_domain(), body.name)


@router.get("/{session_id}")
async def get_session(session_id: str, game: Game) -> SessionView:
    try:
        return await game.get_view(session_id)
    except SessionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found") from None
