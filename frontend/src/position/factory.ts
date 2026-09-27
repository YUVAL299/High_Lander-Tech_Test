import type { LatLngPos } from "../types/protocol";
import { GeolocationSource } from "./geolocation";
import { SimulatedSource } from "./simulated";
import type { PositionSource, PositionSourceKind } from "./types";

/** Build the position source for a mode, starting from `origin`. */
export function createPositionSource(kind: PositionSourceKind, origin: LatLngPos): PositionSource {
  return kind === "gps" ? new GeolocationSource() : new SimulatedSource(origin);
}

export const SOURCE_LABELS: Record<PositionSourceKind, string> = {
  gps: "📍 GPS (browser geolocation)",
  simulated: "🎮 Simulated",
};
