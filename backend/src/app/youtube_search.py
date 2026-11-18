import html
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from collections import OrderedDict
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from app.champions import Champion

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"
YOUTUBE_API_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_API_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
MIN_REPLAY_DURATION_SECONDS = 600

NON_TOP_LANE_PATTERN = re.compile(
    r"\b(?:mid|middle|jungle|jg|bot|bottom|adc|support|sup|aram)\b"
    r"|ミッド|ジャングル|ボット|サポート",
    re.IGNORECASE,
)
TOP_LANE_PATTERN = re.compile(r"\btop\b|トップ", re.IGNORECASE)
EXCLUDED_VIDEO_PATTERN = re.compile(
    r"\b(?:shorts|montage|highlights|compilation)\b|#shorts",
    re.IGNORECASE,
)


def _fetch_text(url: str, timeout: float = 8.0) -> str:
    request = Request(
        url,
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) wintop-wingame/0.1",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def extract_patch_from_title(title: str) -> str | None:
    match = re.search(
        r"(?:Patch\s+|パッチ\s*)([0-9]+(?:\.[0-9]+)+)", title, re.IGNORECASE
    )
    return match.group(1) if match else None


def parse_patch_tuple(patch: str | None) -> tuple[int, ...]:
    if not patch:
        return (0, 0)
    parts = [int(part) for part in patch.split(".") if part.isdigit()]
    return tuple(parts) if parts else (0, 0)


def extract_rank_tier_score(title: str) -> int:
    normalized = title.casefold()
    if "challenger" in normalized or "チャレンジャー" in normalized:
        return 3
    if "grandmaster" in normalized or "グランドマスター" in normalized:
        return 2
    if "master" in normalized or "マスター" in normalized:
        return 1
    return 0


def extract_channel_trust_score(channel_name: str) -> int:
    normalized = channel_name.casefold()
    if "challenger replays" in normalized or "domisumreplay" in normalized:
        return 2
    if "replay" in normalized or "vod" in normalized:
        return 1
    return 0


ISO8601_DURATION_PATTERN = re.compile(
    r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$"
)


