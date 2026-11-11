"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { RiotFooter } from "@/components/RiotFooter";
import {
  apiBaseUrl,
  formatIsoDate,
  getYouTubeEmbedUrl,
  type Champion,
  type ChampionResponse,
  type MatchupResponse,
  type MatchupVideo,
} from "@/lib/api";
import styles from "@/app/page.module.css";

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
      <header className={styles.matchupCompactBar} aria-label="選択中のマッチアップ">
        <div className={styles.matchupBarLeft}>
          <Link className={styles.backLink} href="/">
            ← チャンピオン選択
          </Link>
          <span className={styles.brandCompact}>wintop-wingame</span>
        </div>

        <h1 className={styles.matchupInlineSummary}>
          <span className={`${styles.championChip} ${styles.playerChip}`}>
            {playerChampion && (
              <Image
                src={playerChampion.imageUrl}
                alt=""
                width={28}
                height={28}
                unoptimized
              />
            )}
            <strong>{playerDisplayName}</strong>
          </span>
          <span className={styles.versusInline}>VS</span>
          <span className={`${styles.championChip} ${styles.opponentChip}`}>
            {opponentChampion && (
              <Image
                src={opponentChampion.imageUrl}
                alt=""
                width={28}
                height={28}
                unoptimized
              />
            )}
            <strong>{opponentDisplayName}</strong>
          </span>
        </h1>

        <div className={styles.matchupBarRight}>
          {!loading && !error && (
            <span className={styles.videoCount}>
              全 {matchupVideos.length} 件
            </span>
          )}
        </div>
      </header>

      <section
        className={styles.matchupResults}
        aria-live="polite"
        aria-busy={loading}
      >
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
                      <h2 className={styles.videoTitle}>{video.title}</h2>
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
      <Suspense
        fallback={
          <section
            className={styles.matchupResults}
            aria-live="polite"
            aria-busy="true"
          >
            <p className={styles.message}>確認済みリプレイを検索中...</p>
          </section>
        }
      >
        <MatchupContent />
      </Suspense>

      <RiotFooter />
    </main>
  );
}
