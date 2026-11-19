import type { WaveNote, WaveState } from "@/lib/api";

// Minion waves reach the lane at a fixed interval; once the first one is known, the time
// of every later wave follows from it. This is the time that gets stored.
export const WAVE_INTERVAL_SECONDS = 30;
export const MAX_WAVES = 20;

export const WAVE_STATE_LABEL: Record<WaveState, string> = {
  push: "プッシュ",
  pull: "プル",
  neutral: "中立",
  unknown: "不明",
};

// "1：プッシュ" — the label of one wave in the strip.
export function waveChipLabel(wave: { waveNumber: number; state: WaveState }): string {
  return `${wave.waveNumber}：${WAVE_STATE_LABEL[wave.state]}`;
}

export function waveTime(firstWaveSeconds: number, waveNumber: number): number {
  return firstWaveSeconds + (waveNumber - 1) * WAVE_INTERVAL_SECONDS;
}

export function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

// "1:25", "85", "01:25" -> seconds; null when it cannot be read.
export function parseClock(text: string): number | null {
  const value = text.trim();
  if (/^\d+$/.test(value)) {
    return Number(value);
  }
  const match = /^(\d+):([0-5]?\d)$/.exec(value);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

export function nextWaveNumber(waves: WaveNote[]): number {
  const noted = new Set(waves.map((wave) => wave.waveNumber));
  for (let number = 1; number <= MAX_WAVES; number += 1) {
    if (!noted.has(number)) {
      return number;
    }
  }
  return MAX_WAVES;
}

// Records one wave, replacing an earlier note for the same wave number.
export function recordWave(
  waves: WaveNote[],
  firstWaveSeconds: number,
  waveNumber: number,
  state: WaveState,
): WaveNote[] {
  const next: WaveNote = {
    waveNumber,
    timeSeconds: waveTime(firstWaveSeconds, waveNumber),
    state,
  };
  return [...waves.filter((wave) => wave.waveNumber !== waveNumber), next].sort(
    (a, b) => a.waveNumber - b.waveNumber,
  );
}

export function removeWave(waves: WaveNote[], waveNumber: number): WaveNote[] {
  return waves.filter((wave) => wave.waveNumber !== waveNumber);
}

// Moving the first-wave time moves every later wave with it.
export function retimeWaves(waves: WaveNote[], firstWaveSeconds: number): WaveNote[] {
  return waves.map((wave) => ({
    ...wave,
    timeSeconds: waveTime(firstWaveSeconds, wave.waveNumber),
  }));
}
