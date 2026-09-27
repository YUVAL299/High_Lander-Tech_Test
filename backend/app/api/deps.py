from fastapi import Request, WebSocket

from app.services.game_service import GameService
from app.services.hub import ConnectionHub


def get_game(request: Request) -> GameService:
    return request.app.state.game


def get_game_ws(websocket: WebSocket) -> GameService:
    return websocket.app.state.game


def get_hub_ws(websocket: WebSocket) -> ConnectionHub:
    return websocket.app.state.hub
