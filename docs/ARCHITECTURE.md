# Architecture

## Overview

```
┌──────────────────────────── Browser (TypeScript + Leaflet) ─────────────────────────────┐
│  PositionSource ──► PositionThrottle ──► GameSocket ◄──► GameApp ──► MapView / Hud       │
│   ├─ GeolocationSource (navigator.geolocation)                        DebugPanel          │
│   └─ SimulatedSource   (keyboard, map click, auto-walk)                                   │
└──────────────────────────────────────────┬───────────────────────────────────────────────┘
                                           │  HTTP /api/*   WebSocket /ws/*   (same origin)
┌──────────────────────────────────────────▼───────────────────────────────────────────────┐
│ nginx: serves the built SPA, reverse-proxies /api and /ws (backend resolved via DNS)      │
└──────────────────────────────────────────┬───────────────────────────────────────────────┘
┌──────────────────────────────────────────▼───────────────────────────────────────────────┐
│ FastAPI backend                                                                           │
│   api/        REST (create / join / get session) · WebSocket endpoint · health           │
│   services/   GameService ── GoalGenerator ── RoutingService (fallback) ── ConnectionHub  │
│   domain/     geo math · GameSession state machine · ReroutePolicy   (pure, no I/O)       │
│   routing/    RoutingProvider ◄── OsrmProvider                                            │
│   store/      SessionStore    ◄── InMemorySessionStore                                    │
└──────────────────────────────────────────┬───────────────────────────────────────────────┘
                                           │ HTTP
                               ┌───────────▼────────────┐
                               │ OSRM, walking profile  │  public FOSSGIS server or local container
                               └────────────────────────┘
```

### A game, step by step

1. The browser gets a first position fix (GPS or simulated) and calls
   `POST /api/sessions`.
2. `GoalGenerator` samples a random point 200–800 m away (spread evenly by
   area) and snaps it onto the nearest walkable road via OSRM `/nearest`,
   retrying if snapping moves it out of range. `RoutingService` computes the
   walking route. The response includes the goal, the route and your
   `player_id`.
3. The browser opens `/ws/sessions/{id}?player_id=…` and streams
   `position.update` messages, throttled on the client (≥ 2 m moved and
   ≥ 200 ms apart, plus a heartbeat every 5 s).
4. For each update, under the session lock, `GameService`:
   - records the position and checks the goal (`GameSession.move_player`),
   - asks `ReroutePolicy` whether a new route is needed,
   - broadcasts `player.moved`, and `goal.reached` if this move won.
5. If a reroute is needed, OSRM is called **outside** the lock and the new
   route is broadcast as `route.updated`.

### WebSocket messages

| Direction | Type              | Payload                                                         |
| --------- | ----------------- | --------------------------------------------------------------- |
| C → S     | `position.update` | `{lat, lng}`                                                    |
| C → S     | `ping`            | –                                                               |
| S → C     | `session.state`   | full `SessionView`, sent on connect                             |
| S → C     | `player.moved`    | `{player_id, position, distance_to_goal_m, remaining_route_m}` |
| S → C     | `route.updated`   | `{player_id, reason, reroute_count, route}`                     |
| S → C     | `goal.reached`    | `{player_id, name, elapsed_s, session}`                         |
| S → C     | `player.joined`   | `PlayerView`                                                    |
| S → C     | `player.presence` | `{player_id, connected}`                                        |
| S → C     | `error`           | `{message}` (the socket stays open)                             |

Server messages are defined in `backend/app/schemas.py` and mirrored in
`frontend/src/types/protocol.ts`. Interactive REST docs are at
`http://localhost:8000/docs` when the backend runs outside Docker.

## Key decisions

**The server decides what happens.** The goal, the routes and "who reached
the goal" are all computed on the backend. For a single player, detecting
arrival in the browser would have been enough. But declaring a winner among
several players has to happen in one place, and doing it on the server from
the start meant multiplayer needed no redesign.

