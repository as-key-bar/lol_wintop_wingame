export type Champion = {
  id: string;
  nameJa: string;
  nameEn: string;
  aliases: string[];
  imageUrl: string;
};

export type ChampionResponse = {
  dataDragonVersion: string;
  items: Champion[];
};

export type MatchupVideo = {
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
  origin?: "saved" | "youtube_search";
  upvoteCount?: number;
  upvotedByViewer?: boolean;
};

export type MatchupResponse = {
  playerChampionId: string;
  opponentChampionId: string;
  items: MatchupVideo[];
};

export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function formatIsoDate(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value.trim());
  return match ? match[1] : value;
}

export function getYouTubeEmbedUrl(videoUrl: string): string | null {
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

const VOTER_TOKEN_STORAGE_KEY = "wintop_voter_token";

export function getOrCreateVoterToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    const existing = window.localStorage.getItem(VOTER_TOKEN_STORAGE_KEY);
    if (existing && existing.trim()) {
      return existing.trim();
    }
    const created =
      typeof window.crypto?.randomUUID === "function"
        ? window.crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    window.localStorage.setItem(VOTER_TOKEN_STORAGE_KEY, created);
    return created;
  } catch {
    return "ephemeral-voter";
  }
}

