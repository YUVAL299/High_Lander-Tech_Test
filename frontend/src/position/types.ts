import type { LatLngPos } from "../types/protocol";

export type PositionSourceKind = "gps" | "simulated";

export interface PositionFix extends LatLngPos {
  accuracyM?: number;
}

/** Anything that can tell us where the player is. */
export interface PositionSource {
  readonly kind: PositionSourceKind;
  start(onFix: (fix: PositionFix) => void, onError: (message: string) => void): void;
  stop(): void;
}
