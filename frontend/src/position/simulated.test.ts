import { describe, expect, it } from "vitest";
import { destinationPoint, haversineM } from "../geo";
import { bearingFromKeys } from "./keyboard";
import { SimulatedSource } from "./simulated";

const START = { lat: 32.0853, lng: 34.7818 };

describe("SimulatedSource", () => {
  it("emits its position when started and on every move", () => {
    const fixes: { lat: number; lng: number }[] = [];
    const sim = new SimulatedSource(START);
    sim.start((f) => fixes.push(f));
    sim.stepM = 10;
    sim.step(90);
    expect(fixes).toHaveLength(2);
    expect(haversineM(START, fixes[1])).toBeCloseTo(10, 3);
  });

  it("shift-steps are bigger", () => {
    const sim = new SimulatedSource(START);
    sim.stepM = 10;
    sim.step(0, 5);
    expect(haversineM(START, sim.position)).toBeCloseTo(50, 3);
  });

  it("advance() walks along a path and stops at the end", () => {
    const corner = destinationPoint(START, 90, 30);
    const end = destinationPoint(corner, 0, 30);
    const sim = new SimulatedSource(START);
    sim.setPath([corner, end]);
    expect(sim.advance(40)).toBe(true);
    expect(haversineM(sim.position, corner)).toBeCloseTo(10, 1);
    expect(sim.advance(100)).toBe(false);
    expect(haversineM(sim.position, end)).toBeLessThan(0.01);
  });
});

describe("bearingFromKeys", () => {
  it.each([
    [["ArrowUp"], 0],
    [["KeyD"], 90],
    [["ArrowDown"], 180],
    [["KeyA"], 270],
    [["ArrowUp", "ArrowRight"], 45],
    [["KeyS", "KeyA"], 225],
  ])("%j -> %d°", (keys, bearing) => {
    expect(bearingFromKeys(new Set(keys))).toBeCloseTo(bearing);
  });

  it("opposite keys cancel out", () => {
    expect(bearingFromKeys(new Set(["ArrowUp", "ArrowDown"]))).toBeNull();
  });
});
