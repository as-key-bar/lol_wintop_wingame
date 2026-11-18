import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
CHAMPIONS_PATH = ROOT_DIR / "backend/src/app/data/champions.json"
OUTPUT_PATH = ROOT_DIR / "backend/src/app/data/matchups.json"

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

EXTRA_CHAMPION_ALIASES = {
    "カミーユ": "Camille",
    "アトロックス": "Aatrox",
}


def extract_playlist_id(playlist_url_or_id: str) -> str:
    value = playlist_url_or_id.strip()
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        playlist_ids = parse_qs(parsed.query).get("list", [])
        if not playlist_ids or not playlist_ids[0].strip():
            raise ValueError(f"Playlist URL is missing a 'list' parameter: {value}")
        return playlist_ids[0].strip()
    return value


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) wintop-catalog-updater/0.1",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def load_champion_lookup() -> dict[str, str]:
    payload = json.loads(CHAMPIONS_PATH.read_text(encoding="utf-8"))
    lookup: dict[str, str] = {}
    for champion in payload["items"]:
        champion_id = champion["id"]
        lookup[champion_id.casefold()] = champion_id
        lookup[champion["nameEn"].casefold()] = champion_id
        lookup[champion["nameJa"]] = champion_id
        for alias in champion.get("aliases", []):
            lookup[alias.casefold()] = champion_id
    for alias, champion_id in EXTRA_CHAMPION_ALIASES.items():
        lookup[alias.casefold()] = champion_id
        lookup[alias] = champion_id
    return lookup


def clean_champion_token(raw_value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)|（[^）]*）", "", raw_value)
    return cleaned.strip()


def parse_matchup_from_title(
    title: str, champion_lookup: dict[str, str]
) -> tuple[str, str, str | None] | None:
    head = title.split(" - ")[0].strip()
    english_match = re.match(r"^(.*?)\s+Top\s+vs\s+(.*)$", head, flags=re.IGNORECASE)
    if english_match:
        player_raw = clean_champion_token(english_match.group(1))
        opponent_raw = clean_champion_token(english_match.group(2))
    else:
        japanese_match = re.match(r"^(.*?)対(.*)$", head)
        if not japanese_match:
            return None
        player_raw = clean_champion_token(japanese_match.group(1))
        opponent_raw = clean_champion_token(japanese_match.group(2))

    player_id = champion_lookup.get(player_raw.casefold()) or champion_lookup.get(
        player_raw
    )
    opponent_id = champion_lookup.get(opponent_raw.casefold()) or champion_lookup.get(
        opponent_raw
    )
    if not player_id or not opponent_id:
        raise ValueError(
            f"Could not resolve champion IDs from title '{title}' "
            f"(player='{player_raw}', opponent='{opponent_raw}')"
        )

    patch_match = re.search(r"(?:Patch\s+|パッチ)([0-9]+\.[0-9]+)", title, re.IGNORECASE)
    game_patch = patch_match.group(1) if patch_match else None
    return player_id, opponent_id, game_patch


def parse_atom_feed(xml_text: str) -> dict[str, dict[str, str]]:
    root = ET.fromstring(xml_text)
    feed_entries: dict[str, dict[str, str]] = {}
    for entry in root.findall("atom:entry", ATOM_NS):
        video_id_el = entry.find("yt:videoId", ATOM_NS)
        title_el = entry.find("atom:title", ATOM_NS)
        published_el = entry.find("atom:published", ATOM_NS)
        author_name_el = entry.find("atom:author/atom:name", ATOM_NS)
        if video_id_el is None or not video_id_el.text:
            continue
        video_id = video_id_el.text.strip()
        feed_entries[video_id] = {
            "videoId": video_id,
            "title": (title_el.text or "").strip() if title_el is not None else "",
            "publishedAt": (
                (published_el.text or "").strip() if published_el is not None else ""
            ),
            "channelName": (
                (author_name_el.text or "").strip()
                if author_name_el is not None
                else "Challenger Replays"
            ),
        }
    return feed_entries


