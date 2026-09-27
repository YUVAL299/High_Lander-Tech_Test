"""FastAPI application factory and dependency wiring."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, sessions, ws
from app.config import Settings, get_settings
from app.domain.models import utcnow
from app.domain.rules import ReroutePolicy
from app.logging_config import configure_logging
from app.routing.base import RoutingProvider
from app.routing.osrm import OsrmProvider
from app.services.game_service import GameService
from app.services.goal_generator import GoalConfig, GoalGenerator
from app.services.hub import ConnectionHub
from app.services.routing_service import RoutingService
from app.store.memory import InMemorySessionStore

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, routing_provider: RoutingProvider | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        provider = routing_provider or OsrmProvider(
            settings.osrm_url,
            profile=settings.osrm_profile,
            timeout_s=settings.osrm_timeout_s,
            retries=settings.osrm_retries,
        )
        routing = RoutingService(provider)
        hub = ConnectionHub()
        app.state.hub = hub
        app.state.game = GameService(
            store=InMemorySessionStore(),
            hub=hub,
            routing=routing,
            goals=GoalGenerator(
                routing,
                GoalConfig(settings.goal_min_distance_m, settings.goal_max_distance_m),
            ),
            policy=ReroutePolicy(
                off_route_threshold_m=settings.reroute_off_route_m,
                min_interval_s=settings.reroute_min_interval_s,
            ),
            reach_radius_m=settings.goal_reach_radius_m,
        )
        sweeper = asyncio.create_task(_sweep_idle_sessions(app.state.game, settings))
        log.info("backend started", extra={"osrm_url": settings.osrm_url})
        try:
            yield
        finally:
            sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sweeper
            await provider.aclose()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(ws.router)

    @app.get("/api/config", tags=["config"])
    async def public_config() -> dict[str, float]:
        """Game parameters the client displays (goal radius etc.)."""
        return {
            "goal_reach_radius_m": settings.goal_reach_radius_m,
            "goal_min_distance_m": settings.goal_min_distance_m,
            "goal_max_distance_m": settings.goal_max_distance_m,
            "reroute_off_route_m": settings.reroute_off_route_m,
        }

    return app


async def _sweep_idle_sessions(game: GameService, settings: Settings) -> None:
    while True:
        await asyncio.sleep(settings.session_sweep_interval_s)
        removed = await game.purge_idle(utcnow() - timedelta(seconds=settings.session_ttl_s))
        if removed:
            log.info("purged idle sessions", extra={"count": removed})


app = create_app()
