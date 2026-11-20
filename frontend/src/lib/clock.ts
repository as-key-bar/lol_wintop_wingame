// Minutes:seconds text for the video timeline.
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