def extract_playlist_page_entries(html_text: str) -> list[dict[str, str]]:
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", html_text)
    if not match:
        raise ValueError("Could not find ytInitialData in playlist HTML")

    data = json.loads(match.group(1))
    entries: list[dict[str, str]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "lockupViewModel" in node:
                vm = node["lockupViewModel"]
                video_id = vm.get("contentId")
                title = (
                    vm.get("metadata", {})
                    .get("lockupMetadataViewModel", {})
                    .get("title", {})
                    .get("content")
                )
                if isinstance(video_id, str) and isinstance(title, str):
                    entries.append({"videoId": video_id, "title": title.strip()})
                return
            if "playlistVideoRenderer" in node:
                renderer = node["playlistVideoRenderer"]
                video_id = renderer.get("videoId")
                runs = renderer.get("title", {}).get("runs", [])
                title = runs[0].get("text") if runs else None
                if isinstance(video_id, str) and isinstance(title, str):
                    entries.append({"videoId": video_id, "title": title.strip()})
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data.get("contents", {}))
    return entries


def build_matchup_items(
    playlist_id: str,
    feed_xml: str,
    page_html: str | None,
    verified_at: str,
) -> list[dict[str, Any]]:
    champion_lookup = load_champion_lookup()
    feed_map = parse_atom_feed(feed_xml)
    raw_entries = (
        extract_playlist_page_entries(page_html)
        if page_html
        else list(feed_map.values())
    )

    source_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    channel_url = "https://www.youtube.com/@ChallengerReplays"

    items: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()

    for entry in raw_entries:
        video_id = entry["videoId"]
        if video_id in seen_video_ids:
            continue
        seen_video_ids.add(video_id)

        feed_info = feed_map.get(video_id, {})
        # Prefer the original English title from the Atom feed when available.
        title = feed_info.get("title") or entry["title"]
        parsed = parse_matchup_from_title(title, champion_lookup)
        if parsed is None:
            continue

        player_id, opponent_id, game_patch = parsed
        published_at = feed_info.get("publishedAt") or None
        channel_name = feed_info.get("channelName") or "Challenger Replays"

        items.append(
            {
                "id": f"{player_id.lower()}-vs-{opponent_id.lower()}-{video_id}",
                "playerChampionId": player_id,
                "opponentChampionId": opponent_id,
                "title": title,
                "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
                "channelName": channel_name,
                "channelUrl": channel_url,
                "publishedAt": published_at,
                "gamePatch": game_patch,
                "verifiedAt": verified_at,
                "verificationStatus": "verified",
                "embedStatus": "unknown",
                "sourceUrl": source_url,
            }
        )

    return items


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build backend/src/app/data/matchups.json from a YouTube playlist."
    )
    parser.add_argument(
        "--playlist",
        required=True,
        help="YouTube playlist URL or playlist ID (no default is bundled)",
    )
    parser.add_argument(
        "--feed-file",
        type=Path,
        default=None,
        help="Optional local Atom XML feed file",
    )
    parser.add_argument(
        "--page-file",
        type=Path,
        default=None,
        help="Optional local playlist HTML file",
    )
    parser.add_argument(
        "--verified-at",
        default=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        help="ISO 8601 timestamp for verifiedAt",
    )
    args = parser.parse_args()

    playlist_id = extract_playlist_id(args.playlist)
    feed_xml = (
        args.feed_file.read_text(encoding="utf-8")
        if args.feed_file
        else fetch_text(
            f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
        )
    )
    page_html = (
        args.page_file.read_text(encoding="utf-8")
        if args.page_file
        else fetch_text(f"https://www.youtube.com/playlist?list={playlist_id}")
    )

    items = build_matchup_items(
        playlist_id=playlist_id,
        feed_xml=feed_xml,
        page_html=page_html,
        verified_at=args.verified_at,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} matchup videos from playlist {playlist_id} to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

