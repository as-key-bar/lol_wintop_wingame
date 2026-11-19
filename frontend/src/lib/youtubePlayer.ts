"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// The subset of the YouTube IFrame Player API this app uses.
// Reference: https://developers.google.com/youtube/iframe_api_reference
export type YouTubePlayer = {
  getCurrentTime: () => number;
  seekTo: (seconds: number, allowSeekAhead: boolean) => void;
  pauseVideo: () => void;
  playVideo: () => void;
  getPlayerState: () => number;
  destroy: () => void;
};

type YouTubeNamespace = {
  Player: new (
    element: HTMLIFrameElement,
    options: { events: { onReady: () => void } },
  ) => YouTubePlayer;
};

declare global {
  interface Window {
    YT?: YouTubeNamespace;
    onYouTubeIframeAPIReady?: () => void;
  }
}

const API_SRC = "https://www.youtube.com/iframe_api";
let apiPromise: Promise<YouTubeNamespace> | null = null;

function loadYouTubeApi(): Promise<YouTubeNamespace> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("no window"));
  }
  if (window.YT?.Player) {
    return Promise.resolve(window.YT);
  }
  if (!apiPromise) {
    apiPromise = new Promise<YouTubeNamespace>((resolve, reject) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        previous?.();
        if (window.YT?.Player) {
          resolve(window.YT);
        } else {
          reject(new Error("YouTube API did not load"));
        }
      };
      const script = document.createElement("script");
      script.src = API_SRC;
      script.async = true;
      script.onerror = () => {
        apiPromise = null;
        reject(new Error("YouTube API script failed to load"));
      };
      document.head.appendChild(script);
    });
  }
  return apiPromise;
}

export type PlayerControls = {
  ready: boolean;
  failed: boolean;
  currentTime: () => number | null;
  seekAndPause: (seconds: number) => void;
};

// Controls the player inside the given iframe. It only reads the time and seeks and pauses;
// it does not modify the player's UI or its standard playback.
export function useYouTubePlayer(
  iframe: HTMLIFrameElement | null,
): PlayerControls {
  const playerRef = useRef<YouTubePlayer | null>(null);
  // The state is keyed by the iframe it belongs to, so a new iframe starts as "not ready"
  // without resetting state from inside the effect.
  const [state, setState] = useState<{
    frame: HTMLIFrameElement | null;
    ready: boolean;
    failed: boolean;
  }>({ frame: null, ready: false, failed: false });

  useEffect(() => {
    playerRef.current = null;
    if (!iframe) {
      return undefined;
    }
    let cancelled = false;
    loadYouTubeApi()
      .then((YT) => {
        if (cancelled) {
          return;
        }
        playerRef.current = new YT.Player(iframe, {
          events: {
            onReady: () => {
              if (!cancelled) {
                setState({ frame: iframe, ready: true, failed: false });
              }
            },
          },
        });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ frame: iframe, ready: false, failed: true });
        }
      });
    return () => {
      cancelled = true;
      playerRef.current = null;
    };
  }, [iframe]);

  const currentTime = useCallback((): number | null => {
    const player = playerRef.current;
    return player ? Math.floor(player.getCurrentTime()) : null;
  }, []);

  const seekAndPause = useCallback((seconds: number) => {
    const player = playerRef.current;
    if (!player) {
      return;
    }
    player.seekTo(Math.max(0, seconds), true);
    player.pauseVideo();
  }, []);

  const current = state.frame === iframe && iframe !== null;
  return {
    ready: current && state.ready,
    failed: current && state.failed,
    currentTime,
    seekAndPause,
  };
}
