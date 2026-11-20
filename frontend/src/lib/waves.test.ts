import { describe, expect, it } from "vitest";
import type { WaveNote } from "./api";
import {
  waveChipLabel,
  nextWaveNumber,
  recordWave,
  removeWave,
} from "./waves";

const note = (waveNumber: number, state: WaveNote["state"]): WaveNote => ({
  waveNumber,
  state,
});

describe("recordWave", () => {
  it("adds waves in wave-number order, with no video time", () => {
    let waves: WaveNote[] = [];
    waves = recordWave(waves, 2, "pull");
    waves = recordWave(waves, 1, "push");

    expect(waves).toEqual([
      { waveNumber: 1, state: "push" },
      { waveNumber: 2, state: "pull" },
    ]);
  });

  it("replaces an earlier note for the same wave", () => {
    const waves = recordWave([note(1, "push")], 1, "pull");

    expect(waves).toEqual([{ waveNumber: 1, state: "pull" }]);
  });
});

describe("nextWaveNumber", () => {
  it("returns the first wave that has not been noted yet", () => {
    expect(nextWaveNumber([])).toBe(1);
    expect(nextWaveNumber([note(1, "push"), note(2, "pull")])).toBe(3);
    expect(nextWaveNumber([note(1, "push"), note(3, "pull")])).toBe(2);
  });
});

describe("removeWave", () => {
  it("removes only the chosen wave", () => {
    expect(removeWave([note(1, "push"), note(2, "pull")], 1).map((w) => w.waveNumber)).toEqual([2]);
  });
});

describe("waveChipLabel", () => {
  it("shows the wave number and its state", () => {
    expect(waveChipLabel({ waveNumber: 1, state: "push" })).toBe("1：プッシュ");
    expect(waveChipLabel({ waveNumber: 3, state: "pull" })).toBe("3：プル");
    expect(waveChipLabel({ waveNumber: 4, state: "unknown" })).toBe("4：不明");
  });
});
