import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    """In-memory per-key limiter. Single process only, which matches the single-EC2 deployment."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = 0.0

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_sweep > 300:
                self._sweep(now, window_seconds)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def _sweep(self, now: float, window_seconds: float) -> None:
        self._last_sweep = now
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] > window_seconds]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    # Caddy sets X-Forwarded-For and uvicorn applies it (--proxy-headers) to request.client.
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window_seconds: float):
    """FastAPI dependency factory. Limits are scaled by RATE_LIMIT_MULTIPLIER (0 disables)."""

    def dependency(request: Request) -> None:
        multiplier = float(os.getenv("RATE_LIMIT_MULTIPLIER", "1"))
        if multiplier <= 0:
            return
        allowed = limiter.allow(
            f"{name}:{client_ip(request)}", max(1, int(limit * multiplier)), window_seconds
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "message": "リクエストが多すぎます。しばらくしてからもう一度お試しください。",
                },
                headers={"Retry-After": str(int(window_seconds))},
            )

    return dependency
