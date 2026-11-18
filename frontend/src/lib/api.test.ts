import { afterEach, describe, expect, it, vi } from "vitest";
import { formatIsoDate, getOrCreateVoterToken, getYouTubeEmbedUrl } from "./api";

describe("getYouTubeEmbedUrl", () => {
  it("builds an embed URL from a watch URL", () => {
    expect(getYouTubeEmbedUrl("https://www.youtube.com/watch?v=abc123")).toBe(
      "https://www.youtube.com/embed/abc123",
    );
  });

  it("adds a start offset and autoplay when seconds are given", () => {
    expect(
      getYouTubeEmbedUrl("https://www.youtube.com/watch?v=abc123", 95.9),
    ).toBe("https://www.youtube.com/embed/abc123?start=95&autoplay=1");
  });

  it("ignores a zero start offset", () => {
    expect(
      getYouTubeEmbedUrl("https://www.youtube.com/watch?v=abc123", 0),
    ).toBe("https://www.youtube.com/embed/abc123");
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
