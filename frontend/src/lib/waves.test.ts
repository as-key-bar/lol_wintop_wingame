import { describe, expect, it } from "vitest";
import type { WaveNote } from "./api";
import {
  waveChipLabel,
  formatClock,
  nextWaveNumber,
  parseClock,
  recordWave,
  removeWave,
  retimeWaves,
  waveTime,
} from "./waves";

const note = (waveNumber: number, state: WaveNote["state"]): WaveNote => ({
  waveNumber,
  timeSeconds: 0,
  state,
});

describe("waveTime", () => {
  it("places waves 30 seconds apart starting from the first wave", () => {
    expect(waveTime(85, 1)).toBe(85);
    expect(waveTime(85, 2)).toBe(115);
    expect(waveTime(85, 4)).toBe(175);
  });
});

describe("clock text", () => {
  it("formats and parses minutes and seconds", () => {
    expect(formatClock(85)).toBe("1:25");
    expect(formatClock(5)).toBe("0:05");
    expect(parseClock("1:25")).toBe(85);
    expect(parseClock("01:05")).toBe(65);
    expect(parseClock("85")).toBe(85);
  });

  it("rejects text that is not a time", () => {
    expect(parseClock("")).toBeNull();
    expect(parseClock("1:75")).toBeNull();
    expect(parseClock("abc")).toBeNull();
  });
});

describe("recordWave", () => {
  it("adds waves in order and fills in their time from the first wave", () => {
    let waves: WaveNote[] = [];
    waves = recordWave(waves, 85, 2, "pull");
    waves = recordWave(waves, 85, 1, "push");

    expect(waves.map((w) => [w.waveNumber, w.timeSeconds, w.state])).toEqual([
      [1, 85, "push"],
      [2, 115, "pull"],
    ]);
  });

  it("replaces an earlier note for the same wave", () => {
    const waves = recordWave([note(1, "push")], 85, 1, "pull");

    expect(waves).toEqual([{ waveNumber: 1, timeSeconds: 85, state: "pull" }]);
  });
});

describe("nextWaveNumber", () => {
  it("returns the first wave that has not been noted yet", () => {
    expect(nextWaveNumber([])).toBe(1);
    expect(nextWaveNumber([note(1, "push"), note(2, "pull")])).toBe(3);
    expect(nextWaveNumber([note(1, "push"), note(3, "pull")])).toBe(2);
  });
});

describe("removeWave and retimeWaves", () => {
  it("removes only the chosen wave", () => {
    expect(removeWave([note(1, "push"), note(2, "pull")], 1).map((w) => w.waveNumber)).toEqual([2]);
  });

  it("moves every wave when the first-wave time changes", () => {
    const moved = retimeWaves([note(1, "push"), note(2, "pull")], 90);
    expect(moved.map((w) => w.timeSeconds)).toEqual([90, 120]);
  });
});

describe("waveChipLabel", () => {
  it("shows the wave number and its state", () => {
    expect(waveChipLabel({ waveNumber: 1, state: "push" })).toBe("1：プッシュ");
    expect(waveChipLabel({ waveNumber: 3, state: "pull" })).toBe("3：プル");
    expect(waveChipLabel({ waveNumber: 4, state: "unknown" })).toBe("4：不明");
  });
});
