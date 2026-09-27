"""End-to-end smoke test against a running stack (through nginx, like a browser).

Plays a real two-player race over REST + WebSockets and checks that routing,
rerouting and "first to the goal wins" all work.

    python e2e/smoke_test.py [http://localhost:8080]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx
import websockets

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
WS_BASE = BASE.replace("http", "ws", 1)
START = {"lat": 32.0853, "lng": 34.7818}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  ✓ {message}")


async def wait_until_up(client: httpx.AsyncClient, timeout_s: float = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if (await client.get("/api/config")).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError(f"{BASE} did not come up within {timeout_s}s")
        await asyncio.sleep(1)


async def next_of(ws, type_: str, timeout_s: float = 10) -> dict:
    """Read messages until one of the given type arrives."""
    async with asyncio.timeout(timeout_s):
        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == type_:
                return msg["payload"]


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        print(f"Smoke testing {BASE}")
        await wait_until_up(client)
        check((await client.get("/healthz")).status_code == 200, "frontend is healthy")

        created = (await client.post("/api/sessions", json={"position": START, "name": "Alice"})).json()
        session = created["session"]
        sid, alice = session["id"], created["player_id"]
        goal = session["goal"]
        route = session["players"][0]["route"]
        check(route["source"] == "osrm" and len(route["points"]) >= 2, "game starts with a route")

        joined = await client.post(f"/api/sessions/{sid}/players", json={"position": START, "name": "Bob"})
        check(joined.status_code == 201, "a second player can join")
        bob = joined.json()["player_id"]

        async with (
            websockets.connect(f"{WS_BASE}/ws/sessions/{sid}?player_id={alice}") as ws_a,
            websockets.connect(f"{WS_BASE}/ws/sessions/{sid}?player_id={bob}") as ws_b,
        ):
            state = await next_of(ws_a, "session.state")
            check(len(state["players"]) == 2, "WebSocket delivers the session state")
            await next_of(ws_b, "session.state")

            # Alice walks far off her route: she should get a new one.
            off_route = {"lat": START["lat"] - 0.01, "lng": START["lng"] - 0.01}
            await ws_a.send(json.dumps({"type": "position.update", "payload": off_route}))
            moved = await next_of(ws_b, "player.moved")
            check(moved["player_id"] == alice, "other players see you move")
            rerouted = await next_of(ws_a, "route.updated")
            check(rerouted["reason"] == "off_route", "walking off the route triggers a reroute")

            # Both arrive at the same moment: exactly one winner.
            update = json.dumps({"type": "position.update", "payload": goal})
            await asyncio.gather(ws_a.send(update), ws_b.send(update))
            won_a = await next_of(ws_a, "goal.reached")
            won_b = await next_of(ws_b, "goal.reached")
            check(won_a["player_id"] == won_b["player_id"], "everyone agrees on the same winner")

        final = (await client.get(f"/api/sessions/{sid}")).json()
        check(final["status"] == "finished", "the game is finished")
        winners = [p for p in final["players"] if p["reached_goal_at"]]
        check(len(winners) == 1 and final["winner_id"] == winners[0]["id"], "only one player won")

        late = await client.post(f"/api/sessions/{sid}/players", json={"position": START})
        check(late.status_code == 409, "nobody can join a finished game")

    print("All smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
