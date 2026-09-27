import { haversineM } from "../geo";
import type { LatLngPos } from "../types/protocol";

export interface ThrottleOptions {
  /** Ignore jitter smaller than this... */
  minDistanceM: number;
  /** ...and never send faster than this... */
  minIntervalMs: number;
  /** ...but always send at least this often, so the server knows we're alive. */
  heartbeatMs: number;
}

export const DEFAULT_THROTTLE: ThrottleOptions = {
  minDistanceM: 2,
  minIntervalMs: 200,
  heartbeatMs: 5_000,
};

/** Decides which position fixes are worth sending to the server. */
export class PositionThrottle {
  private last: LatLngPos | null = null;
  private lastAt = -Infinity;

  constructor(private readonly opts: ThrottleOptions = DEFAULT_THROTTLE) {}

  shouldSend(pos: LatLngPos, now: number): boolean {
    const elapsed = now - this.lastAt;
    const moved = this.last ? haversineM(this.last, pos) : Infinity;
    const send =
      elapsed >= this.opts.heartbeatMs ||
      (elapsed >= this.opts.minIntervalMs && moved >= this.opts.minDistanceM);
    if (send) {
      this.last = pos;
      this.lastAt = now;
    }
    return send;
  }

  reset(): void {
    this.last = null;
    this.lastAt = -Infinity;
  }
}
