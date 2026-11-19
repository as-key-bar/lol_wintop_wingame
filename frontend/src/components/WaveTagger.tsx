"use client";

import { useEffect, useState } from "react";
import styles from "@/app/page.module.css";
import type { WaveNote, WaveState } from "@/lib/api";
import {
  MAX_WAVES,
  WAVE_INTERVAL_SECONDS,
  WAVE_STATE_LABEL,
  formatClock,
  nextWaveNumber,
  parseClock,
  recordWave,
  removeWave,
  retimeWaves,
  waveTime,
} from "@/lib/waves";

type WaveTaggerProps = {
  waves: WaveNote[];
  firstWaveSeconds: number | null;
  onChange: (waves: WaveNote[], firstWaveSeconds: number | null) => void;
  // From the player hook. Without them the tagger still works by typing times.
  playerReady: boolean;
  currentTime: () => number | null;
  seekAndPause: (seconds: number) => void;
};

const BUTTONS: { state: WaveState; key: string; className: string }[] = [
  { state: "push", key: "1", className: styles.waveButtonPush },
  { state: "pull", key: "2", className: styles.waveButtonPull },
  { state: "neutral", key: "3", className: styles.waveButtonNeutral },
  { state: "unknown", key: "4", className: styles.waveButtonUnknown },
];

// Tags the early minion waves with one button each. After a wave is recorded the video seeks
// forward by the wave interval and pauses, so a whole early game takes one press per wave.
export function WaveTagger({
  waves,
  firstWaveSeconds,
  onChange,
  playerReady,
  currentTime,
  seekAndPause,
}: WaveTaggerProps) {
  const [timeText, setTimeText] = useState(
    firstWaveSeconds === null ? "" : formatClock(firstWaveSeconds),
  );
  const [error, setError] = useState("");
  const [targetWave, setTargetWave] = useState(() => nextWaveNumber(waves));

  const waveNumber = Math.min(targetWave, MAX_WAVES);

  function setFirstWave(seconds: number) {
    setError("");
    setTimeText(formatClock(seconds));
    onChange(retimeWaves(waves, seconds), seconds);
    seekAndPause(seconds);
    setTargetWave(nextWaveNumber(waves));
  }

  function applyTypedTime() {
    const seconds = parseClock(timeText);
    if (seconds === null) {
      setError("時刻は「1:25」または秒数で入力してください。");
      return;
    }
    setFirstWave(seconds);
  }

  function useCurrentTime() {
    const seconds = currentTime();
    if (seconds === null) {
      setError("プレーヤーの準備ができていません。時刻を直接入力してください。");
      return;
    }
    setFirstWave(seconds);
  }

  function record(state: WaveState) {
    if (firstWaveSeconds === null) {
      setError("先に、最初のウェーブが来る時刻を設定してください。");
      return;
    }
    setError("");
    const next = recordWave(waves, firstWaveSeconds, waveNumber, state);
    onChange(next, firstWaveSeconds);
    const following = Math.min(waveNumber + 1, MAX_WAVES);
    setTargetWave(following);
    seekAndPause(waveTime(firstWaveSeconds, following));
  }

  function goToWave(number: number) {
    if (firstWaveSeconds === null) {
      return;
    }
    setTargetWave(number);
    seekAndPause(waveTime(firstWaveSeconds, number));
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
      ) {
        return;
      }
      const match = BUTTONS.find((button) => button.key === event.key);
      if (match) {
        event.preventDefault();
        record(match.state);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const current = waves.find((wave) => wave.waveNumber === waveNumber);

  return (
    <div className={styles.editorSection}>
      <h4>ウェーブのプッシュ・プル（手動入力）</h4>
      <p className={styles.emptyAnalysisNote}>
        ウェーブは、概要欄からは取得できません。動画を見ながら、1ウェーブごとにボタンを押してください。
        押すと記録して、{WAVE_INTERVAL_SECONDS}秒先へ送って一時停止します。
        プッシュ・プルは、この動画の「自分側」のチャンピオンから見た向きです。
      </p>

      <div className={styles.timelineEditRow}>
        <label htmlFor="first-wave-time">最初のウェーブの時刻</label>
        <input
          id="first-wave-time"
          className={styles.timelineTimeInput}
          placeholder="1:25"
          value={timeText}
          onChange={(event) => setTimeText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              applyTypedTime();
            }
          }}
        />
        <button type="button" className={styles.loadCandidatesButton} onClick={applyTypedTime}>
          設定
        </button>
        <button
          type="button"
          className={styles.loadCandidatesButton}
          disabled={!playerReady}
          title={playerReady ? undefined : "プレーヤーの準備中です"}
          onClick={useCurrentTime}
        >
          今の再生位置にする
        </button>
      </div>

      {firstWaveSeconds !== null && (
        <>
          <p className={styles.waveStatus} aria-live="polite">
            ウェーブ {waveNumber}（{formatClock(waveTime(firstWaveSeconds, waveNumber))}）：
            {current ? `記録済み＝${WAVE_STATE_LABEL[current.state]}` : "まだ記録していません"}
          </p>
          <div className={styles.waveButtons}>
            {BUTTONS.map((button) => (
              <button
                key={button.state}
                type="button"
                className={`${styles.waveButton} ${button.className}`}
                onClick={() => record(button.state)}
              >
                {WAVE_STATE_LABEL[button.state]}
                <kbd>{button.key}</kbd>
              </button>
            ))}
          </div>
        </>
      )}

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      {waves.length > 0 && (
        <ul className={styles.timelineEditList}>
          {waves.map((wave) => (
            <li key={wave.waveNumber} className={styles.timelineEditRow}>
              <button
                type="button"
                className={styles.loadCandidatesButton}
                onClick={() => goToWave(wave.waveNumber)}
              >
                ウェーブ{wave.waveNumber}（{formatClock(wave.timeSeconds)}）
              </button>
              <select
                aria-label={`ウェーブ${wave.waveNumber}の状態`}
                value={wave.state}
                onChange={(event) =>
                  onChange(
                    waves.map((item) =>
                      item.waveNumber === wave.waveNumber
                        ? { ...item, state: event.target.value as WaveState }
                        : item,
                    ),
                    firstWaveSeconds,
                  )
                }
              >
                {BUTTONS.map((button) => (
                  <option key={button.state} value={button.state}>
                    {WAVE_STATE_LABEL[button.state]}
                  </option>
                ))}
              </select>
              <input
                className={styles.timelineLabelInput}
                aria-label={`ウェーブ${wave.waveNumber}のメモ`}
                placeholder="メモ"
                maxLength={200}
                defaultValue={wave.note}
                onBlur={(event) =>
                  onChange(
                    waves.map((item) =>
                      item.waveNumber === wave.waveNumber
                        ? { ...item, note: event.target.value.trim() }
                        : item,
                    ),
                    firstWaveSeconds,
                  )
                }
              />
              <button
                type="button"
                className={styles.loadCandidatesButton}
                aria-label={`ウェーブ${wave.waveNumber}を削除`}
                onClick={() => onChange(removeWave(waves, wave.waveNumber), firstWaveSeconds)}
              >
                削除
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
