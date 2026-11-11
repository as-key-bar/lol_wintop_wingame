import json
import logging
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from app.champions import Champion

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"
YOUTUBE_API_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


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
    match = re.search(r"(?:Patch\s+|パッチ)([0-9]+\.[0-9]+)", title, re.IGNORECASE)
    return match.group(1) if match else None


def title_matches_matchup(
    title: str, player: Champion, opponent: Champion
) -> bool:
    normalized = title.casefold()
    player_names = {
        player.id.casefold(),
        player.nameEn.casefold(),
        player.nameJa.casefold(),
        *(alias.casefold() for alias in player.aliases),
    }
    opponent_names = {
        opponent.id.casefold(),
        opponent.nameEn.casefold(),
        opponent.nameJa.casefold(),
        *(alias.casefold() for alias in opponent.aliases),
    }

    vs_split = re.split(r"\bvs\.?\b|対", normalized, maxsplit=1)
    if len(vs_split) == 2:
        left_part, right_part = vs_split
        has_player_left = any(name in left_part for name in player_names if name)
        has_opponent_right = any(
            name in right_part for name in opponent_names if name
        )
        if has_player_left and has_opponent_right:
            return True
        return False

    return any(name in normalized for name in player_names if name) and any(
        name in normalized for name in opponent_names if name
    )


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
    results: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()

    for renderer in renderers:
        video_id = renderer.get("videoId")
        if not isinstance(video_id, str) or not video_id.strip():
            continue
        video_id = video_id.strip()
        if video_id in seen_video_ids:
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
        results.append(
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
        if len(results) >= max_results:
            break

    return results


def _search_via_data_api(
    api_key: str,
    query: str,
    player: Champion,
    opponent: Champion,
    max_results: int,
) -> list[dict[str, Any]]:
    params = urlencode(
        {
            "part": "snippet",
            "type": "video",
            "videoEmbeddable": "true",
            "maxResults": max(max_results * 2, 10),
            "q": query,
            "key": api_key,
        }
    )
    request_url = f"{YOUTUBE_API_SEARCH_URL}?{params}"
    public_source_url = f"{YOUTUBE_SEARCH_URL}?search_query={quote_plus(query)}"
    payload = json.loads(_fetch_text(request_url))

    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    results: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        title = (snippet.get("title") or "").strip()
        if not video_id or not title:
            continue
        if not title_matches_matchup(title, player, opponent):
            continue

        channel_id = (snippet.get("channelId") or "").strip()
        channel_url = (
            f"https://www.youtube.com/channel/{channel_id}"
            if channel_id
            else "https://www.youtube.com"
        )
        published_at = (snippet.get("publishedAt") or "").strip() or None
        results.append(
            {
                "id": f"yt-{player.id.lower()}-vs-{opponent.id.lower()}-{video_id}",
                "playerChampionId": player.id,
                "opponentChampionId": opponent.id,
                "title": title,
                "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
                "channelName": (snippet.get("channelTitle") or "YouTube").strip(),
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
        if len(results) >= max_results:
            break

    return results


@lru_cache(maxsize=256)
def _cached_youtube_search(
    player_id: str,
    opponent_id: str,
    max_results: int,
) -> tuple[dict[str, Any], ...]:
    from app.champions import load_catalog

    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    player = by_id[player_id]
    opponent = by_id[opponent_id]

    query = f'"{player.nameEn} Top vs {opponent.nameEn}" Challenger Replays'
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        items = _search_via_data_api(api_key, query, player, opponent, max_results)
        return tuple(items)

    search_url = f"{YOUTUBE_SEARCH_URL}?search_query={quote_plus(query)}"
    html_text = _fetch_text(search_url)
    items = parse_youtube_initial_data(
        html_text=html_text,
        player=player,
        opponent=opponent,
        source_url=search_url,
        max_results=max_results,
    )
    return tuple(items)


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
    except Exception:
        logger.warning(
            "YouTube candidate search failed for %s vs %s",
            player_champion_id,
            opponent_champion_id,
            exc_info=True,
        )
        return []

