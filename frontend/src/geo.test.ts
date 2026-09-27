import { describe, expect, it } from "vitest";
import { destinationPoint, formatDistance, formatDuration, haversineM } from "./geo";

const TLV = { lat: 32.0853, lng: 34.7818 };

describe("geo", () => {
  it("haversine: one degree of latitude is ~111 km", () => {
    expect(haversineM({ lat: 0, lng: 0 }, { lat: 1, lng: 0 })).toBeCloseTo(111_195, -2);
  });

  it("destinationPoint round-trips the distance", () => {
    for (const bearing of [0, 90, 200, 315]) {
      const p = destinationPoint(TLV, bearing, 250);
      expect(haversineM(TLV, p)).toBeCloseTo(250, 3);
    }
  });

  it("formats distances and durations for humans", () => {
    expect(formatDistance(42.4)).toBe("42 m");
    expect(formatDistance(1534)).toBe("1.53 km");
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(125)).toBe("2m 05s");
  });
});
