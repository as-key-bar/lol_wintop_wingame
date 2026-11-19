import { afterEach, describe, expect, it, vi } from "vitest";
import { formatIsoDate, getOrCreateVoterToken, getYouTubeEmbedUrl } from "./api";

describe("getYouTubeEmbedUrl", () => {
  function parts(url: string | null) {
    const parsed = new URL(url as string);
    return { path: parsed.origin + parsed.pathname, params: parsed.searchParams };
  }

  it("builds an embed URL from a watch URL with the JS API enabled", () => {
    const { path, params } = parts(
      getYouTubeEmbedUrl("https://www.youtube.com/watch?v=abc123"),
    );

    expect(path).toBe("https://www.youtube.com/embed/abc123");
    expect(params.get("enablejsapi")).toBe("1");
    expect(params.get("origin")).toBe(window.location.origin);
    expect(params.has("start")).toBe(false);
    expect(params.has("autoplay")).toBe(false);
  });

  it("adds a start offset and autoplay when seconds are given", () => {
    const { params } = parts(
      getYouTubeEmbedUrl("https://www.youtube.com/watch?v=abc123", 95.9),
    );

    expect(params.get("start")).toBe("95");
    expect(params.get("autoplay")).toBe("1");
    expect(params.get("enablejsapi")).toBe("1");
  });

  it("ignores a zero start offset", () => {
    const { params } = parts(
      getYouTubeEmbedUrl("https://www.youtube.com/watch?v=abc123", 0),
    );

    expect(params.has("start")).toBe(false);
  });

  it("returns null when the URL has no video id or is invalid", () => {
    expect(getYouTubeEmbedUrl("https://www.youtube.com/watch")).toBeNull();
    expect(getYouTubeEmbedUrl("not a url")).toBeNull();
  });
});

describe("formatIsoDate", () => {
  it("keeps only the date part of an ISO timestamp", () => {
    expect(formatIsoDate("2026-11-11T11:40:00+09:00")).toBe("2026-11-11");
  });

  it("returns the input when it does not start with a date", () => {
    expect(formatIsoDate("unknown")).toBe("unknown");
  });
});

describe("getOrCreateVoterToken", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("creates a token once and reuses it", () => {
    const first = getOrCreateVoterToken();
    expect(first).not.toBe("");
    expect(getOrCreateVoterToken()).toBe(first);
  });

  it("falls back to an ephemeral token when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getOrCreateVoterToken()).toBe("ephemeral-voter");
  });
});

describe("apiBaseUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("falls back to the local API when the variable is unset", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", undefined as unknown as string);
    vi.resetModules();
    const { apiBaseUrl } = await import("./api");
    expect(apiBaseUrl).toBe("http://localhost:8000");
  });

  it("uses the page origin when the variable is empty (same-origin deployment)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    vi.resetModules();
    const { apiBaseUrl } = await import("./api");
    expect(apiBaseUrl).toBe(window.location.origin);
  });

  it("uses an explicit URL when one is given", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com");
    vi.resetModules();
    const { apiBaseUrl } = await import("./api");
    expect(apiBaseUrl).toBe("https://api.example.com");
  });
});
