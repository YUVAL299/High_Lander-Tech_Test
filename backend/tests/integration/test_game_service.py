import asyncio
import random

import pytest

from app.domain.geo import LatLng, destination_point, haversine_m
from app.domain.models import Player, RouteSource, SessionStatus, utcnow
from app.domain.rules import ReroutePolicy
from app.services.game_service import GameService, SessionNotFound
from app.services.goal_generator import GoalConfig, GoalGenerator
from app.services.hub import ConnectionHub
from app.services.routing_service import RoutingService
from app.store.memory import InMemorySessionStore
from tests.fakes import FakeRoutingProvider, ManualClock, RecordingConnection

START = LatLng(32.0853, 34.7818)


@pytest.fixture
def provider():
    return FakeRoutingProvider()


@pytest.fixture
def clock():
    return ManualClock(utcnow())


@pytest.fixture
def hub():
    return ConnectionHub()


@pytest.fixture
def store():
    return InMemorySessionStore()


@pytest.fixture
def game(provider, clock, hub, store):
    routing = RoutingService(provider)
    return GameService(
        store=store,
        hub=hub,
        routing=routing,
        goals=GoalGenerator(routing, GoalConfig(200, 800), random.Random(3)),
        policy=ReroutePolicy(off_route_threshold_m=25, min_interval_s=3),
        reach_radius_m=20,
        clock=clock,
    )


async def _start(game, hub):
    created = await game.create_session(START, "Alice")
    conn = RecordingConnection()
    hub.connect(created.session.id, created.player_id, conn)
    return created.session.id, created.player_id, conn


def _goal(view):
    return LatLng(view.goal.lat, view.goal.lng)


def _away_from_goal(goal):
    """A point behind the start, so it's far from any route towards the goal."""
    return LatLng(START.lat + (START.lat - goal.lat) / 2, START.lng + (START.lng - goal.lng) / 2)


async def test_create_session_places_goal_and_route(game):
    created = await game.create_session(START, None)
    s = created.session
    assert s.status is SessionStatus.ACTIVE
    assert 200 <= haversine_m(START, _goal(s)) <= 800
    me = s.players[0]
    assert me.id == created.player_id
    assert me.name == "Player 1"
    assert me.route is not None and me.route.source is RouteSource.OSRM


async def test_moving_along_route_broadcasts_position_without_reroute(game, hub, clock, provider):
    sid, pid, conn = await _start(game, hub)
    calls_before = len(provider.route_calls)
    clock.advance(10)
    await game.update_position(sid, pid, START)

    moved = conn.of_type("player.moved")
    assert len(moved) == 1
    assert moved[0]["payload"]["player_id"] == pid
    assert moved[0]["payload"]["remaining_route_m"] > 0
    assert conn.of_type("route.updated") == []
    assert len(provider.route_calls) == calls_before


async def test_walking_off_route_triggers_reroute(game, hub, clock):
    sid, pid, conn = await _start(game, hub)
    clock.advance(10)
    off = _away_from_goal(_goal(await game.get_view(sid)))
    await game.update_position(sid, pid, off)

    [update] = conn.of_type("route.updated")
    assert update["payload"]["reason"] == "off_route"
    assert update["payload"]["reroute_count"] == 1
    first_point = update["payload"]["route"]["points"][0]
    assert first_point == pytest.approx([off.lat, off.lng])


async def test_reroute_is_throttled(game, hub, clock):
    sid, pid, conn = await _start(game, hub)
    clock.advance(1)  # less than min_interval_s
    await game.update_position(sid, pid, _away_from_goal(_goal(await game.get_view(sid))))
    assert conn.of_type("route.updated") == []


async def test_reaching_goal_finishes_game(game, hub, clock, provider):
    sid, pid, conn = await _start(game, hub)
    goal = _goal(await game.get_view(sid))
    clock.advance(42)
    await game.update_position(sid, pid, destination_point(goal, 0, 5))

    [reached] = conn.of_type("goal.reached")
    assert reached["payload"]["player_id"] == pid
    assert reached["payload"]["elapsed_s"] == pytest.approx(42)
    view = await game.get_view(sid)
    assert view.status is SessionStatus.FINISHED
    assert view.winner_id == pid

    # No more rerouting once the game is over.
    calls = len(provider.route_calls)
    clock.advance(10)
    await game.update_position(sid, pid, destination_point(START, 225, 500))
    assert len(provider.route_calls) == calls


async def test_session_with_several_players_has_exactly_one_winner(game, hub, store):
    """Multiplayer readiness: the service already handles a session holding
    several players (added directly here, as there's no join endpoint yet)."""
    sid, alice, conn = await _start(game, hub)
    session = await store.get(sid)
    for pid in ("bob", "carol"):
        session.add_player(Player(id=pid, name=pid, position=START))
    goal = session.goal

    await asyncio.gather(*(game.update_position(sid, p, goal) for p in (alice, "bob", "carol")))

    reached = conn.of_type("goal.reached")
    assert len(reached) == 1
    view = await game.get_view(sid)
    assert view.winner_id == reached[0]["payload"]["player_id"]
    assert sum(p.reached_goal_at is not None for p in view.players) == 1


async def test_unknown_session(game):
    with pytest.raises(SessionNotFound):
        await game.get_view("nope")


async def test_routing_outage_uses_straight_line_that_follows_player(game, hub, clock, provider):
    provider.fail = True
    sid, pid, _ = await _start(game, hub)
    view = await game.get_view(sid)
    assert view.players[0].route.source is RouteSource.STRAIGHT_LINE

    clock.advance(5)
    moved_to = destination_point(START, 90, 30)
    await game.update_position(sid, pid, moved_to)
    route = (await game.get_view(sid)).players[0].route
    assert route.points[0] == pytest.approx((moved_to.lat, moved_to.lng))


async def test_router_recovery_replaces_straight_line(game, hub, clock, provider):
    provider.fail = True
    sid, pid, conn = await _start(game, hub)
    provider.fail = False
    clock.advance(16)  # past fallback_retry_interval_s
    await game.update_position(sid, pid, START)

    [update] = conn.of_type("route.updated")
    assert update["payload"]["reason"] == "retry_routing"
    assert update["payload"]["route"]["source"] == "osrm"


async def test_purge_idle_removes_stale_sessions(game, hub, clock):
    sid, _, _ = await _start(game, hub)
    clock.advance(7200)
    assert await game.purge_idle(clock.now) == 1
    with pytest.raises(SessionNotFound):
        await game.get_view(sid)
