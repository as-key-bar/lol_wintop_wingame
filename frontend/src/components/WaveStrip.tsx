"use client";

import { useEffect, useState } from "react";
import styles from "@/app/page.module.css";
import type { WaveNote, WaveState } from "@/lib/api";
import {
  MAX_WAVES,
  WAVE_STATE_LABEL,
  nextWaveNumber,
  recordWave,
  removeWave,
  waveChipLabel,
} from "@/lib/waves";

type WaveStripProps = {
  waves: WaveNote[];
  // Saves the wave list on its own, as the logged-in editor. Rejects with an Error whose message
  // is shown to the user. The strip never saves the build (runes, spells, items, timeline).
  onSave: (waves: WaveNote[]) => Promise<void>;
  saving: boolean;
  // Only approved editors see the edit button; everyone else just views the waves.
  canEdit: boolean;
};

const BUTTONS: { state: WaveState; key: string; className: string }[] = [
  { state: "push", key: "1", className: styles.waveButtonPush },
  { state: "pull", key: "2", className: styles.waveButtonPull },
  { state: "neutral", key: "3", className: styles.waveButtonNeutral },
  { state: "unknown", key: "4", className: styles.waveButtonUnknown },
];

// A horizontal strip under the video information: "ウェーブ管理  1：プッシュ  2：プッシュ  3：プル".
// "編集" at the right end swaps the strip, in place, for the input controls. In the input mode a
// wave is recorded with one button (or key) and the next wave becomes the target. The waves are
// just an ordered list of push/pull states: they have no video time and never touch the player.
// A recorded wave can only be deleted, not edited: to correct one, delete it and record it again.
export function WaveStrip({ waves, onSave, saving, canEdit }: WaveStripProps) {
  const [editing, setEditing] = useState(false);
  const [draftWaves, setDraftWaves] = useState<WaveNote[]>(waves);
  const [targetWave, setTargetWave] = useState(1);
  const [error, setError] = useState("");

  const waveNumber = Math.min(targetWave, MAX_WAVES);

  function open() {
    setDraftWaves(waves);
    setTargetWave(nextWaveNumber(waves));
    setError("");
    setEditing(true);
  }

  function close() {
    setEditing(false);
  }

  function record(state: WaveState) {
    setError("");
    setDraftWaves((previous) => recordWave(previous, waveNumber, state));
    setTargetWave(Math.min(waveNumber + 1, MAX_WAVES));
  }

  function remove(number: number) {
    setDraftWaves((previous) => {
      const next = removeWave(previous, number);
      setTargetWave(number);
      return next;
    });
  }

  async function save() {
    setError("");
    try {
      await onSave(draftWaves);
      close();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "ウェーブ情報の保存に失敗しました。",
      );
    }
  }

  useEffect(() => {
    if (!editing) {
      return undefined;
    }
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
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

  const current = draftWaves.find((wave) => wave.waveNumber === waveNumber);

  if (!editing) {
    return (
      <section className={styles.waveStrip} aria-label="ウェーブ管理">
        <h4 className={styles.waveStripTitle}>ウェーブ管理</h4>
        <div className={styles.waveStripChips}>
          {waves.length > 0 ? (
            waves.map((wave) => (
              <span
                key={wave.waveNumber}
                className={`${styles.waveChip} ${styles[`waveChip_${wave.state}`]}`}
              >
                {waveChipLabel(wave)}
              </span>
            ))
          ) : (
            <span className={styles.emptyInlineNote}>未入力</span>
          )}
        </div>
        {canEdit && (
          <button type="button" className={styles.loadCandidatesButton} onClick={open}>
            編集
          </button>
        )}
      </section>
    );
  }

  return (
    <section
      className={`${styles.waveStrip} ${styles.waveStripEditing}`}
      aria-label="ウェーブ管理（編集）"
    >
      <div className={styles.waveStripEditHeader}>
        <div className={styles.waveStripEditTitle}>
          <h4 className={styles.waveStripTitle}>ウェーブ管理（編集）</h4>
          <span className={styles.helpWrapper}>
            <button
              type="button"
              className={styles.helpIcon}
              aria-label="ウェーブ管理の使い方"
              aria-describedby="wave-help-text"
            >
              ?
            </button>
            <span id="wave-help-text" role="tooltip" className={styles.helpTooltip}>
              ウェーブは概要欄から取得できないため、動画を見ながら入力します。
              ウェーブごとに、プッシュ・プルなどのボタンを押して順番に記録します。動画の再生位置は記録しません。向きは、この動画の「自分側」のチャンピオンから見たものです。
              間違えたときは、そのウェーブの左端の赤い×で削除して、入力し直してください。
            </span>
          </span>
        </div>
        <button type="button" className={styles.loadCandidatesButton} onClick={close}>
          閉じる
        </button>
      </div>

      <p className={styles.waveStatus} aria-live="polite">
        ウェーブ {waveNumber}：
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

      {draftWaves.length > 0 && (
        <ul className={styles.waveStripDeleteList}>
          {draftWaves.map((wave) => (
            <li key={wave.waveNumber} className={styles.waveEditItem}>
              <span className={`${styles.waveChip} ${styles[`waveChip_${wave.state}`]}`}>
                <button
                  type="button"
                  className={styles.waveDeleteMark}
                  aria-label={`ウェーブ${wave.waveNumber}を削除`}
                  onClick={() => remove(wave.waveNumber)}
                >
                  ×
                </button>
                {waveChipLabel(wave)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className={styles.waveStripRow}>
        <button
          type="button"
          className={styles.upvoteButtonActive}
          style={{ padding: "8px 16px", borderRadius: "8px", fontWeight: 700 }}
          disabled={saving}
          onClick={save}
        >
          {saving ? "保存中..." : "ウェーブを保存"}
        </button>
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
