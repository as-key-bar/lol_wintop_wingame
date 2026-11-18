"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { RiotFooter } from "@/components/RiotFooter";
import { VideoMetadataPanel } from "@/components/VideoMetadataPanel";
import {
  apiBaseUrl,
  formatIsoDate,
  getOrCreateVoterToken,
  getYouTubeEmbedUrl,
  type Champion,
  type ChampionResponse,
  type GameAssetsCatalog,
  type MatchupResponse,
  type MatchupVideo,
  type VideoMetadataAnalysis,
} from "@/lib/api";
import styles from "@/app/page.module.css";

function sortMatchupVideos(videos: MatchupVideo[]): MatchupVideo[] {
  return [...videos].sort((a, b) => {
    const aSaved = a.origin !== "youtube_search" ? 1 : 0;
    const bSaved = b.origin !== "youtube_search" ? 1 : 0;
    if (aSaved !== bSaved) {
      return bSaved - aSaved;
    }
    const aVotes = a.upvoteCount ?? 0;
    const bVotes = b.upvoteCount ?? 0;
    if (aVotes !== bVotes) {
      return bVotes - aVotes;
    }
    return 0;
  });
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
  const [gameAssets, setGameAssets] = useState<GameAssetsCatalog | null>(null);
  const [matchupVideos, setMatchupVideos] = useState<MatchupVideo[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
  const [playbackStartSeconds, setPlaybackStartSeconds] = useState<
    number | null
  >(null);
  const [loading, setLoading] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [searchedCandidates, setSearchedCandidates] = useState(false);
  const [upvotingVideoId, setUpvotingVideoId] = useState<string | null>(null);
  const [analyzingVideoId, setAnalyzingVideoId] = useState<string | null>(null);
  const [savingMetadata, setSavingMetadata] = useState(false);
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
      setSelectedVideoId(null);
      setSearchedCandidates(false);

      try {
        const voterToken = getOrCreateVoterToken();
        const championsUrl = new URL("/api/v1/champions", apiBaseUrl);
        const gameAssetsUrl = new URL("/api/v1/game-assets", apiBaseUrl);
        const matchupUrl = new URL(
          `/api/v1/matchups/${encodeURIComponent(playerChampionId)}/${encodeURIComponent(opponentChampionId)}`,
          apiBaseUrl,
        );
        if (voterToken) {
          matchupUrl.searchParams.set("voterToken", voterToken);
        }

        const [championsResponse, gameAssetsResponse, matchupResponse] =
          await Promise.all([
            fetch(championsUrl, { signal: controller.signal }),
            fetch(gameAssetsUrl, { signal: controller.signal }),
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

        if (gameAssetsResponse.ok) {
          const assetsData =
            (await gameAssetsResponse.json()) as GameAssetsCatalog;
          setGameAssets(assetsData);
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
        setSelectedVideoId(matchupData.items[0]?.id ?? null);
        if (
          matchupData.items.length === 0 ||
          matchupData.items.some((item) => item.origin === "youtube_search")
        ) {
          setSearchedCandidates(true);
        }
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
  const activeVideo =
    matchupVideos.find((video) => video.id === selectedVideoId) ??
    matchupVideos[0] ??
    null;
  const activeEmbedUrl =
    activeVideo && activeVideo.embedStatus !== "disabled"
      ? getYouTubeEmbedUrl(activeVideo.videoUrl, playbackStartSeconds)
      : null;

  async function handleAnalyzeVideo(video: MatchupVideo, refresh: boolean) {
    if (!playerChampionId || !opponentChampionId || analyzingVideoId) {
      return;
    }
    setAnalyzingVideoId(video.id);
    setError("");
    try {
      const analyzeUrl = new URL(
        `/api/v1/matchups/${encodeURIComponent(playerChampionId)}/${encodeURIComponent(opponentChampionId)}/analyze`,
        apiBaseUrl,
      );
      const response = await fetch(analyzeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ video, refresh }),
      });
      if (!response.ok) {
        throw new Error("動画概要欄からの情報取得に失敗しました。");
      }
      const analyzed = (await response.json()) as VideoMetadataAnalysis;
      setMatchupVideos((previous) =>
        previous.map((item) =>
          item.id === video.id ? { ...item, metadata: analyzed } : item,
        ),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "動画概要欄からの情報取得に失敗しました。",
      );
    } finally {
      setAnalyzingVideoId(null);
    }
  }

  async function handleSaveManualMetadata(
    video: MatchupVideo,
    metadata: VideoMetadataAnalysis,
    adminToken: string,
  ) {
    if (!playerChampionId || !opponentChampionId || savingMetadata) {
      return;
    }
    setSavingMetadata(true);
    try {
      const saveUrl = new URL(
        `/api/v1/matchups/${encodeURIComponent(playerChampionId)}/${encodeURIComponent(opponentChampionId)}/metadata`,
        apiBaseUrl,
      );
      const response = await fetch(saveUrl, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${adminToken}`,
        },
        body: JSON.stringify({ video, metadata }),
      });
      if (response.status === 401) {
        throw new Error("管理者トークンが正しくありません。");
      }
      if (response.status === 403) {
        throw new Error(
          "サーバーで管理者機能が無効です（ADMIN_TOKEN が未設定です）。",
        );
      }
      if (!response.ok) {
        throw new Error("ビルド情報の保存に失敗しました。");
      }
      const savedMetadata = (await response.json()) as VideoMetadataAnalysis;
      setMatchupVideos((previous) =>
        previous.map((item) =>
          item.id === video.id
            ? { ...item, origin: "saved", metadata: savedMetadata }
            : item,
        ),
      );
    } finally {
      setSavingMetadata(false);
    }
  }

  async function handleLoadMoreCandidates() {
    if (!playerChampionId || !opponentChampionId || loadingCandidates) {
      return;
    }
    setLoadingCandidates(true);
    try {
      const voterToken = getOrCreateVoterToken();
      const matchupUrl = new URL(
        `/api/v1/matchups/${encodeURIComponent(playerChampionId)}/${encodeURIComponent(opponentChampionId)}`,
        apiBaseUrl,
      );
      matchupUrl.searchParams.set("includeCandidates", "true");
      if (voterToken) {
        matchupUrl.searchParams.set("voterToken", voterToken);
      }
      const response = await fetch(matchupUrl);
      if (response.ok) {
        const data = (await response.json()) as MatchupResponse;
        setMatchupVideos(data.items);
        if (!selectedVideoId && data.items[0]) {
          setSelectedVideoId(data.items[0].id);
        }
      }
    } finally {
      setSearchedCandidates(true);
      setLoadingCandidates(false);
    }
  }

  async function handleToggleUpvote(video: MatchupVideo) {
    if (!playerChampionId || !opponentChampionId || upvotingVideoId) {
      return;
    }

    setUpvotingVideoId(video.id);
    setError("");
    try {
      const voterToken = getOrCreateVoterToken();
      const upvoteUrl = new URL(
        `/api/v1/matchups/${encodeURIComponent(playerChampionId)}/${encodeURIComponent(opponentChampionId)}/upvote`,
        apiBaseUrl,
      );
      const response = await fetch(upvoteUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          video,
          voterToken,
        }),
      });
      if (!response.ok) {
        let errorMessage =
          "UVの保存に失敗しました。データベースの起動状態を確認してください。";
        try {
          const payload = (await response.json()) as {
            detail?: { message?: string };
          };
          if (payload.detail?.message) {
            errorMessage = payload.detail.message;
          }
        } catch {
          // Keep fallback error message.
        }
        throw new Error(errorMessage);
      }

      const updatedVideo = (await response.json()) as MatchupVideo;
      setMatchupVideos((previous) =>
        sortMatchupVideos(
          previous.map((item) =>
            item.id === video.id || item.videoUrl === updatedVideo.videoUrl
              ? updatedVideo
              : item,
          ),
        ),
      );
      setSelectedVideoId(updatedVideo.id);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "UVの保存に失敗しました。",
      );
    } finally {
      setUpvotingVideoId(null);
    }
  }

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
          {!loading &&
            !error &&
            !searchedCandidates &&
            matchupVideos.length > 0 &&
            matchupVideos.length < 5 && (
              <button
                type="button"
                className={styles.loadCandidatesButton}
                disabled={loadingCandidates}
                onClick={handleLoadMoreCandidates}
              >
                {loadingCandidates ? "候補を検索中..." : "+ YouTube候補を検索"}
              </button>
            )}
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

        {!loading && !error && activeVideo && (
          <>
            <div
              className={styles.videoSelector}
              role="tablist"
              aria-label="マッチアップ動画の切り替え"
            >
              {matchupVideos.map((video, index) => {
                const isSelected = video.id === activeVideo.id;
                const isYouTubeCandidate = video.origin === "youtube_search";
                const upvotes = video.upvoteCount ?? 0;
                return (
                  <button
                    key={video.id}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    className={`${styles.videoSelectorOption} ${
                      isSelected ? styles.videoSelectorOptionActive : ""
                    }`}
                    onClick={() => {
                      setSelectedVideoId(video.id);
                      setPlaybackStartSeconds(null);
                    }}
                    title={video.title}
                  >
                    <span className={styles.videoSelectorIndex}>
                      動画 {index + 1}
                    </span>
                    <span
                      className={`${styles.videoOriginBadge} ${
                        isYouTubeCandidate
                          ? styles.originCandidate
                          : styles.originSaved
                      }`}
                    >
                      {isYouTubeCandidate ? "YouTube検索" : "DB保存済"}
                    </span>
                    {upvotes > 0 && (
                      <span className={styles.videoSelectorVotes}>
                        ▲ {upvotes}
                      </span>
                    )}
                    {video.gamePatch && (
                      <span className={styles.videoSelectorPatch}>
                        Patch {video.gamePatch}
                      </span>
                    )}
                    <span className={styles.videoSelectorTitle}>
                      {video.title}
                    </span>
                  </button>
                );
              })}
            </div>

            <article
              className={`${styles.videoEmbedCard} ${styles.videoEmbedCardWithSelector}`}
            >
              {activeEmbedUrl && (
                <div className={styles.videoPlayerWrapper}>
                  <iframe
                    key={`${activeVideo.id}-${playbackStartSeconds ?? 0}`}
                    className={styles.videoPlayer}
                    src={activeEmbedUrl}
                    title={activeVideo.title}
                    loading="lazy"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allowFullScreen
                  />
                </div>
              )}

              <div className={styles.videoCardBody}>
                <div className={styles.videoInfo}>
                  <div className={styles.videoTitleRow}>
                    <span
                      className={`${styles.videoOriginBadge} ${
                        activeVideo.origin === "youtube_search"
                          ? styles.originCandidate
                          : styles.originSaved
                      }`}
                    >
                      {activeVideo.origin === "youtube_search"
                        ? "YouTube検索"
                        : "DB保存済"}
                    </span>
                    <h2 className={styles.videoTitle}>{activeVideo.title}</h2>
                  </div>
                  <dl className={styles.videoMeta}>
                    <div>
                      <dt>チャンネル</dt>
                      <dd>
                        <a
                          href={activeVideo.channelUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {activeVideo.channelName}（外部サイト）
                        </a>
                      </dd>
                    </div>
                    {activeVideo.gamePatch && (
                      <div>
                        <dt>パッチ</dt>
                        <dd>{activeVideo.gamePatch}</dd>
                      </div>
                    )}
                    {activeVideo.publishedAt && (
                      <div>
                        <dt>公開日</dt>
                        <dd>{formatIsoDate(activeVideo.publishedAt)}</dd>
                      </div>
                    )}
                    <div>
                      <dt>確認日</dt>
                      <dd>{formatIsoDate(activeVideo.verifiedAt)}</dd>
                    </div>
                    <div>
                      <dt>出典</dt>
                      <dd>
                        <a
                          href={activeVideo.sourceUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          確認元ページ（外部サイト）
                        </a>
                      </dd>
                    </div>
                  </dl>
                </div>

                <div className={styles.videoActions}>
                  <button
                    type="button"
                    className={`${styles.upvoteButton} ${
                      activeVideo.upvotedByViewer ? styles.upvoteButtonActive : ""
                    }`}
                    aria-pressed={Boolean(activeVideo.upvotedByViewer)}
                    disabled={upvotingVideoId === activeVideo.id}
                    onClick={() => handleToggleUpvote(activeVideo)}
                  >
                    <span>{activeVideo.upvotedByViewer ? "▲ UV済" : "△ UV"}</span>
                    <strong>{activeVideo.upvoteCount ?? 0}</strong>
                  </button>
                  <a
                    className={styles.videoLink}
                    href={activeVideo.videoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    YouTubeで視聴（外部サイト・新しいタブ）
                  </a>
                </div>
              </div>

              <VideoMetadataPanel
                metadata={activeVideo.metadata}
                gameAssets={gameAssets}
                analyzing={analyzingVideoId === activeVideo.id}
                savingManual={savingMetadata}
                onAnalyzeDescription={(refresh) =>
                  handleAnalyzeVideo(activeVideo, refresh)
                }
                onSaveManualMetadata={(updated, adminToken) =>
                  handleSaveManualMetadata(activeVideo, updated, adminToken)
                }
                onJumpToTimestamp={(seconds) => {
                  setPlaybackStartSeconds(seconds);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            </article>
          </>
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
