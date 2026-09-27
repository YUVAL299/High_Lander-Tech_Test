"""OSRM HTTP client (https://project-osrm.org/docs/v5.24.0/api/)."""

from __future__ import annotations

import logging
import time

import httpx

from app.domain.geo import LatLng
from app.domain.models import Route, RouteSource
from app.routing.base import RoutingError

log = logging.getLogger(__name__)

USER_AGENT = "HighLanderTechTest/0.1 (+https://github.com/YUVAL299/High_Lander-Tech_Test)"


def _coord(p: LatLng) -> str:
    # OSRM takes lng,lat - the opposite of most other APIs.
    return f"{p.lng:.6f},{p.lat:.6f}"


class OsrmProvider:
    def __init__(
        self,
        base_url: str,
        profile: str = "foot",
        timeout_s: float = 5.0,
        retries: int = 1,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # Note: osrm-routed serves a single dataset and ignores this path segment;
        # which travel mode you get is decided by the server behind base_url.
        self._profile = profile
        self._retries = retries
        self._client = client or httpx.AsyncClient(
            timeout=timeout_s, headers={"User-Agent": USER_AGENT}
        )

    async def route(self, origin: LatLng, destination: LatLng) -> Route:
        url = f"{self._base_url}/route/v1/{self._profile}/{_coord(origin)};{_coord(destination)}"
        data = await self._get(url, {"overview": "full", "geometries": "geojson"})
        try:
            best = data["routes"][0]
            points = [LatLng(lat, lng) for lng, lat in best["geometry"]["coordinates"]]
            return Route(
                points=points,
                distance_m=float(best["distance"]),
                duration_s=float(best["duration"]),
                source=RouteSource.OSRM,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RoutingError(f"unexpected OSRM route response: {exc}") from exc

    async def snap(self, point: LatLng) -> LatLng:
        url = f"{self._base_url}/nearest/v1/{self._profile}/{_coord(point)}"
        data = await self._get(url, {"number": "1"})
        try:
            lng, lat = data["waypoints"][0]["location"]
            return LatLng(lat, lng)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RoutingError(f"unexpected OSRM nearest response: {exc}") from exc

    async def _get(self, url: str, params: dict[str, str]) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self._retries + 1):
            started = time.perf_counter()
            try:
                resp = await self._client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - started) * 1000
                log.debug("osrm %s -> %s in %.0f ms", url, resp.status_code, elapsed_ms)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server error {resp.status_code}", request=resp.request, response=resp
                    )
                data = resp.json()
                # 4xx responses carry a meaningful OSRM code (e.g. NoRoute); don't retry.
                if data.get("code") != "Ok":
                    raise RoutingError(f"OSRM: {data.get('code')} - {data.get('message', '')}")
                return data
            except RoutingError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                log.warning("osrm request failed (attempt %d): %s", attempt + 1, exc)
        raise RoutingError(f"OSRM unavailable: {last_exc}") from last_exc

    async def aclose(self) -> None:
        await self._client.aclose()
