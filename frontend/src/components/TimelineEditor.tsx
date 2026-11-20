"use client";

import { useState } from "react";
import styles from "@/app/page.module.css";
import type { VideoTimestamp } from "@/lib/api";
import { formatClock, parseClock } from "@/lib/clock";

const MAX_TIMESTAMPS = 300;

type TimelineEditorProps = {
  timestamps: VideoTimestamp[];
  onChange: (next: VideoTimestamp[]) => void;
  // Reads the current playback time of the video, when the player is available.
  currentTime?: () => number | null;
};

// Edits the description-derived timeline by hand: add, change, or remove entries.
export function TimelineEditor({ timestamps, onChange, currentTime }: TimelineEditorProps) {
  const [timeText, setTimeText] = useState("");
  const [label, setLabel] = useState("");
  const [isKill, setIsKill] = useState(false);
  const [error, setError] = useState("");

  const sorted = [...timestamps].sort((a, b) => a.timeSeconds - b.timeSeconds);

  function add() {
    const seconds = parseClock(timeText);
    if (seconds === null) {
      setError("時刻は「1:25」または秒数で入力してください。");
      return;
    }
    if (!label.trim()) {
      setError("内容を入力してください。");
      return;
    }
    if (timestamps.length >= MAX_TIMESTAMPS) {
      setError(`登録できるのは${MAX_TIMESTAMPS}件までです。`);
      return;
    }
    setError("");
    onChange([
      ...timestamps,
      {
        timeSeconds: seconds,
        timeLabel: formatClock(seconds),
        label: label.trim().slice(0, 200),
        isKillEvent: isKill,
      },
    ]);
    setTimeText("");
    setLabel("");
    setIsKill(false);
  }

  function useCurrentTime() {
    const seconds = currentTime?.();
    if (seconds !== null && seconds !== undefined) {
      setTimeText(formatClock(seconds));
    }
  }

  function update(index: number, patch: Partial<VideoTimestamp>) {
    const target = sorted[index];
    onChange(timestamps.map((item) => (item === target ? { ...item, ...patch } : item)));
  }

  function remove(index: number) {
    const target = sorted[index];
    onChange(timestamps.filter((item) => item !== target));
  }

  return (
    <div className={styles.editorSection}>
      <h4>タイムライン（{timestamps.length}件）</h4>

      <div className={styles.timelineEditRow}>
        <input
          className={styles.timelineTimeInput}
          aria-label="新しい項目の時刻"
          placeholder="1:25"
          value={timeText}
          onChange={(event) => setTimeText(event.target.value)}
        />
        {currentTime && (
          <button type="button" className={styles.loadCandidatesButton} onClick={useCurrentTime}>
            再生位置
          </button>
        )}
        <input
          className={styles.timelineLabelInput}
          aria-label="新しい項目の内容"
          placeholder="内容（例：ファーストブラッド）"
          value={label}
          maxLength={200}
          onChange={(event) => setLabel(event.target.value)}
        />
        <label className={styles.timelineKillToggle}>
          <input
            type="checkbox"
            checked={isKill}
            onChange={(event) => setIsKill(event.target.checked)}
          />
          キル
        </label>
        <button type="button" className={styles.loadCandidatesButton} onClick={add}>
          追加
        </button>
      </div>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      {sorted.length === 0 ? (
        <p className={styles.emptyAnalysisNote}>タイムラインは未登録です。</p>
      ) : (
        <ul className={styles.timelineEditList}>
          {sorted.map((item, index) => (
            <li key={`${item.timeSeconds}-${index}`} className={styles.timelineEditRow}>
              <input
                className={styles.timelineTimeInput}
                aria-label={`${item.timeLabel} の時刻`}
                defaultValue={formatClock(item.timeSeconds)}
                onBlur={(event) => {
                  const seconds = parseClock(event.target.value);
                  if (seconds === null) {
                    event.target.value = formatClock(item.timeSeconds);
                    return;
                  }
                  update(index, { timeSeconds: seconds, timeLabel: formatClock(seconds) });
                }}
              />
              <input
                className={styles.timelineLabelInput}
                aria-label={`${item.timeLabel} の内容`}
                defaultValue={item.label}
                maxLength={200}
                onBlur={(event) => {
                  const value = event.target.value.trim();
                  if (!value) {
                    event.target.value = item.label;
                    return;
                  }
                  update(index, { label: value });
                }}
              />
              <label className={styles.timelineKillToggle}>
                <input
                  type="checkbox"
                  checked={item.isKillEvent}
                  onChange={(event) => update(index, { isKillEvent: event.target.checked })}
                />
                キル
              </label>
              <button
                type="button"
                className={styles.loadCandidatesButton}
                aria-label={`${item.timeLabel} を削除`}
                onClick={() => remove(index)}
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
