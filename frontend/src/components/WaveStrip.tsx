"use client";

import { useEffect, useRef, useState } from "react";
import styles from "@/app/page.module.css";
import { readStoredAdminToken, storeAdminToken } from "@/lib/adminToken";
import type { WaveNote, WaveState } from "@/lib/api";
import {
  DEFAULT_FIRST_WAVE_SECONDS,
  MAX_WAVES,
  SKIP_SECONDS,
  WAVE_STATE_LABEL,
  formatClock,
  nextWaveNumber,
  recordWave,
  removeWave,
  retimeWaves,
  skipTargetAfter,
  waveChipLabel,
  waveTime,
} from "@/lib/waves";

type WaveStripProps = {
  waves: WaveNote[];
  firstWaveSeconds: number | null;
  // Saves the wave list on its own, with the admin token. Rejects with an Error whose message is
  // shown to the user. The strip never saves the build (runes, spells, items, timeline).
  onSave: (
    waves: WaveNote[],
    firstWaveSeconds: number | null,
    adminToken: string,
  ) => Promise<void>;
  saving: boolean;
  onJumpToTimestamp: (seconds: number) => void;
  playerReady: boolean;
  currentTime: () => number | null;
  seekAndPause: (seconds: number) => void;
  // Lets the page load the player API only while the strip is being edited.
  onEditingChange?: (editing: boolean) => void;
};

const BUTTONS: { state: WaveState; key: string; className: string }[] = [
  { state: "push", key: "1", className: styles.waveButtonPush },
  { state: "pull", key: "2", className: styles.waveButtonPull },
  { state: "neutral", key: "3", className: styles.waveButtonNeutral },
  { state: "unknown", key: "4", className: styles.waveButtonUnknown },
];

// A horizontal strip under the video information: "ウェーブ管理  1：プッシュ  2：プッシュ  3：プル".
// "編集" at the right end swaps the strip, in place, for the input controls. In the input mode a
// wave is recorded with one button, which also seeks ahead by one wave interval and pauses.
// A recorded wave can only be deleted, not edited: to correct one, delete it and record it again.
export function WaveStrip({
  waves,
  firstWaveSeconds,
  onSave,
  saving,
  onJumpToTimestamp,
  playerReady,
  currentTime,
  seekAndPause,
  onEditingChange,
}: WaveStripProps) {
  const [editing, setEditing] = useState(false);
  const [draftWaves, setDraftWaves] = useState<WaveNote[]>(waves);
  const [draftFirst, setDraftFirst] = useState<number | null>(firstWaveSeconds);
  const [targetWave, setTargetWave] = useState(1);
  const [token, setToken] = useState(readStoredAdminToken);
  const [error, setError] = useState("");
  // A position the video should be moved to as soon as the player can be controlled. A ref,
  // because nothing is drawn from it; it is consumed once by the effect below.
  const parkAt = useRef<number | null>(null);

  const waveNumber = Math.min(targetWave, MAX_WAVES);

  function open() {
    setDraftWaves(waves);
    // Until the first wave is set by hand, the default is used, so recording can start at once.
    const first = firstWaveSeconds ?? DEFAULT_FIRST_WAVE_SECONDS;
    setDraftFirst(first);
    setTargetWave(nextWaveNumber(waves));
    setError("");
    setEditing(true);
    onEditingChange?.(true);
    // The player is only loaded once editing starts, so this waits for it (see the effect below).
    parkAt.current = first;
  }

  function close() {
    setEditing(false);
    onEditingChange?.(false);
  }

  function setFirstWave(seconds: number) {
    setError("");
    setDraftFirst(seconds);
    setDraftWaves((previous) => retimeWaves(previous, seconds));
    setTargetWave(nextWaveNumber(draftWaves));
    seekAndPause(seconds);
  }

  function useCurrentTime() {
    const seconds = currentTime();
    if (seconds === null) {
      setError("プレーヤーの準備ができていません。しばらくしてから、もう一度押してください。");
      return;
    }
    setFirstWave(seconds);
  }

  function record(state: WaveState) {
    if (draftFirst === null) {
      setError("先に、最初のウェーブが来る時刻を設定してください。");
      return;
    }
    setError("");
    setDraftWaves((previous) => recordWave(previous, draftFirst, waveNumber, state));
    setTargetWave(Math.min(waveNumber + 1, MAX_WAVES));
    seekAndPause(skipTargetAfter(draftFirst, waveNumber));
  }

  function remove(number: number) {
    setDraftWaves((previous) => {
      const next = removeWave(previous, number);
      setTargetWave(number);
      return next;
    });
  }

  async function save() {
    const trimmed = token.trim();
    if (!trimmed) {
      setError("管理者トークンを入力してください。");
      return;
    }
    setError("");
    try {
      await onSave(draftWaves, draftFirst, trimmed);
      storeAdminToken(trimmed);
      close();
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "ウェーブ情報の保存に失敗しました。",
      );
    }
  }

  useEffect(() => {
    if (parkAt.current !== null && editing && playerReady) {
      seekAndPause(parkAt.current);
      parkAt.current = null;
    }
  }, [editing, playerReady, seekAndPause]);

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
              <button
                key={wave.waveNumber}
                type="button"
                className={`${styles.waveChip} ${styles[`waveChip_${wave.state}`]}`}
                title={`${formatClock(wave.timeSeconds)} へ移動`}
                onClick={() => onJumpToTimestamp(wave.timeSeconds)}
              >
                {waveChipLabel(wave)}
              </button>
            ))
          ) : (
            <span className={styles.emptyInlineNote}>未入力</span>
          )}
        </div>
        <button type="button" className={styles.loadCandidatesButton} onClick={open}>
          編集
        </button>
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
          <button
            type="button"
            className={styles.waveStripHeaderButton}
            disabled={!playerReady}
            title={playerReady ? undefined : "プレーヤーの準備中です"}
            onClick={useCurrentTime}
          >
            ファーストウェーブの時間を現在時間に設定
          </button>
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
              ウェーブは概要欄から取得できないため、動画を見ながら入力します。ボタンを押すと記録し、
              {SKIP_SECONDS}秒先へ送って一時停止します。向きは、この動画の「自分側」のチャンピオンから見たものです。
              間違えたときは、そのウェーブの左端の赤い×で削除して、入力し直してください。
            </span>
          </span>
        </div>
        <button type="button" className={styles.loadCandidatesButton} onClick={close}>
          閉じる
        </button>
      </div>

      {draftFirst !== null && (
        <>
          <p className={styles.waveStatus} aria-live="polite">
            ウェーブ {waveNumber}（{formatClock(waveTime(draftFirst, waveNumber))}）：
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

      {draftWaves.length > 0 && (
        <ul className={styles.waveStripDeleteList}>
          {draftWaves.map((wave) => (
            <li key={wave.waveNumber} className={styles.waveEditItem}>
              <span className={styles.waveEditTime}>{formatClock(wave.timeSeconds)}</span>
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
        <label htmlFor="wave-admin-token">管理者トークン</label>
        <input
          id="wave-admin-token"
          type="password"
          className={styles.adminTokenInput}
          value={token}
          autoComplete="off"
          placeholder="ADMIN_TOKEN"
          onChange={(event) => setToken(event.target.value)}
        />
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
