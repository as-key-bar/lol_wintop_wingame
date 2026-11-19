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

export type RuneSelection = {
  primaryStyleId: number | null;
  subStyleId: number | null;
  primarySelections: number[];
  subSelections: number[];
  statShards: number[];
};

export type VideoTimestamp = {
  timeSeconds: number;
  timeLabel: string;
  label: string;
  isKillEvent: boolean;
};

export type WaveState = "push" | "pull" | "neutral" | "unknown";

export type WaveNote = {
  waveNumber: number;
  timeSeconds: number;
  state: WaveState;
};

export type VideoMetadataAnalysis = {
  analysisStatus: "unanalyzed" | "auto_parsed" | "manual_verified";
  runes: RuneSelection | null;
  summonerSpells: string[];
  startingItems: string[];
  timestamps: VideoTimestamp[];
  // Waves have their own save (PUT /waves). They are read back with the metadata, but saving the
  // build never sends them, so a build edit cannot overwrite wave input or the other way round.
  waves: WaveNote[];
  firstWaveSeconds: number | null;
};

export type BuildSavePayload = Omit<VideoMetadataAnalysis, "waves" | "firstWaveSeconds">;

export type RuneAsset = {
  id: number;
  key: string;
  nameJa: string;
  nameEn: string;
  aliases?: string[];
  iconUrl: string;
  slotIndex: number;
};

export type RuneSlotAsset = {
  slotIndex: number;
  runes: RuneAsset[];
};

export type RuneStyleAsset = {
  id: number;
  key: string;
  nameJa: string;
  nameEn: string;
  iconUrl: string;
  slots: RuneSlotAsset[];
};

export type StatShardAsset = {
  id: number;
  key: string;
  nameJa: string;
  nameEn: string;
  iconUrl: string;
};

export type SummonerSpellAsset = {
  id: string;
  key: string;
  nameJa: string;
  nameEn: string;
  iconUrl: string;
};

export type StarterItemAsset = {
  id: string;
  nameJa: string;
  nameEn: string;
  gold: number;
  iconUrl: string;
};

export type GameAssetsCatalog = {
  dataDragonVersion: string;
  sourceUrl: string;
  runeStyles: RuneStyleAsset[];
  statShardRows: StatShardAsset[][];
  summonerSpells: SummonerSpellAsset[];
  starterItems: StarterItemAsset[];
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
  metadata?: VideoMetadataAnalysis | null;
};

export type MatchupResponse = {
  playerChampionId: string;
  opponentChampionId: string;
  items: MatchupVideo[];
};

// An empty NEXT_PUBLIC_API_BASE_URL means "same origin" (production behind the
// reverse proxy); unset falls back to the local API for development.
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

function resolveApiBaseUrl(): string {
  if (configuredApiBaseUrl === undefined) {
    return "http://localhost:8000";
  }
  if (configuredApiBaseUrl === "") {
    return typeof window === "undefined"
      ? "http://localhost:3000"
      : window.location.origin;
  }
  return configuredApiBaseUrl;
}

export const apiBaseUrl = resolveApiBaseUrl();

export function formatIsoDate(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value.trim());
  return match ? match[1] : value;
}

export function getYouTubeEmbedUrl(
  videoUrl: string,
  startSeconds?: number | null,
): string | null {
  try {
    const parsed = new URL(videoUrl);
    const videoId = parsed.searchParams.get("v")?.trim();
    if (!videoId) {
      return null;
    }
    const base = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}`;
    // enablejsapi lets the page read the playback time and seek (wave tagging).
    const params = new URLSearchParams({ enablejsapi: "1" });
    if (typeof window !== "undefined") {
      params.set("origin", window.location.origin);
    }
    if (typeof startSeconds === "number" && startSeconds > 0) {
      params.set("start", String(Math.floor(startSeconds)));
      params.set("autoplay", "1");
    }
    return `${base}?${params.toString()}`;
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

