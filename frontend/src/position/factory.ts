import type { LatLngPos } from "../types/protocol";
import { GeolocationSource } from "./geolocation";
import type { PositionSource, PositionSourceKind } from "./types";

/** Build the position source for a mode, starting from `origin`. */
export function createPositionSource(kind: PositionSourceKind, _origin: LatLngPos): PositionSource {
  switch (kind) {
    case "gps":
      return new GeolocationSource();
    default:
      throw new Error(`Unsupported position source: ${kind}`);
  }
}

export const SOURCE_LABELS: Record<PositionSourceKind, string> = {
  gps: "📍 GPS (browser geolocation)",
  simulated: "🎮 Simulated",
};
