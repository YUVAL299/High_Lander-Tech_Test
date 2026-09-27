from datetime import timedelta

from app.domain.geo import LatLng, destination_point
from app.domain.models import GameSession, Player, SessionStatus, utcnow

START = LatLng(32.0853, 34.7818)
GOAL = destination_point(START, 45, 400)


def _session(*player_ids):
    s = GameSession(id="s1", goal=GOAL, reach_radius_m=20)
    for pid in player_ids:
        s.add_player(Player(id=pid, name=pid, position=START))
    return s


def test_move_far_from_goal_does_not_win():
    s = _session("alice")
    assert s.move_player("alice", destination_point(START, 45, 100)) is False
    assert s.status is SessionStatus.ACTIVE
    assert s.winner_id is None


def test_move_within_radius_wins_and_finishes():
    s = _session("alice")
    assert s.move_player("alice", destination_point(GOAL, 180, 10)) is True
    assert s.status is SessionStatus.FINISHED
    assert s.winner_id == "alice"
    assert s.players["alice"].reached_goal_at is not None


def test_just_outside_radius_does_not_win():
    s = _session("alice")
    assert s.move_player("alice", destination_point(GOAL, 180, 20.5)) is False


def test_first_player_to_arrive_keeps_the_win():
    s = _session("alice", "bob")
    t0 = utcnow()
    assert s.move_player("bob", GOAL, now=t0) is True
    assert s.move_player("alice", GOAL, now=t0 + timedelta(milliseconds=1)) is False
    assert s.winner_id == "bob"
    assert s.players["alice"].reached_goal_at is None


def test_positions_still_tracked_after_finish():
    s = _session("alice", "bob")
    s.move_player("bob", GOAL)
    elsewhere = destination_point(START, 0, 5)
    s.move_player("alice", elsewhere)
    assert s.players["alice"].position == elsewhere


def test_version_increments_on_mutation():
    s = _session("alice")
    v = s.version
    s.move_player("alice", START)
    assert s.version == v + 1


def test_distance_to_goal():
    s = _session("alice")
    assert round(s.distance_to_goal_m("alice")) == 400


def test_remaining_route_follows_the_route_polyline():
    from app.domain.models import Route, RouteSource

    s = _session("alice")
    corner = destination_point(START, 90, 300)
    end = destination_point(corner, 0, 200)
    s.players["alice"].route = Route([START, corner, end], 500, 360, RouteSource.OSRM)
    s.move_player("alice", destination_point(START, 90, 100))
    assert round(s.remaining_route_m("alice")) == 400


def test_remaining_route_without_real_route_is_direct_distance():
    s = _session("alice")
    assert s.remaining_route_m("alice") == s.distance_to_goal_m("alice")


def test_remaining_route_includes_getting_back_onto_the_route():
    from app.domain.models import Route, RouteSource

    s = _session("alice")
    end = destination_point(START, 90, 300)
    s.players["alice"].route = Route([START, end], 300, 214, RouteSource.OSRM)
    # 100 m along the route, then 40 m off to the side of it
    s.move_player("alice", destination_point(destination_point(START, 90, 100), 0, 40))
    assert round(s.remaining_route_m("alice")) == 240