**Location comes from the browser.** A container can't read the host's
location services, but the browser can, through the Geolocation API. It
works on `localhost` without HTTPS. `SimulatedSource` implements the same
`PositionSource` interface, so the rest of the app doesn't know or care which
one is active.

**A single-player game is just a session with one player.** Multiplayer
reuses the same code: one more REST call to join, plus a broadcast to
everyone in the session.

**Rerouting is throttled.** Asking OSRM for a route on every GPS tick would
be wasteful and would make the route line flicker. `ReroutePolicy` only
reroutes when the player is more than 25 m from the route line, and at most
once every 3 s. Between reroutes the server just measures how much of the
route is left.

**Routing failures are expected.** `OsrmProvider` has timeouts, one retry on
network or 5xx errors, and no retry on real answers such as `NoRoute`.
`RoutingService` falls back to a straight line, and the policy retries the
real router every 15 s. The game never gets stuck on "loading".

**Concurrency.** Each session has an `asyncio.Lock`, and every
read-modify-write happens under it, so simultaneous arrivals are processed
one at a time. `GameSession.move_player` only assigns a winner while the
session is still `ACTIVE`, so the first player to arrive wins and later
arrivals can't change that. Routing calls happen outside the lock, so one
player's reroute never delays another player's movement. A per-player
"routing in flight" set prevents duplicate reroutes.

**The game rules are separate from I/O.** Everything in `domain/` is
synchronous and has no dependencies, which makes it quick and thorough to
unit test. Services handle orchestration; the API layer only translates
between the wire format and service calls.

## Operations & production readiness

- **Health checks**: `/healthz` and `/readyz` on the backend, `/healthz` on
  nginx. Compose starts the frontend only once the backend is healthy.
- **Logs**: one JSON object per line, with `session_id` / `player_id` where
  relevant, ready for Loki or ELK.
- **Config**: all settings come from `HL_*` environment variables (12-factor
  style), documented in `.env.example`.
- **Containers**: multi-stage builds, non-root users (`appuser`,
  `nginx-unprivileged`), dependency layers cached separately from source, and
  static assets served with long-lived cache headers.
- **Cleanup**: idle sessions are removed after `HL_SESSION_TTL_S`. Clients
  send a ping every 20 s, so an idle but connected player isn't removed.
- **Client resilience**: the WebSocket reconnects with exponential backoff,
  and a page refresh resumes the game (the session is kept in
  `sessionStorage`).
- **Input validation**: Pydantic models on every REST body and WebSocket
  message; player names are restricted to a safe set of characters, and the
  UI only ever inserts text via `textContent`.

## Scaling out

One backend process can handle many concurrent sessions: the work per update
is small, and the only I/O is the occasional OSRM call. To run **several
backend replicas**, two in-process parts would move to Redis. Both are
already behind interfaces:

| Piece                 | Today                   | With multiple replicas                                                                  |
| --------------------- | ----------------------- | --------------------------------------------------------------------------------------- |
| `SessionStore`        | dict + `asyncio.Lock`   | Redis hash per session; the lock becomes a Redis lock, or optimistic concurrency on `GameSession.version` (already incremented on every change) |
| `ConnectionHub`       | sockets in this process | Publish events to a Redis channel per session; every replica forwards them to its own sockets |
| Routing               | public OSRM             | Self-hosted OSRM (`docker-compose.osrm.yml`), scaled horizontally; optionally cache routes by rounded origin/goal |

nginx already resolves the backend through DNS at request time, so adding
replicas behind a Compose/Kubernetes service needs no nginx change. Since
state lives in Redis, WebSocket connections don't need sticky sessions.

## Possible next steps

- Store sessions in Redis (above), so a backend restart doesn't end games.
- Anti-cheat: reject impossible speeds between updates (when not in debug
  mode) and sign player tokens instead of using a bare `player_id`.
- Lobby / countdown before a race starts, and several rounds per session.
- Serve map tiles from a local tile server to remove the last external
  dependency.
- Metrics (Prometheus): active sessions, update rate, OSRM latency and error
  rate.
