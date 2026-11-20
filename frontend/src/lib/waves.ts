import type { WaveNote, WaveState } from "@/lib/api";

// Waves are an ordered list of push/pull states; they carry no video time.
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
export function recordWave(waves: WaveNote[], waveNumber: number, state: WaveState): WaveNote[] {
  const next: WaveNote = { waveNumber, state };
  return [...waves.filter((wave) => wave.waveNumber !== waveNumber), next].sort(
    (a, b) => a.waveNumber - b.waveNumber,
  );
}

export function removeWave(waves: WaveNote[], waveNumber: number): WaveNote[] {
  return waves.filter((wave) => wave.waveNumber !== waveNumber);
}