def parse_iso8601_duration(value: str | None) -> int | None:
    """Parse the contentDetails.duration format of the YouTube Data API (e.g. PT26M5S)."""
    if not value:
        return None
    match = ISO8601_DURATION_PATTERN.fullmatch(value.strip().upper())
    if not match:
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def parse_duration_seconds(duration_text: str | None) -> int | None:
    if not duration_text:
        return None
    cleaned = duration_text.strip().upper()
    if cleaned == "SHORTS":
        return 0
    if not re.fullmatch(r"\d+(?::\d{2}){1,2}", cleaned):
        return None
    parts = [int(part) for part in cleaned.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    return None


def _contains_champion_name(segment: str, champion: Champion) -> bool:
    candidates = {
        champion.id,
        champion.nameEn,
        champion.nameJa,
        *champion.aliases,
    }
    for name in candidates:
        cleaned = name.strip()
        if not cleaned:
            continue
        if cleaned.isascii():
            pattern = rf"(?<![a-z0-9]){re.escape(cleaned.casefold())}(?![a-z0-9])"
            if re.search(pattern, segment.casefold()):
                return True
        else:
            if cleaned.casefold() in segment.casefold():
                return True
    return False


def title_matches_matchup(
    title: str, player: Champion, opponent: Champion
) -> bool:
    if EXCLUDED_VIDEO_PATTERN.search(title):
        return False
    if NON_TOP_LANE_PATTERN.search(title):
        return False
    if not TOP_LANE_PATTERN.search(title):
        return False

    vs_split = re.split(r"\bvs\.?\b|対", title, maxsplit=1, flags=re.IGNORECASE)
    if len(vs_split) != 2:
        return False

    left_part, right_part = vs_split
    return _contains_champion_name(left_part, player) and _contains_champion_name(
        right_part, opponent
    )


def score_candidate(item: dict[str, Any]) -> tuple[tuple[int, ...], int, int]:
    patch_score = parse_patch_tuple(item.get("gamePatch"))
    rank_score = extract_rank_tier_score(item.get("title", ""))
    channel_score = extract_channel_trust_score(item.get("channelName", ""))
    return (patch_score, rank_score, channel_score)


def _extract_renderer_duration_text(renderer: dict[str, Any]) -> str | None:
    length_text = renderer.get("lengthText", {})
    if isinstance(length_text, dict):
        if isinstance(length_text.get("simpleText"), str):
            return length_text["simpleText"]
        runs = length_text.get("runs")
        if isinstance(runs, list) and runs:
            joined = "".join(
                run.get("text", "") for run in runs if isinstance(run, dict)
            ).strip()
            if joined:
                return joined

    overlays = renderer.get("thumbnailOverlays", [])
    if isinstance(overlays, list):
        for overlay in overlays:
            if not isinstance(overlay, dict):
                continue
            status = overlay.get("thumbnailOverlayTimeStatusRenderer", {})
            if not isinstance(status, dict):
                continue
            style = status.get("style")
            if style == "SHORTS":
                return "SHORTS"
            text_obj = status.get("text", {})
            if isinstance(text_obj, dict) and isinstance(
                text_obj.get("simpleText"), str
            ):
                return text_obj["simpleText"]
    return None


def parse_youtube_initial_data(
    html_text: str,
    player: Champion,
    opponent: Champion,
    source_url: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", html_text)
    if not match:
        return []

    data = json.loads(match.group(1))
    renderers: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "videoRenderer" in node and isinstance(node["videoRenderer"], dict):
                renderers.append(node["videoRenderer"])
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data.get("contents", {}))

    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    candidates: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()

    for renderer in renderers:
        video_id = renderer.get("videoId")
        if not isinstance(video_id, str) or not video_id.strip():
            continue
        video_id = video_id.strip()
        if video_id in seen_video_ids:
            continue

        duration_text = _extract_renderer_duration_text(renderer)
        duration_seconds = parse_duration_seconds(duration_text)
        if (
            duration_seconds is not None
            and duration_seconds < MIN_REPLAY_DURATION_SECONDS
        ):
            continue

        title_runs = renderer.get("title", {}).get("runs", [])
        title = (
            "".join(run.get("text", "") for run in title_runs).strip()
            if isinstance(title_runs, list)
            else ""
        )
        if not title or not title_matches_matchup(title, player, opponent):
            continue

        owner_runs = (
            renderer.get("ownerText", {}).get("runs")
            or renderer.get("longBylineText", {}).get("runs")
            or []
        )
        channel_name = "YouTube"
        channel_url = "https://www.youtube.com"
        if isinstance(owner_runs, list) and owner_runs:
            first_run = owner_runs[0]
            if isinstance(first_run.get("text"), str) and first_run["text"].strip():
                channel_name = first_run["text"].strip()
            canonical_base = (
                first_run.get("navigationEndpoint", {})
                .get("browseEndpoint", {})
                .get("canonicalBaseUrl")
            )
            browse_id = (
                first_run.get("navigationEndpoint", {})
                .get("browseEndpoint", {})
                .get("browseId")
            )
            if isinstance(canonical_base, str) and canonical_base.startswith("/"):
                channel_url = f"https://www.youtube.com{canonical_base}"
            elif isinstance(browse_id, str) and browse_id.strip():
                channel_url = f"https://www.youtube.com/channel/{browse_id.strip()}"

        seen_video_ids.add(video_id)
        candidates.append(
            {
                "id": f"yt-{player.id.lower()}-vs-{opponent.id.lower()}-{video_id}",
                "playerChampionId": player.id,
                "opponentChampionId": opponent.id,
                "title": title,
                "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
                "channelName": channel_name,
                "channelUrl": channel_url,
                "publishedAt": None,
                "gamePatch": extract_patch_from_title(title),
                "verifiedAt": now_iso,
                "verificationStatus": "verified",
                "embedStatus": "unknown",
                "sourceUrl": source_url,
                "origin": "youtube_search",
            }
        )

    candidates.sort(key=score_candidate, reverse=True)
    return candidates[:max_results]


def _fetch_durations_via_data_api(api_key: str, video_ids: list[str]) -> dict[str, int]:
    """videos.list costs 1 quota unit per call for up to 50 ids."""
    if not video_ids:
        return {}
    params = urlencode(
        {"part": "contentDetails", "id": ",".join(video_ids[:50]), "key": api_key}
    )
    payload = json.loads(_fetch_text(f"{YOUTUBE_API_VIDEOS_URL}?{params}"))
    durations: dict[str, int] = {}
    for item in payload.get("items", []):
        seconds = parse_iso8601_duration(item.get("contentDetails", {}).get("duration"))
        if item.get("id") and seconds is not None:
            durations[item["id"]] = seconds
    return durations


def _search_via_data_api(
    api_key: str,
    query: str,
    player: Champion,
    opponent: Champion,
    max_results: int,
) -> list[dict[str, Any]]:
    # No videoDuration filter: "medium" means 4 to 20 minutes and would drop most full
    # replays. Length is checked afterwards from contentDetails instead.
    params = urlencode(
        {
            "part": "snippet",
            "type": "video",
            "videoEmbeddable": "true",
            "maxResults": max(max_results * 5, 25),
            "q": query,
            "key": api_key,
        }
    )
    request_url = f"{YOUTUBE_API_SEARCH_URL}?{params}"
    public_source_url = f"{YOUTUBE_SEARCH_URL}?search_query={quote_plus(query)}"
    payload = json.loads(_fetch_text(request_url))

    matched: list[tuple[str, str, dict[str, Any]]] = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        # The Data API returns titles HTML-escaped (Cho&#39;Gath); unescape before matching.
        title = html.unescape(snippet.get("title") or "").strip()
        if not video_id or not title:
            continue
        if not title_matches_matchup(title, player, opponent):
            continue
        matched.append((video_id, title, snippet))

    durations = _fetch_durations_via_data_api(api_key, [m[0] for m in matched])

    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    candidates: list[dict[str, Any]] = []
    for video_id, title, snippet in matched:
        # Unknown length is dropped too, mirroring the HTML path's 10 minute minimum.
        if durations.get(video_id, 0) < MIN_REPLAY_DURATION_SECONDS:
            continue
        channel_id = (snippet.get("channelId") or "").strip()
        channel_url = (
            f"https://www.youtube.com/channel/{channel_id}"
            if channel_id
            else "https://www.youtube.com"
        )
        published_at = (snippet.get("publishedAt") or "").strip() or None
        candidates.append(
            {
                "id": f"yt-{player.id.lower()}-vs-{opponent.id.lower()}-{video_id}",
                "playerChampionId": player.id,
                "opponentChampionId": opponent.id,
                "title": title,
                "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
                "channelName": html.unescape(snippet.get("channelTitle") or "YouTube").strip(),
                "channelUrl": channel_url,
                "publishedAt": published_at,
                "gamePatch": extract_patch_from_title(title),
                "verifiedAt": now_iso,
                "verificationStatus": "verified",
                "embedStatus": "allowed",
                "sourceUrl": public_source_url,
                "origin": "youtube_search",
            }
        )

    candidates.sort(key=score_candidate, reverse=True)
    return candidates[:max_results]


def build_search_query(player: Champion, opponent: Champion) -> str:
    return f'"{player.nameEn} Top vs {opponent.nameEn}"'


SEARCH_CACHE_MAX_ENTRIES = 256
SEARCH_CACHE_TTL_SECONDS = 6 * 3600
# A failed or empty lookup must not stick for hours; retry soon.
EMPTY_RESULT_TTL_SECONDS = 120
_search_cache: "OrderedDict[tuple[str, str, int], tuple[float, tuple[dict[str, Any], ...]]]" = OrderedDict()
_search_cache_lock = threading.Lock()


def clear_search_cache() -> None:
    with _search_cache_lock:
        _search_cache.clear()


def _search_uncached(
    player_id: str, opponent_id: str, max_results: int
) -> tuple[dict[str, Any], ...]:
    from app.champions import load_catalog

    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    player = by_id[player_id]
    opponent = by_id[opponent_id]

    query = build_search_query(player, opponent)
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        return tuple(_search_via_data_api(api_key, query, player, opponent, max_results))

    search_url = f"{YOUTUBE_SEARCH_URL}?search_query={quote_plus(query)}"
    html_text = _fetch_text(search_url)
    return tuple(
        parse_youtube_initial_data(
            html_text=html_text,
            player=player,
            opponent=opponent,
            source_url=search_url,
            max_results=max_results,
        )
    )


def _ttl_for(items: tuple[dict[str, Any], ...]) -> int:
    return SEARCH_CACHE_TTL_SECONDS if items else EMPTY_RESULT_TTL_SECONDS


def _cached_youtube_search(
    player_id: str, opponent_id: str, max_results: int
) -> tuple[dict[str, Any], ...]:
    key = (player_id, opponent_id, max_results)
    now = time.monotonic()
    with _search_cache_lock:
        entry = _search_cache.get(key)
        if entry and now - entry[0] < _ttl_for(entry[1]):
            _search_cache.move_to_end(key)
            return entry[1]

    items = _search_uncached(player_id, opponent_id, max_results)
    with _search_cache_lock:
        _search_cache[key] = (now, items)
        _search_cache.move_to_end(key)
        while len(_search_cache) > SEARCH_CACHE_MAX_ENTRIES:
            _search_cache.popitem(last=False)
    return items


def was_offered_as_candidate(
    player_champion_id: str, opponent_champion_id: str, video_url: str
) -> bool:
    """True if this server's own search returned the video for this matchup.

    Reads the cache only, so it never triggers an outbound request.
    """
    now = time.monotonic()
    with _search_cache_lock:
        for (player_id, opponent_id, _), (stored_at, items) in _search_cache.items():
            if (player_id, opponent_id) != (player_champion_id, opponent_champion_id):
                continue
            if now - stored_at >= _ttl_for(items):
                continue
            if any(item.get("videoUrl") == video_url for item in items):
                return True
    return False


def search_youtube_matchup_candidates(
    player_champion_id: str,
    opponent_champion_id: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    try:
        return list(
            _cached_youtube_search(
                player_champion_id, opponent_champion_id, max_results
            )
        )
    except Exception as error:
        # Never log the request URL: it carries the API key.
        logger.warning(
            "YouTube candidate search failed for %s vs %s: %s: %s",
            player_champion_id,
            opponent_champion_id,
            type(error).__name__,
            str(error)[:200],
        )
        return []
