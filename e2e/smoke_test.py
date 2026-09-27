"""End-to-end smoke test against a running stack (through nginx, like a browser).

Plays a real game over REST + WebSockets and checks that routing, rerouting,
goal detection and the end of the game all work.

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

        created = (await client.post("/api/sessions", json={"position": START})).json()
        session = created["session"]
        sid, player = session["id"], created["player_id"]
        goal = session["goal"]
        route = session["players"][0]["route"]
        check(route["source"] == "osrm" and len(route["points"]) >= 2, "game starts with a route")

        async with websockets.connect(f"{WS_BASE}/ws/sessions/{sid}?player_id={player}") as ws:
            state = await next_of(ws, "session.state")
            check(state["id"] == sid and state["status"] == "active", "WebSocket delivers the game state")

            # Walk far off the route: a new route should arrive.
            off_route = {"lat": START["lat"] - 0.01, "lng": START["lng"] - 0.01}
            await ws.send(json.dumps({"type": "position.update", "payload": off_route}))
            moved = await next_of(ws, "player.moved")
            check(moved["remaining_route_m"] > 0, "position updates are acknowledged")
            rerouted = await next_of(ws, "route.updated")
            check(rerouted["reason"] == "off_route", "walking off the route triggers a reroute")
            first = rerouted["route"]["points"][0]
            check(
                abs(first[0] - off_route["lat"]) < 1e-6 and abs(first[1] - off_route["lng"]) < 1e-6,
                "the new route starts where the player is",
            )

            await ws.send(json.dumps({"type": "position.update", "payload": goal}))
            reached = await next_of(ws, "goal.reached")
            check(reached["player_id"] == player, "reaching the goal is detected")

            await ws.send(json.dumps({"type": "position.update", "payload": {"lat": 200, "lng": 0}}))
            error = await next_of(ws, "error")
            check("lat" in error["message"], "invalid input is rejected without dropping the socket")

        final = (await client.get(f"/api/sessions/{sid}")).json()
        check(final["status"] == "finished" and final["winner_id"] == player, "the game is finished")

    print("All smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
