import random

from app.domain.geo import LatLng, haversine_m
from app.domain.models import RouteSource
from app.services.goal_generator import GoalConfig, GoalGenerator
from app.services.routing_service import RoutingService
from tests.fakes import FakeRoutingProvider

START = LatLng(32.0853, 34.7818)
CFG = GoalConfig(min_distance_m=200, max_distance_m=800, max_attempts=5)


async def test_route_uses_provider_when_healthy():
    route = await RoutingService(FakeRoutingProvider()).route(START, LatLng(32.09, 34.79))
    assert route.source is RouteSource.OSRM
    assert len(route.points) == 3


async def test_route_falls_back_to_straight_line():
    goal = LatLng(32.09, 34.79)
    route = await RoutingService(FakeRoutingProvider(fail=True)).route(START, goal)
    assert route.source is RouteSource.STRAIGHT_LINE
    assert route.points == [START, goal]
    assert route.distance_m == haversine_m(START, goal)


async def test_goal_is_snapped_and_within_ring():
    provider = FakeRoutingProvider()
    gen = GoalGenerator(RoutingService(provider), CFG, random.Random(1))
    for _ in range(50):
        goal = await gen.generate(START)
        assert 200 <= haversine_m(START, goal) <= 800
    assert provider.snap_calls


async def test_goal_retries_when_snap_lands_outside_ring():
    # Snapping moves every point ~3.3 km north, so no attempt can land in the ring.
    provider = FakeRoutingProvider(snap_offset=(0.03, 0))
    gen = GoalGenerator(RoutingService(provider), CFG, random.Random(1))
    goal = await gen.generate(START)
    assert len(provider.snap_calls) == CFG.max_attempts
    assert 200 <= haversine_m(START, goal) <= 800  # falls back to the raw sample


async def test_goal_still_generated_when_routing_is_down():
    provider = FakeRoutingProvider(fail=True)
    gen = GoalGenerator(RoutingService(provider), CFG, random.Random(1))
    goal = await gen.generate(START)
    assert 200 <= haversine_m(START, goal) <= 800
    assert len(provider.snap_calls) == 1
