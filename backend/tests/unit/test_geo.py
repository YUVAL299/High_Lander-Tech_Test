import math
import random

import pytest

from app.domain.geo import (
    LatLng,
    destination_point,
    haversine_m,
    polyline_length_m,
    project_onto_polyline,
    random_point_in_ring,
    trim_polyline_from,
)

TEL_AVIV = LatLng(32.0853, 34.7818)


def test_haversine_zero_for_same_point():
    assert haversine_m(TEL_AVIV, TEL_AVIV) == 0


def test_haversine_one_degree_of_latitude_is_about_111km():
    assert haversine_m(LatLng(0, 0), LatLng(1, 0)) == pytest.approx(111_195, rel=1e-3)


def test_haversine_known_city_pair():
    jerusalem = LatLng(31.7683, 35.2137)
    assert haversine_m(TEL_AVIV, jerusalem) == pytest.approx(54_000, rel=0.02)


@pytest.mark.parametrize("bearing", [0, 45, 90, 180, 270, 333])
@pytest.mark.parametrize("distance", [1, 50, 500, 5000])
def test_destination_point_round_trips_distance(bearing, distance):
    dest = destination_point(TEL_AVIV, bearing, distance)
    assert haversine_m(TEL_AVIV, dest) == pytest.approx(distance, rel=1e-6)


def test_destination_point_north_increases_latitude():
    dest = destination_point(TEL_AVIV, 0, 1000)
    assert dest.lat > TEL_AVIV.lat
    assert dest.lng == pytest.approx(TEL_AVIV.lng)


def test_latlng_rejects_out_of_range():
    with pytest.raises(ValueError):
        LatLng(91, 0)
    with pytest.raises(ValueError):
        LatLng(0, 181)


def test_random_point_in_ring_stays_within_bounds():
    rng = random.Random(42)
    for _ in range(500):
        p = random_point_in_ring(TEL_AVIV, 200, 800, rng)
        assert 200 - 1e-6 <= haversine_m(TEL_AVIV, p) <= 800 + 1e-6


def test_random_point_in_ring_is_uniform_by_area():
    # With r = sqrt(U), half the points should fall outside the radius that
    # splits the disk into two equal areas (R / sqrt(2)).
    rng = random.Random(7)
    radius = 1000
    half_area_radius = radius / math.sqrt(2)
    samples = [random_point_in_ring(TEL_AVIV, 0, radius, rng) for _ in range(4000)]
    outside = sum(haversine_m(TEL_AVIV, p) > half_area_radius for p in samples)
    assert outside / 4000 == pytest.approx(0.5, abs=0.03)


def test_random_point_in_ring_rejects_bad_radii():
    with pytest.raises(ValueError):
        random_point_in_ring(TEL_AVIV, 500, 100)


def _line(*bearing_distance_pairs):
    """Build a polyline by walking from TEL_AVIV along (bearing, distance) legs."""
    pts = [TEL_AVIV]
    for bearing, dist in bearing_distance_pairs:
        pts.append(destination_point(pts[-1], bearing, dist))
    return pts


def test_projection_of_point_on_line_is_zero_distance():
    line = _line((90, 100))
    mid = destination_point(TEL_AVIV, 90, 40)
    proj = project_onto_polyline(mid, line)
    assert proj.distance_m == pytest.approx(0, abs=0.05)
    assert proj.fraction == pytest.approx(0.4, abs=1e-3)


def test_projection_perpendicular_offset():
    line = _line((90, 100))
    off = destination_point(destination_point(TEL_AVIV, 90, 50), 0, 30)
    proj = project_onto_polyline(off, line)
    assert proj.distance_m == pytest.approx(30, rel=1e-2)
    assert proj.segment_index == 0


def test_projection_beyond_end_clamps_to_endpoint():
    line = _line((90, 100))
    beyond = destination_point(TEL_AVIV, 90, 150)
    proj = project_onto_polyline(beyond, line)
    assert proj.fraction == 1.0
    assert proj.distance_m == pytest.approx(50, rel=1e-2)


def test_projection_picks_closest_segment():
    line = _line((90, 100), (0, 100))  # east then north: an L shape
    near_second_leg = destination_point(destination_point(line[1], 0, 60), 90, 5)
    proj = project_onto_polyline(near_second_leg, line)
    assert proj.segment_index == 1
    assert proj.distance_m == pytest.approx(5, rel=0.05)


def test_trim_polyline_drops_walked_part():
    line = _line((90, 100), (0, 100))
    walker = destination_point(line[1], 0, 30)
    remaining = trim_polyline_from(walker, line)
    assert len(remaining) == 2
    assert polyline_length_m(remaining) == pytest.approx(70, rel=1e-2)


def test_polyline_length():
    assert polyline_length_m(_line((90, 100), (0, 50))) == pytest.approx(150, rel=1e-6)
