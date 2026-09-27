import { describe, expect, it } from "vitest";
import { destinationPoint } from "../geo";
import { PositionThrottle } from "./throttle";

const START = { lat: 32.0853, lng: 34.7818 };
const opts = { minDistanceM: 2, minIntervalMs: 200, heartbeatMs: 5000 };

describe("PositionThrottle", () => {
  it("always sends the first fix", () => {
    expect(new PositionThrottle(opts).shouldSend(START, 0)).toBe(true);
  });

  it("ignores GPS jitter below the distance threshold", () => {
    const t = new PositionThrottle(opts);
    t.shouldSend(START, 0);
    expect(t.shouldSend(destinationPoint(START, 90, 1), 1000)).toBe(false);
  });

  it("rate-limits real movement", () => {
    const t = new PositionThrottle(opts);
    t.shouldSend(START, 0);
    const moved = destinationPoint(START, 90, 10);
    expect(t.shouldSend(moved, 50)).toBe(false);
    expect(t.shouldSend(moved, 250)).toBe(true);
  });

  it("sends a heartbeat even when standing still", () => {
    const t = new PositionThrottle(opts);
    t.shouldSend(START, 0);
    expect(t.shouldSend(START, 4999)).toBe(false);
    expect(t.shouldSend(START, 5000)).toBe(true);
  });

  it("reset forces the next fix through", () => {
    const t = new PositionThrottle(opts);
    t.shouldSend(START, 0);
    t.reset();
    expect(t.shouldSend(START, 10)).toBe(true);
  });
});
