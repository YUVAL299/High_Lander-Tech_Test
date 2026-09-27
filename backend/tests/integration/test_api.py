import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from tests.fakes import FakeRoutingProvider

POS = {"lat": 32.0853, "lng": 34.7818}


@pytest.fixture
def client():
    app = create_app(Settings(reroute_min_interval_s=0), routing_provider=FakeRoutingProvider())
    with TestClient(app) as c:
        yield c


def _create(client, name="Alice"):
    resp = client.post("/api/sessions", json={"position": POS, "name": name})
    assert resp.status_code == 201
    return resp.json()


def test_create_and_fetch_session(client):
    body = _create(client)
    sid = body["session"]["id"]
    fetched = client.get(f"/api/sessions/{sid}").json()
    assert fetched["id"] == sid
    assert fetched["players"][0]["name"] == "Alice"
    assert fetched["players"][0]["route"]["points"]


def test_rejects_invalid_coordinates(client):
    resp = client.post("/api/sessions", json={"position": {"lat": 95, "lng": 0}})
    assert resp.status_code == 422


def test_rejects_odd_player_names(client):
    resp = client.post("/api/sessions", json={"position": POS, "name": "<script>"})
    assert resp.status_code == 422


def test_unknown_session_is_404(client):
    assert client.get("/api/sessions/missing").status_code == 404


def test_public_config(client):
    assert client.get("/api/config").json()["goal_reach_radius_m"] == 20


def test_websocket_full_game(client):
    body = _create(client)
    sid, pid = body["session"]["id"], body["player_id"]
    goal = body["session"]["goal"]

    with client.websocket_connect(f"/ws/sessions/{sid}?player_id={pid}") as ws:
        state = ws.receive_json()
        assert state["type"] == "session.state"
        assert state["payload"]["players"][0]["id"] == pid

        ws.send_json({"type": "position.update", "payload": {"lat": 32.0, "lng": 34.7}})
        assert ws.receive_json()["type"] == "player.moved"
        assert ws.receive_json()["type"] == "route.updated"  # far off route

        ws.send_json({"type": "position.update", "payload": goal})
        assert ws.receive_json()["type"] == "player.moved"
        reached = ws.receive_json()
        assert reached["type"] == "goal.reached"
        assert reached["payload"]["player_id"] == pid

        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_reports_bad_messages_without_disconnecting(client):
    body = _create(client)
    sid, pid = body["session"]["id"], body["player_id"]
    with client.websocket_connect(f"/ws/sessions/{sid}?player_id={pid}") as ws:
        assert ws.receive_json()["type"] == "session.state"
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "position.update", "payload": {"lat": 200, "lng": 0}})
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_websocket_rejects_unknown_player(client):
    sid = _create(client)["session"]["id"]
    with client.websocket_connect(f"/ws/sessions/{sid}?player_id=intruder") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4404
