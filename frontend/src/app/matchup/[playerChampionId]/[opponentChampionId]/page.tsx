"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import styles from "../../../page.module.css";

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

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

function formatIsoDate(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value.trim());
  return match ? match[1] : value;
}

function getYouTubeEmbedUrl(videoUrl: string): string | null {
  try {
    const parsed = new URL(videoUrl);
    const videoId = parsed.searchParams.get("v")?.trim();
    if (!videoId) {
      return null;
    }
    return `https://www.youtube.com/embed/${encodeURIComponent(videoId)}`;
  } catch {
    return null;
  }
}

function MatchupContent() {
  const params = useParams<{
    playerChampionId: string;
    opponentChampionId: string;
  }>();
  const playerChampionId = decodeURIComponent(params.playerChampionId ?? "");
  const opponentChampionId = decodeURIComponent(params.opponentChampionId ?? "");

  const [playerChampion, setPlayerChampion] = useState<Champion | null>(null);
  const [opponentChampion, setOpponentChampion] = useState<Champion | null>(null);
  const [matchupVideos, setMatchupVideos] = useState<MatchupVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!playerChampionId || !opponentChampionId) {
      return;
    }

    const controller = new AbortController();

    async function fetchMatchupData() {
      setLoading(true);
      setError("");
      setMatchupVideos([]);

      try {
        const championsUrl = new URL("/api/v1/champions", apiBaseUrl);
        const matchupUrl = new URL(
          `/api/v1/matchups/${encodeURIComponent(playerChampionId)}/${encodeURIComponent(opponentChampionId)}`,
          apiBaseUrl,
        );

        const [championsResponse, matchupResponse] = await Promise.all([
          fetch(championsUrl, { signal: controller.signal }),
          fetch(matchupUrl, { signal: controller.signal }),
        ]);

        if (championsResponse.ok) {
          const championsData =
            (await championsResponse.json()) as ChampionResponse;
          setPlayerChampion(
            championsData.items.find((item) => item.id === playerChampionId) ??
              null,
          );
          setOpponentChampion(
            championsData.items.find((item) => item.id === opponentChampionId) ??
              null,
          );
        }

        if (!matchupResponse.ok) {
          let errorMessage =
            "マッチアップ情報を取得できませんでした。APIの起動状態を確認してください。";
          try {
            const payload = (await matchupResponse.json()) as {
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

        const matchupData = (await matchupResponse.json()) as MatchupResponse;
        setMatchupVideos(matchupData.items);
      } catch (requestError) {
        if (
          requestError instanceof Error &&
          requestError.name === "AbortError"
        ) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : "マッチアップ情報を取得できませんでした。APIの起動状態を確認してください。",
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void fetchMatchupData();

    return () => {
      controller.abort();
    };
  }, [playerChampionId, opponentChampionId]);

  const playerDisplayName = playerChampion?.nameJa ?? playerChampionId;
  const opponentDisplayName = opponentChampion?.nameJa ?? opponentChampionId;

  return (
    <>
      <section className={styles.matchupBanner} aria-label="選択中のマッチアップ">
        <div className={`${styles.matchupFighter} ${styles.playerPicker}`}>
          <p className={styles.step}>PLAYER CHAMPION</p>
          <div className={styles.fighterSummary}>
            {playerChampion && (
              <Image
                src={playerChampion.imageUrl}
                alt=""
                width={44}
                height={44}
                unoptimized
              />
            )}
            <div>
              <strong>{playerDisplayName}</strong>
              {playerChampion && <span>{playerChampion.nameEn}</span>}
            </div>
          </div>
        </div>

        <div className={styles.versusBadge} aria-hidden="true">
          VS
        </div>

        <div className={`${styles.matchupFighter} ${styles.opponentPicker}`}>
          <p className={styles.step}>OPPONENT CHAMPION</p>
          <div className={styles.fighterSummary}>
            {opponentChampion && (
              <Image
                src={opponentChampion.imageUrl}
                alt=""
                width={44}
                height={44}
                unoptimized
              />
            )}
            <div>
              <strong>{opponentDisplayName}</strong>
              {opponentChampion && <span>{opponentChampion.nameEn}</span>}
            </div>
          </div>
        </div>
      </section>

      <section
        className={styles.matchupNotice}
        aria-live="polite"
        aria-busy={loading}
      >
        <div className={styles.matchupSectionHeader}>
          <div>
            <p className={styles.step}>MATCHUP REPLAYS</p>
            <h2 className={styles.matchupHeading}>
              <strong>{playerDisplayName}</strong>
              <span className={styles.versus}> vs </span>
              <strong>{opponentDisplayName}</strong>
            </h2>
          </div>
          {!loading && !error && matchupVideos.length > 0 && (
            <span className={styles.videoCount}>
              全 {matchupVideos.length} 件
            </span>
          )}
        </div>

        {loading && (
          <p className={styles.message}>確認済みリプレイを検索中...</p>
        )}

        {!loading && error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        {!loading && !error && matchupVideos.length === 0 && (
          <p className={styles.noticeText}>
            この対面の確認済み動画はまだありません。
          </p>
        )}

        {!loading && !error && matchupVideos.length > 0 && (
          <ul className={styles.videoGrid}>
            {matchupVideos.map((video) => {
              const embedUrl =
                video.embedStatus === "disabled"
                  ? null
                  : getYouTubeEmbedUrl(video.videoUrl);

              return (
                <li className={styles.videoEmbedCard} key={video.id}>
                  {embedUrl && (
                    <div className={styles.videoPlayerWrapper}>
                      <iframe
                        className={styles.videoPlayer}
                        src={embedUrl}
                        title={video.title}
                        loading="lazy"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        referrerPolicy="strict-origin-when-cross-origin"
                        allowFullScreen
                      />
                    </div>
                  )}

                  <div className={styles.videoCardBody}>
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
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}

export default function MatchupPage() {
  return (
    <main className={`${styles.page} ${styles.matchupPage}`}>
      <header className={`${styles.header} ${styles.matchupHeader}`}>
        <div>
          <p className={styles.eyebrow}>LEAGUE OF LEGENDS · TOP LANE</p>
          <h1>wintop-wingame</h1>
        </div>
        <div className={styles.headerActions}>
          <Link className={styles.backLink} href="/">
            ← チャンピオン選択に戻る
          </Link>
          <span className={styles.phase}>PHASE 1 · MVP</span>
        </div>
      </header>

      <Suspense
        fallback={
          <section
            className={styles.matchupNotice}
            aria-live="polite"
            aria-busy="true"
          >
            <p className={styles.message}>確認済みリプレイを検索中...</p>
          </section>
        }
      >
        <MatchupContent />
      </Suspense>

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
