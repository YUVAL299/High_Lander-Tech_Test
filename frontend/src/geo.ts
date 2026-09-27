import type { LatLngPos } from "./types/protocol";

const EARTH_RADIUS_M = 6_371_008.8;
const rad = (deg: number) => (deg * Math.PI) / 180;
const deg = (r: number) => (r * 180) / Math.PI;

export function haversineM(a: LatLngPos, b: LatLngPos): number {
  const dPhi = rad(b.lat - a.lat);
  const dLmb = rad(b.lng - a.lng);
  const h =
    Math.sin(dPhi / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLmb / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Point reached from `origin` after `distanceM` metres on `bearingDeg` (0 = north). */
export function destinationPoint(origin: LatLngPos, bearingDeg: number, distanceM: number): LatLngPos {
  const delta = distanceM / EARTH_RADIUS_M;
  const theta = rad(bearingDeg);
  const phi1 = rad(origin.lat);
  const lmb1 = rad(origin.lng);
  const phi2 = Math.asin(
    Math.sin(phi1) * Math.cos(delta) + Math.cos(phi1) * Math.sin(delta) * Math.cos(theta),
  );
  const lmb2 =
    lmb1 +
    Math.atan2(
      Math.sin(theta) * Math.sin(delta) * Math.cos(phi1),
      Math.cos(delta) - Math.sin(phi1) * Math.sin(phi2),
    );
  return { lat: deg(phi2), lng: ((deg(lmb2) + 540) % 360) - 180 };
}

export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}

export function formatDuration(s: number): string {
  const mins = Math.floor(s / 60);
  const secs = Math.round(s % 60);
  return mins > 0 ? `${mins}m ${secs.toString().padStart(2, "0")}s` : `${secs}s`;
}

/** Initial compass bearing from `a` to `b`, in degrees (0 = north). */
export function bearingDeg(a: LatLngPos, b: LatLngPos): number {
  const phi1 = rad(a.lat);
  const phi2 = rad(b.lat);
  const dLmb = rad(b.lng - a.lng);
  const y = Math.sin(dLmb) * Math.cos(phi2);
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLmb);
  return (deg(Math.atan2(y, x)) + 360) % 360;
}

/** The part of `points` still ahead of `pos` (from the nearest vertex on). */
export function remainingPath(points: LatLngPos[], pos: LatLngPos): LatLngPos[] {
  if (points.length === 0) return [];
  let nearest = 0;
  let best = Infinity;
  points.forEach((p, i) => {
    const d = haversineM(p, pos);
    if (d < best) {
      best = d;
      nearest = i;
    }
  });
  // If we're already past the nearest vertex, don't walk back to it.
  const ahead = points.slice(nearest);
  if (ahead.length > 1 && haversineM(pos, ahead[1]) <= haversineM(ahead[0], ahead[1])) {
    return ahead.slice(1);
  }
  return ahead;
}
