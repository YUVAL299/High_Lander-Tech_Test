# High Lander – Navigation Game

A real-time, map-based navigation game. When you start, a goal flag appears
somewhere 200–800 m away. The shortest **walking** route to it is drawn on an
OpenStreetMap map, and you race to reach it. Walk off the path and the route
is recalculated. Get within 20 m of the flag and you win.

This delivers **Part 1** of the assessment (the core single-player system).
The design is ready for **Part 2** (multiplayer): see
[Designed for multiplayer](docs/ARCHITECTURE.md#designed-for-multiplayer-part-2).

![stack](https://img.shields.io/badge/stack-FastAPI%20%C2%B7%20WebSockets%20%C2%B7%20Leaflet%20%C2%B7%20OSRM-blue)

---

## Quick start

Requirements: **Docker** with Docker Compose v2. Nothing else: no API keys,
no cloud accounts.

```bash
git clone https://github.com/YUVAL299/High_Lander-Tech_Test.git
cd High_Lander-Tech_Test
docker compose up --build
```

Open **<http://localhost:8080>** and choose:

- **📍 Use my location**: your real position from the browser's Geolocation API
  (Wi-Fi, GPS or IP based, depending on the machine), or
- **🎮 Simulate**: no GPS needed. Move with the keyboard (see below).

> Geolocation only works on `localhost` or HTTPS. That's a browser rule, not
> ours. `http://localhost:8080` is fine.

Stop with `Ctrl+C` or `docker compose down`. A `Makefile` wraps the common
commands: `make up`, `make down`, `make test`, `make e2e`, `make offline`.

## How to test it (reviewer's guide)

The **🛠 Debug & simulation** panel (bottom left) makes every feature easy to
check from a desk:

| Want to see…                  | Do this                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------ |
| Real-time movement            | `←↑↓→` / `WASD` (hold two for diagonals, `Shift` = 5× step), or click the map to teleport |
| Proximity / goal detection    | **🏁 Jump near goal** (puts you 10 m outside the radius), then take one step in |
| Dynamic rerouting             | **🔀 Wander off route** jumps 60 m sideways and a new route appears (counter +1) |
| The whole game, hands-free    | **▶ Auto-walk route** follows the route to the flag (speed slider: 1–30 m/s)   |
| Real GPS                      | Switch to **📍 GPS** at any time; your real position takes over                |
| Resilience                    | Refresh the page (the game resumes); `docker compose restart frontend` drops the connection and the client reconnects on its own |

Pressing a movement key or clicking the map while in GPS mode switches to
simulation automatically. To start a simulated game somewhere specific, open
`http://localhost:8080/?at=51.5007,-0.1246` (lat,lng).

## Routing: online by default, fully offline if you want

Routes come from [OSRM](https://project-osrm.org/) using its **walking**
profile, so only paths a pedestrian may use are allowed.

| Mode                  | How                                                                                     | Notes                                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Default**           | `docker compose up --build`                                                             | Uses the free public [FOSSGIS OSRM](https://routing.openstreetmap.de) walking server. No key; works anywhere in the world.  |
| **Offline (local OSRM)** | `docker compose -f docker-compose.yml -f docker-compose.osrm.yml up --build` (or `make offline`) | First run downloads an OSM extract (Israel by default, ~100 MB) and builds a routing graph (a few minutes, ~2–4 GB RAM). Choose another region with `OSRM_PBF_URL` in `.env`. |

If the router is unreachable the game **keeps working**: it draws a dashed
straight line to the goal, shows "⚠️ Straight line (router offline)", and
retries the real router every 15 s.

Map tiles come from OpenStreetMap's public tile servers. They're the one
remaining external request; you can swap in any tile server in
`frontend/src/map/mapView.ts`.

## Configuration

Copy `.env.example` to `.env`. Every setting is optional:

| Variable                    | Default                                          | Meaning                                  |
| --------------------------- | ------------------------------------------------ | ---------------------------------------- |
| `HL_PORT`                   | `8080`                                           | Port the game is served on               |
| `HL_OSRM_URL`               | `https://routing.openstreetmap.de/routed-foot`   | OSRM server                              |
| `HL_GOAL_MIN_DISTANCE_M` / `HL_GOAL_MAX_DISTANCE_M` | `200` / `800`            | Where the goal may be placed             |
| `HL_GOAL_REACH_RADIUS_M`    | `20`                                             | How close counts as "reached"            |
| `HL_REROUTE_OFF_ROUTE_M`    | `25`                                             | Distance from the route that triggers a reroute |
| `HL_REROUTE_MIN_INTERVAL_S` | `3`                                              | Minimum time between reroutes            |
| `HL_SESSION_TTL_S`          | `3600`                                           | Idle games are cleaned up after this     |
| `HL_LOG_LEVEL`              | `INFO`                                           | Backend log level (JSON logs)            |
| `OSRM_PBF_URL`              | Israel & Palestine extract                        | Region for the offline OSRM              |

## Development

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload            # http://localhost:8000/docs for the API
pytest                                   # unit + integration tests
ruff check . && ruff format --check .

# Frontend (Node 22)
cd frontend
npm install
npm run dev                              # http://localhost:5173, proxies to :8000
npm test && npm run typecheck
```

No local toolchain? `make test` runs both test suites in Docker, and `make e2e`
starts the whole stack with a stub router and plays a scripted game against
it.

## Project layout

```
backend/                 FastAPI game server
  app/domain/            pure game rules: geo math, sessions, reroute policy (no I/O)
  app/routing/           RoutingProvider interface + OSRM client
  app/services/          GameService (orchestration), goal placement, fallback routing, WS hub
  app/store/             SessionStore interface + in-memory implementation
  app/api/               REST + WebSocket endpoints
  tests/                 unit & integration tests (OSRM faked)
frontend/                TypeScript + Leaflet single-page app, served by nginx
  src/position/          GPS, simulated position, keyboard, send throttling
  src/net/               REST client + auto-reconnecting WebSocket
  src/map/, src/ui/      map layers, HUD, debug panel, start/result screens
osrm/                    scripts for the optional local OSRM
e2e/                     stub OSRM + end-to-end smoke test
deploy/                  compose overlay that runs published images (staging)
docs/ARCHITECTURE.md     design, decisions, scaling notes
.github/workflows/ci.yml CI/CD: lint → test → build → e2e → publish → staging
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`):

1. **Backend**: ruff lint and format check, pytest.
2. **Frontend**: TypeScript typecheck, vitest, production build.
3. **End-to-end**: builds the Docker images, starts the full Compose stack
   (with a stub OSRM so CI never depends on the internet) and plays a
   scripted game through nginx.
4. **Publish** (on `main`): pushes images to GHCR, tagged with the commit SHA.
5. **Deploy to staging**: starts exactly those images and runs the smoke test
   against them. It uses an ephemeral runner by default; point it at a
   self-hosted runner for a persistent staging box.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and the
reasoning behind it.
