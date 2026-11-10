"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import styles from "./page.module.css";

type Champion = {
  id: string;
  nameJa: string;
  nameEn: string;
  aliases: string[];
  imageUrl: string;
};

type ChampionResponse = {
  dataDragonVersion: string;
  items: Champion[];
};

type MatchupVideo = {
  id: string;
  playerChampionId: string;
  opponentChampionId: string;
  title: string;
  videoUrl: string;
  channelName: string;
  channelUrl: string;
  publishedAt: string | null;
  gamePatch: string | null;
  verifiedAt: string;
  verificationStatus: "verified";
  embedStatus: "unknown" | "allowed" | "disabled";
  sourceUrl: string;
};

type MatchupResponse = {
  playerChampionId: string;
  opponentChampionId: string;
  items: MatchupVideo[];
};

function formatIsoDate(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value.trim());
  return match ? match[1] : value;
}

type ChampionPickerProps = {
  id: string;
  side: "player" | "opponent";
  title: string;
  selected: Champion | null;
  onSelect: (champion: Champion | null) => void;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function ChampionPicker({
  id,
  side,
  title,
  selected,
  onSelect,
}: ChampionPickerProps) {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Champion[]>([]);
  const [version, setVersion] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError("");

      try {
        const url = new URL("/api/v1/champions", apiBaseUrl);
        const trimmedQuery = query.trim();
        if (trimmedQuery) {
          url.searchParams.set("q", trimmedQuery);
        }

        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`Champion request failed (${response.status})`);
        }

        const data = (await response.json()) as ChampionResponse;
        setItems(data.items);
        setVersion(data.dataDragonVersion);
      } catch (requestError) {
        if (requestError instanceof Error && requestError.name === "AbortError") {
          return;
        }
        setError("チャンピオン一覧を読み込めませんでした。APIの起動状態を確認してください。");
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, 120);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return (
    <section
      className={`${styles.picker} ${side === "player" ? styles.playerPicker : styles.opponentPicker}`}
      aria-labelledby={`${id}-heading`}
    >
      <div className={styles.pickerHeader}>
        <div>
          <p className={styles.step}>CHAMPION SELECT</p>
          <h2 id={`${id}-heading`}>{title}</h2>
        </div>
        {selected && (
          <button
            className={styles.clearButton}
            type="button"
            onClick={() => onSelect(null)}
          >
            解除
          </button>
        )}
      </div>

      <div
        className={`${styles.selected} ${selected ? "" : styles.selectedEmpty}`}
        aria-live="polite"
      >
        {selected ? (
          <>
            <Image
              src={selected.imageUrl}
              alt=""
              width={48}
              height={48}
              unoptimized
            />
            <div>
              <strong>{selected.nameJa}</strong>
              <span>{selected.nameEn}</span>
            </div>
            <span className={styles.selectedMark}>選択中</span>
          </>
        ) : (
          <span className={styles.selectionPlaceholder}>
            チャンピオン未選択
          </span>
        )}
      </div>

      <label className={styles.searchLabel} htmlFor={`${id}-search`}>
        チャンピオン名で検索
      </label>
      <input
        id={`${id}-search`}
        className={styles.searchInput}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="日本語・英語・ローマ字"
        autoComplete="off"
      />

      <div className={styles.results} aria-busy={loading}>
        {loading && <p className={styles.message}>読み込み中...</p>}
        {!loading && error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className={styles.message}>該当するチャンピオンがいません。</p>
        )}
        {!loading && !error && items.length > 0 && (
          <div className={styles.championGrid}>
            {items.map((champion) => {
              const isSelected = selected?.id === champion.id;
              return (
                <button
                  className={`${styles.champion} ${isSelected ? styles.championSelected : ""}`}
                  key={champion.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onSelect(champion)}
                  title={`${champion.nameJa} (${champion.nameEn})`}
                >
                  <Image
                    src={champion.imageUrl}
                    alt=""
                    width={48}
                    height={48}
                    unoptimized
                  />
                  <span>{champion.nameJa}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      {version && <p className={styles.version}>Data Dragon {version}</p>}
    </section>
  );
}

export default function Home() {
  const [playerChampion, setPlayerChampion] = useState<Champion | null>(null);
  const [opponentChampion, setOpponentChampion] = useState<Champion | null>(null);
  const [searchedMatchup, setSearchedMatchup] = useState(false);
  const [matchupVideos, setMatchupVideos] = useState<MatchupVideo[]>([]);
  const [matchupLoading, setMatchupLoading] = useState(false);
  const [matchupError, setMatchupError] = useState("");
  const matchupAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      matchupAbortRef.current?.abort();
    };
  }, []);

  function resetMatchupState() {
    matchupAbortRef.current?.abort();
    matchupAbortRef.current = null;
    setSearchedMatchup(false);
    setMatchupVideos([]);
    setMatchupLoading(false);
    setMatchupError("");
  }

  function selectPlayer(champion: Champion | null) {
    setPlayerChampion(champion);
    resetMatchupState();
  }

  function selectOpponent(champion: Champion | null) {
    setOpponentChampion(champion);
    resetMatchupState();
  }

  async function handleSearchMatchup() {
    if (!playerChampion || !opponentChampion) {
      return;
    }

    matchupAbortRef.current?.abort();
    const controller = new AbortController();
    matchupAbortRef.current = controller;

    setSearchedMatchup(true);
    setMatchupLoading(true);
    setMatchupError("");
    setMatchupVideos([]);

    try {
      const url = new URL(
        `/api/v1/matchups/${encodeURIComponent(playerChampion.id)}/${encodeURIComponent(opponentChampion.id)}`,
        apiBaseUrl,
      );
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) {
        let errorMessage =
          "マッチアップ情報を取得できませんでした。APIの起動状態を確認してください。";
        try {
          const payload = (await response.json()) as {
            detail?: { message?: string };
          };
          if (payload.detail?.message) {
            errorMessage = payload.detail.message;
          }
        } catch {
          // Keep fallback error message when response body is not JSON.
        }
        throw new Error(errorMessage);
      }

      const data = (await response.json()) as MatchupResponse;
      setMatchupVideos(data.items);
    } catch (requestError) {
      if (requestError instanceof Error && requestError.name === "AbortError") {
        return;
      }
      setMatchupError(
        requestError instanceof Error
          ? requestError.message
          : "マッチアップ情報を取得できませんでした。APIの起動状態を確認してください。",
      );
    } finally {
      if (!controller.signal.aborted) {
        setMatchupLoading(false);
      }
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>LEAGUE OF LEGENDS · TOP LANE</p>
          <h1>wintop-wingame</h1>
          <p className={styles.description}>
            自分と相手のチャンピオンを選択して、マッチアップを確認しましょう。
          </p>
        </div>
        <span className={styles.phase}>PHASE 1 · MVP</span>
      </header>

      <div className={styles.matchupSelector}>
        <ChampionPicker
          id="player"
          side="player"
          title="自分のチャンピオン"
          selected={playerChampion}
          onSelect={selectPlayer}
        />
        <div className={styles.searchAction}>
          <button
            className={styles.matchupSearchButton}
            type="button"
            disabled={!playerChampion || !opponentChampion || matchupLoading}
            onClick={handleSearchMatchup}
          >
            {matchupLoading ? "検索中..." : "WinTop!!"}
          </button>
        </div>
        <ChampionPicker
          id="opponent"
          side="opponent"
          title="相手のチャンピオン"
          selected={opponentChampion}
          onSelect={selectOpponent}
        />
      </div>

      {searchedMatchup && playerChampion && opponentChampion && (
        <section
          className={styles.matchupNotice}
          aria-live="polite"
          aria-busy={matchupLoading}
        >
          <p className={styles.step}>MATCHUP REPLAYS</p>
          <p className={styles.matchupHeading}>
            <strong>{playerChampion.nameJa}</strong>
            <span className={styles.versus}> vs </span>
            <strong>{opponentChampion.nameJa}</strong>
          </p>

          {matchupLoading && (
            <p className={styles.message}>確認済みリプレイを検索中...</p>
          )}

          {!matchupLoading && matchupError && (
            <p className={styles.error} role="alert">
              {matchupError}
            </p>
          )}

          {!matchupLoading && !matchupError && matchupVideos.length === 0 && (
            <p className={styles.noticeText}>
              この対面の確認済み動画はまだありません。
            </p>
          )}

          {!matchupLoading && !matchupError && matchupVideos.length > 0 && (
            <ul className={styles.videoList}>
              {matchupVideos.map((video) => (
                <li className={styles.videoCard} key={video.id}>
                  <div className={styles.videoInfo}>
                    <h3 className={styles.videoTitle}>{video.title}</h3>
                    <dl className={styles.videoMeta}>
                      <div>
                        <dt>チャンネル</dt>
                        <dd>
                          <a
                            href={video.channelUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {video.channelName}（外部サイト）
                          </a>
                        </dd>
                      </div>
                      {video.gamePatch && (
                        <div>
                          <dt>パッチ</dt>
                          <dd>{video.gamePatch}</dd>
                        </div>
                      )}
                      {video.publishedAt && (
                        <div>
                          <dt>公開日</dt>
                          <dd>{formatIsoDate(video.publishedAt)}</dd>
                        </div>
                      )}
                      <div>
                        <dt>確認日</dt>
                        <dd>{formatIsoDate(video.verifiedAt)}</dd>
                      </div>
                      <div>
                        <dt>出典</dt>
                        <dd>
                          <a
                            href={video.sourceUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            確認元ページ（外部サイト）
                          </a>
                        </dd>
                      </div>
                    </dl>
                  </div>
                  <a
                    className={styles.videoLink}
                    href={video.videoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    YouTubeで視聴（外部サイト・新しいタブ）
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <footer className={styles.footer}>
        <p>
          チャンピオン情報:{" "}
          <a
            href="https://developer.riotgames.com/docs/lol#data-dragon"
            target="_blank"
            rel="noopener noreferrer"
          >
            Riot Games Data Dragon
          </a>
        </p>
        <p className={styles.legal}>
          wintop-wingame is not endorsed by Riot Games and does not reflect the
          views or opinions of Riot Games or anyone officially involved in
          producing or managing Riot Games properties. Riot Games and all
          associated properties are trademarks or registered trademarks of
          Riot Games, Inc.
        </p>
      </footer>
    </main>
  );
}
