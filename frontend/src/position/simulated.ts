import { destinationPoint, haversineM } from "../geo";
import type { LatLngPos } from "../types/protocol";
import type { PositionFix, PositionSource } from "./types";

const AUTO_WALK_TICK_MS = 200;

/**
 * A fake position you control: step with the keyboard, teleport by clicking
 * the map, or let it walk along the route by itself.
 */
export class SimulatedSource implements PositionSource {
  readonly kind = "simulated" as const;
  private onFix: ((fix: PositionFix) => void) | null = null;
  private walkTimer: ReturnType<typeof setInterval> | undefined;
  private walkPath: LatLngPos[] = [];
  /** Metres per keyboard step. */
  stepM = 10;
  /** Auto-walk speed in metres per second. */
  speedMps = 8;

  constructor(private pos: LatLngPos) {}

  get position(): LatLngPos {
    return this.pos;
  }

  get walking(): boolean {
    return this.walkTimer !== undefined;
  }

  start(onFix: (fix: PositionFix) => void): void {
    this.onFix = onFix;
    this.emit();
  }

  stop(): void {
    this.stopWalking();
    this.onFix = null;
  }

  teleport(pos: LatLngPos): void {
    this.pos = pos;
    this.emit();
  }

  /** Move one step on a compass bearing (0 = north). */
  step(bearingDeg: number, multiplier = 1): void {
    this.teleport(destinationPoint(this.pos, bearingDeg, this.stepM * multiplier));
  }

  /** Follow `path` (e.g. the current route) at `speedMps` until the end. */
  walkAlong(path: LatLngPos[], onDone?: () => void): void {
    this.stopWalking();
    this.setPath(path);
    this.walkTimer = setInterval(() => {
      if (!this.advance((this.speedMps * AUTO_WALK_TICK_MS) / 1000)) {
        this.stopWalking();
        onDone?.();
      }
    }, AUTO_WALK_TICK_MS);
  }

  /** Replace the path that `advance()` follows. */
  setPath(path: LatLngPos[]): void {
    this.walkPath = [...path];
  }

  stopWalking(): void {
    clearInterval(this.walkTimer);
    this.walkTimer = undefined;
  }

  /** Move `budgetM` metres along the remaining path. Returns false at the end. */
  advance(budgetM: number): boolean {
    let remaining = budgetM;
    while (this.walkPath.length > 0) {
      const next = this.walkPath[0];
      const d = haversineM(this.pos, next);
      if (d > remaining) {
        const fraction = remaining / d;
        this.pos = {
          lat: this.pos.lat + (next.lat - this.pos.lat) * fraction,
          lng: this.pos.lng + (next.lng - this.pos.lng) * fraction,
        };
        this.emit();
        return true;
      }
      remaining -= d;
      this.pos = next;
      this.walkPath.shift();
    }
    this.emit();
    return false;
  }

  private emit(): void {
    this.onFix?.({ ...this.pos });
  }
}
