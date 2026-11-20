"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { RiotFooter } from "@/components/RiotFooter";
import { VideoMetadataPanel } from "@/components/VideoMetadataPanel";
import { WaveStrip } from "@/components/WaveStrip";
import {
  apiBaseUrl,
  formatIsoDate,
  getOrCreateVoterToken,
  getYouTubeEmbedUrl,
  matchupApiUrl,
  putAsAdmin,
  readErrorMessage,
  type Champion,
  type ChampionResponse,
  type BuildSavePayload,
  type GameAssetsCatalog,
  type MatchupResponse,
  type MatchupVideo,
  type VideoMetadataAnalysis,
  type WaveNote,
} from "@/lib/api";
import { useYouTubePlayer } from "@/lib/youtubePlayer";
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
  const [upvotingVideoId, setUpvotingVideoId] = useState<string | null>(null);
  const [analyzingVideoId, setAnalyzingVideoId] = useState<string | null>(null);
  const [savingMetadata, setSavingMetadata] = useState(false);
  const [savingWaves, setSavingWaves] = useState(false);
  const [error, setError] = useState("");
  const [playerFrame, setPlayerFrame] = useState<HTMLIFrameElement | null>(null);
  const [buildEditing, setBuildEditing] = useState(false);
  // The player API is only loaded while the build editor is open (its timeline reads the
  // playback position), so ordinary viewing never pulls in the extra script.
  const player = useYouTubePlayer(buildEditing ? playerFrame : null);

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

      try {
        const voterToken = getOrCreateVoterToken();
        const championsUrl = new URL("/api/v1/champions", apiBaseUrl);
        const gameAssetsUrl = new URL("/api/v1/game-assets", apiBaseUrl);
        const matchupUrl = matchupApiUrl(playerChampionId, opponentChampionId);
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
          throw new Error(
            await readErrorMessage(
              matchupResponse,
              "マッチアップ情報を取得できませんでした。APIの起動状態を確認してください。",
            ),
          );
        }

        const matchupData = (await matchupResponse.json()) as MatchupResponse;
        setMatchupVideos(matchupData.items);
        setSelectedVideoId(matchupData.items[0]?.id ?? null);
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
      const analyzeUrl = matchupApiUrl(playerChampionId, opponentChampionId, "/analyze");
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
    metadata: BuildSavePayload,
    adminToken: string,
  ) {
    if (!playerChampionId || !opponentChampionId || savingMetadata) {
      return;
    }
    setSavingMetadata(true);
    try {
      const savedMetadata = await putAsAdmin<VideoMetadataAnalysis>(
        matchupApiUrl(playerChampionId, opponentChampionId, "/metadata"),
        { video, metadata },
        adminToken,
        "ビルド情報の保存に失敗しました。",
      );
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

  async function handleSaveWaves(
    video: MatchupVideo,
    waves: WaveNote[],
    adminToken: string,
  ) {
    if (!playerChampionId || !opponentChampionId || savingWaves) {
      return;
    }
    setSavingWaves(true);
    try {
      const saved = await putAsAdmin<VideoMetadataAnalysis>(
        matchupApiUrl(playerChampionId, opponentChampionId, "/waves"),
        { video, waves },
        adminToken,
        "ウェーブ情報の保存に失敗しました。",
      );
      setMatchupVideos((previous) =>
        previous.map((item) =>
          item.id === video.id
            ? {
                ...item,
                origin: "saved",
                metadata: {
                  ...(item.metadata ?? saved),
                  waves: saved.waves,
                },
              }
            : item,
        ),
      );
    } finally {
      setSavingWaves(false);
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
      const upvoteUrl = matchupApiUrl(playerChampionId, opponentChampionId, "/upvote");
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
        throw new Error(
          await readErrorMessage(
            response,
            "UVの保存に失敗しました。データベースの起動状態を確認してください。",
          ),
        );
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
                <div className={styles.videoPlayerFrame}>
                  <div className={styles.videoPlayerWrapper}>
                    <iframe
                      ref={setPlayerFrame}
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

              <WaveStrip
                key={activeVideo.id}
                waves={activeVideo.metadata?.waves ?? []}
                saving={savingWaves}
                onSave={(waves, adminToken) =>
                  handleSaveWaves(activeVideo, waves, adminToken)
                }
              />

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
                playerReady={player.ready}
                currentTime={player.currentTime}
                onEditingChange={setBuildEditing}
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
