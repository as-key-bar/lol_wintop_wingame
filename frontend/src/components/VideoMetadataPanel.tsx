"use client";

import Image from "next/image";
import { useState } from "react";
import styles from "@/app/page.module.css";
import {
  type GameAssetsCatalog,
  type RuneSelection,
  type VideoMetadataAnalysis,
} from "@/lib/api";

type VideoMetadataPanelProps = {
  metadata: VideoMetadataAnalysis | null | undefined;
  gameAssets: GameAssetsCatalog | null;
  analyzing: boolean;
  savingManual: boolean;
  onAnalyzeDescription: () => void;
  onSaveManualMetadata: (updated: VideoMetadataAnalysis) => Promise<void>;
  onJumpToTimestamp: (seconds: number) => void;
};

export function VideoMetadataPanel({
  metadata,
  gameAssets,
  analyzing,
  savingManual,
  onAnalyzeDescription,
  onSaveManualMetadata,
  onJumpToTimestamp,
}: VideoMetadataPanelProps) {
  const [editing, setEditing] = useState(false);
  const [onlyKills, setOnlyKills] = useState(false);

  const [draftPrimaryStyleId, setDraftPrimaryStyleId] = useState<number | null>(
    null,
  );
  const [draftSubStyleId, setDraftSubStyleId] = useState<number | null>(null);
  const [draftPrimarySelections, setDraftPrimarySelections] = useState<
    number[]
  >([]);
  const [draftSubSelections, setDraftSubSelections] = useState<number[]>([]);
  const [draftShards, setDraftShards] = useState<number[]>([]);
  const [draftSpells, setDraftSpells] = useState<string[]>([]);
  const [draftItems, setDraftItems] = useState<string[]>([]);

  function openEditor() {
    if (!gameAssets) {
      return;
    }
    const existingRunes = metadata?.runes;
    const defaultPrimary =
      existingRunes?.primaryStyleId ?? gameAssets.runeStyles[0]?.id ?? null;
    const defaultSub =
      existingRunes?.subStyleId ??
      gameAssets.runeStyles.find((s) => s.id !== defaultPrimary)?.id ??
      null;

    setDraftPrimaryStyleId(defaultPrimary);
    setDraftSubStyleId(defaultSub);
    setDraftPrimarySelections(existingRunes?.primarySelections ?? []);
    setDraftSubSelections(existingRunes?.subSelections ?? []);
    setDraftShards(existingRunes?.statShards ?? [5008, 5008, 5001]);
    setDraftSpells(metadata?.summonerSpells ?? []);
    setDraftItems(metadata?.startingItems ?? []);
    setEditing(true);
  }

  function togglePrimaryRune(slotIndex: number, runeId: number) {
    if (!gameAssets || !draftPrimaryStyleId) {
      return;
    }
    const style = gameAssets.runeStyles.find(
      (s) => s.id === draftPrimaryStyleId,
    );
    if (!style) {
      return;
    }
    const slotRuneIds = new Set(
      style.slots[slotIndex]?.runes.map((r) => r.id) ?? [],
    );
    const filtered = draftPrimarySelections.filter(
      (id) => !slotRuneIds.has(id),
    );
    setDraftPrimarySelections([...filtered, runeId]);
  }

  function toggleSubRune(slotIndex: number, runeId: number) {
    if (!gameAssets || !draftSubStyleId) {
      return;
    }
    const style = gameAssets.runeStyles.find((s) => s.id === draftSubStyleId);
    if (!style) {
      return;
    }
    const slotRuneIds = new Set(
      style.slots[slotIndex]?.runes.map((r) => r.id) ?? [],
    );
    const withoutSameSlot = draftSubSelections.filter(
      (id) => !slotRuneIds.has(id),
    );
    const next = [...withoutSameSlot, runeId];
    setDraftSubSelections(next.slice(-2));
  }

  function selectShard(rowIndex: number, shardId: number) {
    const next = [...draftShards];
    while (next.length < 3) {
      next.push(5008);
    }
    next[rowIndex] = shardId;
    setDraftShards(next);
  }

  function toggleSpell(spellId: string) {
    if (draftSpells.includes(spellId)) {
      setDraftSpells(draftSpells.filter((id) => id !== spellId));
      return;
    }
    const next = [...draftSpells, spellId];
    setDraftSpells(next.slice(-2));
  }

  function toggleStarterItem(itemId: string) {
    if (draftItems.includes(itemId)) {
      setDraftItems(draftItems.filter((id) => id !== itemId));
      return;
    }
    const next = [...draftItems, itemId];
    setDraftItems(next.slice(0, 4));
  }

  async function handleSaveDraft() {
    const runesPayload: RuneSelection | null = draftPrimaryStyleId
      ? {
          primaryStyleId: draftPrimaryStyleId,
          subStyleId: draftSubStyleId,
          primarySelections: draftPrimarySelections,
          subSelections: draftSubSelections,
          statShards: draftShards,
        }
      : null;

    await onSaveManualMetadata({
      analysisStatus: "manual_verified",
      runes: runesPayload,
      summonerSpells: draftSpells,
      startingItems: draftItems,
      timestamps: metadata?.timestamps ?? [],
    });
    setEditing(false);
  }

  if (!gameAssets) {
    return null;
  }

  const runes = metadata?.runes ?? null;
  const primaryStyle =
    gameAssets.runeStyles.find((s) => s.id === runes?.primaryStyleId) ?? null;
  const subStyle =
    gameAssets.runeStyles.find((s) => s.id === runes?.subStyleId) ?? null;
  const selectedRuneSet = new Set([
    ...(runes?.primarySelections ?? []),
    ...(runes?.subSelections ?? []),
  ]);

  const spells = (metadata?.summonerSpells ?? [])
    .map((id) => gameAssets.summonerSpells.find((s) => s.id === id))
    .filter((s): s is NonNullable<typeof s> => Boolean(s));

  const starterItems = (metadata?.startingItems ?? [])
    .map((id) => gameAssets.starterItems.find((item) => item.id === id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  const allTimestamps = metadata?.timestamps ?? [];
  const killCount = allTimestamps.filter((ts) => ts.isKillEvent).length;
  const visibleTimestamps = onlyKills
    ? allTimestamps.filter((ts) => ts.isKillEvent)
    : allTimestamps;

  const statusLabel =
    metadata?.analysisStatus === "manual_verified"
      ? "手動確認済"
      : metadata?.analysisStatus === "auto_parsed"
        ? "概要欄から自動抽出"
        : "未抽出";

  return (
    <section className={styles.analysisPanel} aria-label="ビルド・タイムライン解析">
      <div className={styles.analysisHeader}>
        <div className={styles.analysisTitleGroup}>
          <h3 className={styles.analysisTitle}>
            ルーン・スペル・初手アイテム・タイムライン
          </h3>
          <span
            className={`${styles.videoOriginBadge} ${
              metadata && metadata.analysisStatus !== "unanalyzed"
                ? styles.originSaved
                : styles.originCandidate
            }`}
          >
            {statusLabel}
          </span>
        </div>

        <div className={styles.analysisActions}>
          <button
            type="button"
            className={styles.loadCandidatesButton}
            disabled={analyzing}
            onClick={onAnalyzeDescription}
          >
            {analyzing ? "概要欄を解析中..." : "概要欄から自動取得"}
          </button>
          <button
            type="button"
            className={styles.loadCandidatesButton}
            onClick={() => (editing ? setEditing(false) : openEditor())}
          >
            {editing ? "編集を閉じる" : "ビルドを手動編集"}
          </button>
        </div>
      </div>

      {editing && (
        <div className={styles.metadataEditor}>
          <div className={styles.editorSection}>
            <h4>メインパス・ルーン選択</h4>
            <div className={styles.styleOptionRow}>
              {gameAssets.runeStyles.map((style) => (
                <button
                  key={style.id}
                  type="button"
                  className={`${styles.assetChoiceButton} ${
                    draftPrimaryStyleId === style.id
                      ? styles.assetChoiceActive
                      : ""
                  }`}
                  onClick={() => {
                    setDraftPrimaryStyleId(style.id);
                    setDraftPrimarySelections([]);
                    if (draftSubStyleId === style.id) {
                      const fallbackSub = gameAssets.runeStyles.find(
                        (s) => s.id !== style.id,
                      );
                      setDraftSubStyleId(fallbackSub?.id ?? null);
                      setDraftSubSelections([]);
                    }
                  }}
                >
                  <Image
                    src={style.iconUrl}
                    alt=""
                    width={22}
                    height={22}
                    unoptimized
                  />
                  <span>{style.nameJa}</span>
                </button>
              ))}
            </div>

            {draftPrimaryStyleId &&
              gameAssets.runeStyles
                .find((s) => s.id === draftPrimaryStyleId)
                ?.slots.map((slot) => (
                  <div key={slot.slotIndex} className={styles.runeSlotRow}>
                    {slot.runes.map((rune) => (
                      <button
                        key={rune.id}
                        type="button"
                        className={`${styles.assetChoiceButton} ${
                          draftPrimarySelections.includes(rune.id)
                            ? styles.assetChoiceActive
                            : ""
                        }`}
                        onClick={() =>
                          togglePrimaryRune(slot.slotIndex, rune.id)
                        }
                      >
                        <Image
                          src={rune.iconUrl}
                          alt=""
                          width={24}
                          height={24}
                          unoptimized
                        />
                        <span>{rune.nameJa}</span>
                      </button>
                    ))}
                  </div>
                ))}
          </div>

          <div className={styles.editorSection}>
            <h4>サブパス・ルーン選択（2枠）</h4>
            <div className={styles.styleOptionRow}>
              {gameAssets.runeStyles
                .filter((style) => style.id !== draftPrimaryStyleId)
                .map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    className={`${styles.assetChoiceButton} ${
                      draftSubStyleId === style.id
                        ? styles.assetChoiceActive
                        : ""
                    }`}
                    onClick={() => {
                      setDraftSubStyleId(style.id);
                      setDraftSubSelections([]);
                    }}
                  >
                    <Image
                      src={style.iconUrl}
                      alt=""
                      width={22}
                      height={22}
                      unoptimized
                    />
                    <span>{style.nameJa}</span>
                  </button>
                ))}
            </div>

            {draftSubStyleId &&
              gameAssets.runeStyles
                .find((s) => s.id === draftSubStyleId)
                ?.slots.slice(1)
                .map((slot) => (
                  <div key={slot.slotIndex} className={styles.runeSlotRow}>
                    {slot.runes.map((rune) => (
                      <button
                        key={rune.id}
                        type="button"
                        className={`${styles.assetChoiceButton} ${
                          draftSubSelections.includes(rune.id)
                            ? styles.assetChoiceActive
                            : ""
                        }`}
                        onClick={() => toggleSubRune(slot.slotIndex, rune.id)}
                      >
                        <Image
                          src={rune.iconUrl}
                          alt=""
                          width={22}
                          height={22}
                          unoptimized
                        />
                        <span>{rune.nameJa}</span>
                      </button>
                    ))}
                  </div>
                ))}
          </div>

          <div className={styles.editorSection}>
            <h4>ステータスシャード（3段）</h4>
            {gameAssets.statShardRows.map((row, rowIdx) => (
              <div key={rowIdx} className={styles.runeSlotRow}>
                {row.map((shard) => (
                  <button
                    key={`${rowIdx}-${shard.id}`}
                    type="button"
                    className={`${styles.assetChoiceButton} ${
                      draftShards[rowIdx] === shard.id
                        ? styles.assetChoiceActive
                        : ""
                    }`}
                    onClick={() => selectShard(rowIdx, shard.id)}
                  >
                    <Image
                      src={shard.iconUrl}
                      alt=""
                      width={20}
                      height={20}
                      unoptimized
                    />
                    <span>{shard.nameJa}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>

          <div className={styles.editorSection}>
            <h4>サモナースペル（2枠）＆ 初手アイテム</h4>
            <div className={styles.runeSlotRow}>
              {gameAssets.summonerSpells.map((spell) => (
                <button
                  key={spell.id}
                  type="button"
                  className={`${styles.assetChoiceButton} ${
                    draftSpells.includes(spell.id)
                      ? styles.assetChoiceActive
                      : ""
                  }`}
                  onClick={() => toggleSpell(spell.id)}
                >
                  <Image
                    src={spell.iconUrl}
                    alt=""
                    width={22}
                    height={22}
                    unoptimized
                  />
                  <span>{spell.nameJa}</span>
                </button>
              ))}
            </div>
            <div className={styles.runeSlotRow}>
              {gameAssets.starterItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`${styles.assetChoiceButton} ${
                    draftItems.includes(item.id)
                      ? styles.assetChoiceActive
                      : ""
                  }`}
                  onClick={() => toggleStarterItem(item.id)}
                >
                  <Image
                    src={item.iconUrl}
                    alt=""
                    width={22}
                    height={22}
                    unoptimized
                  />
                  <span>{item.nameJa}</span>
                </button>
              ))}
            </div>
          </div>

          <div className={styles.editorFooter}>
            <button
              type="button"
              className={styles.upvoteButtonActive}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                border: "1px solid #f6c873",
                fontWeight: 700,
                cursor: "pointer",
              }}
              disabled={savingManual}
              onClick={handleSaveDraft}
            >
              {savingManual ? "保存中..." : "このビルド情報をDBに保存"}
            </button>
          </div>
        </div>
      )}

      <div className={styles.analysisGrid}>
        {/* Full Rune Tree Display */}
        <div className={styles.analysisCard}>
          <h4 className={styles.analysisCardHeading}>
            ルーン構成（フル表示）
          </h4>
          {primaryStyle ? (
            <div className={styles.runeTreesContainer}>
              <div className={styles.runeTreeColumn}>
                <div className={styles.runeStyleHeader}>
                  <Image
                    src={primaryStyle.iconUrl}
                    alt=""
                    width={24}
                    height={24}
                    unoptimized
                  />
                  <strong>{primaryStyle.nameJa}</strong>
                  <span className={styles.runeStyleSub}>
                    {primaryStyle.nameEn}
                  </span>
                </div>
                {primaryStyle.slots.map((slot) => (
                  <div key={slot.slotIndex} className={styles.runeTreeRow}>
                    {slot.runes.map((rune) => {
                      const active = selectedRuneSet.has(rune.id);
                      const isKeystone = slot.slotIndex === 0;
                      return (
                        <div
                          key={rune.id}
                          className={`${styles.runeNode} ${
                            active
                              ? styles.runeNodeActive
                              : styles.runeNodeInactive
                          }`}
                          title={`${rune.nameJa} (${rune.nameEn})`}
                        >
                          <Image
                            src={rune.iconUrl}
                            alt={rune.nameJa}
                            width={isKeystone ? 38 : 28}
                            height={isKeystone ? 38 : 28}
                            unoptimized
                          />
                          <span className={styles.runeNodeLabel}>
                            {rune.nameJa}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>

              <div className={styles.runeTreeColumn}>
                {subStyle && (
                  <>
                    <div className={styles.runeStyleHeader}>
                      <Image
                        src={subStyle.iconUrl}
                        alt=""
                        width={22}
                        height={22}
                        unoptimized
                      />
                      <strong>{subStyle.nameJa}</strong>
                      <span className={styles.runeStyleSub}>
                        {subStyle.nameEn}
                      </span>
                    </div>
                    {subStyle.slots.slice(1).map((slot) => (
                      <div key={slot.slotIndex} className={styles.runeTreeRow}>
                        {slot.runes.map((rune) => {
                          const active = selectedRuneSet.has(rune.id);
                          return (
                            <div
                              key={rune.id}
                              className={`${styles.runeNode} ${
                                active
                                  ? styles.runeNodeActive
                                  : styles.runeNodeInactive
                              }`}
                              title={`${rune.nameJa} (${rune.nameEn})`}
                            >
                              <Image
                                src={rune.iconUrl}
                                alt={rune.nameJa}
                                width={26}
                                height={26}
                                unoptimized
                              />
                              <span className={styles.runeNodeLabel}>
                                {rune.nameJa}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </>
                )}

                <div className={styles.shardsBlock}>
                  <span className={styles.shardsHeading}>
                    ステータスシャード
                  </span>
                  {gameAssets.statShardRows.map((row, rowIndex) => {
                    const selectedShardId = runes?.statShards?.[rowIndex];
                    return (
                      <div key={rowIndex} className={styles.runeTreeRow}>
                        {row.map((shard) => {
                          const active = selectedShardId === shard.id;
                          return (
                            <div
                              key={`${rowIndex}-${shard.id}`}
                              className={`${styles.runeNode} ${
                                active
                                  ? styles.runeNodeActive
                                  : styles.runeNodeInactive
                              }`}
                              title={`${shard.nameJa} (${shard.nameEn})`}
                            >
                              <Image
                                src={shard.iconUrl}
                                alt={shard.nameJa}
                                width={20}
                                height={20}
                                unoptimized
                              />
                              <span className={styles.runeNodeLabel}>
                                {shard.nameJa}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <p className={styles.emptyAnalysisNote}>
              ルーン情報は未抽出です。「概要欄から自動取得」を押すか「ビルドを手動編集」から設定できます。
            </p>
          )}
        </div>

        {/* Spells, Starter Items, and Kill Timestamps */}
        <div className={styles.analysisSideColumn}>
          <div className={styles.analysisCard}>
            <h4 className={styles.analysisCardHeading}>
              サモナースペル ＆ スタートアイテム
            </h4>
            <div className={styles.LoadoutRow}>
              <div className={styles.loadoutGroup}>
                <span className={styles.loadoutLabel}>サモナースペル</span>
                {spells.length > 0 ? (
                  <div className={styles.assetChipList}>
                    {spells.map((spell) => (
                      <div key={spell.id} className={styles.assetBadge}>
                        <Image
                          src={spell.iconUrl}
                          alt={spell.nameJa}
                          width={28}
                          height={28}
                          unoptimized
                        />
                        <span>{spell.nameJa}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className={styles.emptyInlineNote}>未抽出</span>
                )}
              </div>

              <div className={styles.loadoutGroup}>
                <span className={styles.loadoutLabel}>
                  スタートアイテム（Phase 2Bで画像認識自動化予定）
                </span>
                {starterItems.length > 0 ? (
                  <div className={styles.assetChipList}>
                    {starterItems.map((item) => (
                      <div key={item.id} className={styles.assetBadge}>
                        <Image
                          src={item.iconUrl}
                          alt={item.nameJa}
                          width={28}
                          height={28}
                          unoptimized
                        />
                        <span>{item.nameJa}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className={styles.emptyInlineNote}>
                    未設定（「ビルドを手動編集」から登録可）
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className={styles.analysisCard}>
            <div className={styles.timelineHeaderRow}>
              <h4 className={styles.analysisCardHeading}>
                タイムライン・キルタイミング（クリックで再生位置ジャンプ）
              </h4>
              {killCount > 0 && (
                <button
                  type="button"
                  className={`${styles.filterKillButton} ${
                    onlyKills ? styles.filterKillButtonActive : ""
                  }`}
                  onClick={() => setOnlyKills((prev) => !prev)}
                >
                  ⚔ キル・交戦のみ ({killCount})
                </button>
              )}
            </div>

            {visibleTimestamps.length > 0 ? (
              <div className={styles.timelineList}>
                {visibleTimestamps.map((ts, index) => (
                  <button
                    key={`${ts.timeSeconds}-${index}`}
                    type="button"
                    className={`${styles.timestampChip} ${
                      ts.isKillEvent ? styles.timestampChipKill : ""
                    }`}
                    onClick={() => onJumpToTimestamp(ts.timeSeconds)}
                  >
                    <span className={styles.timestampTime}>
                      ▶ {ts.timeLabel}
                    </span>
                    {ts.isKillEvent && (
                      <span className={styles.killTag}>KILL</span>
                    )}
                    <span className={styles.timestampLabel}>{ts.label}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className={styles.emptyAnalysisNote}>
                タイムスタンプ情報は未抽出です。「概要欄から自動取得」を押すと動画概要欄のチャプター・キル時間を抽出します。
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

