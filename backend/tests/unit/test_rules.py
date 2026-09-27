from datetime import timedelta

from app.domain.geo import LatLng, destination_point
from app.domain.models import Route, RouteSource, utcnow
from app.domain.rules import ReroutePolicy, RerouteReason

START = LatLng(32.0853, 34.7818)
END = destination_point(START, 90, 300)
POLICY = ReroutePolicy(off_route_threshold_m=25, min_interval_s=3, fallback_retry_interval_s=15)


def _route(source=RouteSource.OSRM, age_s=10.0):
    return Route(
        points=[START, END],
        distance_m=300,
        duration_s=200,
        source=source,
        computed_at=utcnow() - timedelta(seconds=age_s),
    )


def test_no_route_needs_one():
    assert POLICY.reason_to_reroute(None, START, utcnow()) is RerouteReason.NO_ROUTE


def test_on_route_does_not_reroute():
    on_route = destination_point(START, 90, 100)
    assert POLICY.reason_to_reroute(_route(), on_route, utcnow()) is None


def test_small_drift_is_tolerated():
    drift = destination_point(destination_point(START, 90, 100), 0, 15)
    assert POLICY.reason_to_reroute(_route(), drift, utcnow()) is None


def test_off_route_triggers_reroute():
    off = destination_point(destination_point(START, 90, 100), 0, 40)
    assert POLICY.reason_to_reroute(_route(), off, utcnow()) is RerouteReason.OFF_ROUTE


def test_reroute_is_throttled():
    off = destination_point(destination_point(START, 90, 100), 0, 40)
    assert POLICY.reason_to_reroute(_route(age_s=1), off, utcnow()) is None


def test_straight_line_route_is_retried_periodically():
    route = _route(RouteSource.STRAIGHT_LINE, age_s=16)
    assert POLICY.reason_to_reroute(route, START, utcnow()) is RerouteReason.RETRY_ROUTING


def test_straight_line_route_is_not_retried_too_soon_even_off_route():
    off = destination_point(START, 0, 100)
    route = _route(RouteSource.STRAIGHT_LINE, age_s=5)
    assert POLICY.reason_to_reroute(route, off, utcnow()) is None
