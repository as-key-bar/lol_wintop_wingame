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

