import httpx
import pytest
import respx

from app.domain.geo import LatLng
from app.domain.models import RouteSource
from app.routing.base import RoutingError
from app.routing.osrm import OsrmProvider

BASE = "http://osrm.test"
A = LatLng(32.08, 34.78)
B = LatLng(32.09, 34.79)
ROUTE_URL = f"{BASE}/route/v1/foot/34.780000,32.080000;34.790000,32.090000"

ROUTE_OK = {
    "code": "Ok",
    "routes": [
        {
            "distance": 1523.4,
            "duration": 1100.2,
            "geometry": {"type": "LineString", "coordinates": [[34.78, 32.08], [34.79, 32.09]]},
        }
    ],
}


@pytest.fixture
def provider():
    return OsrmProvider(BASE, profile="foot", retries=1)


@respx.mock
async def test_route_parses_geometry_in_latlng_order(provider):
    respx.get(ROUTE_URL).mock(return_value=httpx.Response(200, json=ROUTE_OK))
    route = await provider.route(A, B)
    assert route.points == [A, B]
    assert route.distance_m == pytest.approx(1523.4)
    assert route.source is RouteSource.OSRM


@respx.mock
async def test_route_requests_full_geojson_geometry(provider):
    call = respx.get(ROUTE_URL).mock(return_value=httpx.Response(200, json=ROUTE_OK))
    await provider.route(A, B)
    params = call.calls.last.request.url.params
    assert params["overview"] == "full"
    assert params["geometries"] == "geojson"


@respx.mock
async def test_no_route_is_not_retried(provider):
    call = respx.get(ROUTE_URL).mock(
        return_value=httpx.Response(400, json={"code": "NoRoute", "message": "Impossible route"})
    )
    with pytest.raises(RoutingError, match="NoRoute"):
        await provider.route(A, B)
    assert call.call_count == 1


@respx.mock
async def test_server_error_is_retried_then_succeeds(provider):
    respx.get(ROUTE_URL).mock(side_effect=[httpx.Response(502), httpx.Response(200, json=ROUTE_OK)])
    route = await provider.route(A, B)
    assert route.distance_m == pytest.approx(1523.4)


@respx.mock
async def test_network_error_raises_routing_error_after_retries(provider):
    call = respx.get(ROUTE_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(RoutingError, match="unavailable"):
        await provider.route(A, B)
    assert call.call_count == 2


@respx.mock
async def test_malformed_response_raises_routing_error(provider):
    respx.get(ROUTE_URL).mock(return_value=httpx.Response(200, json={"code": "Ok"}))
    with pytest.raises(RoutingError):
        await provider.route(A, B)


@respx.mock
async def test_snap_returns_nearest_waypoint(provider):
    respx.get(f"{BASE}/nearest/v1/foot/34.780000,32.080000").mock(
        return_value=httpx.Response(
            200, json={"code": "Ok", "waypoints": [{"location": [34.7801, 32.0802]}]}
        )
    )
    assert await provider.snap(A) == LatLng(32.0802, 34.7801)
