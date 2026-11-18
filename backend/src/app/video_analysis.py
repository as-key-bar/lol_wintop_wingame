import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
GAME_ASSETS_PATH = Path(__file__).parent / "data" / "game_assets.json"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class RuneSelection(BaseModel):
    primaryStyleId: int | None = None
    subStyleId: int | None = None
    primarySelections: list[int] = Field(default_factory=list)
    subSelections: list[int] = Field(default_factory=list)
    statShards: list[int] = Field(default_factory=list)


class VideoTimestamp(BaseModel):
    timeSeconds: int = Field(ge=0)
    timeLabel: str = Field(min_length=1)
    label: str = Field(min_length=1)
    isKillEvent: bool = False


class VideoMetadataAnalysis(BaseModel):
    analysisStatus: Literal["unanalyzed", "auto_parsed", "manual_verified"] = (
        "unanalyzed"
    )
    runes: RuneSelection | None = None
    summonerSpells: list[str] = Field(default_factory=list)
    startingItems: list[str] = Field(default_factory=list)
    timestamps: list[VideoTimestamp] = Field(default_factory=list)


@lru_cache(maxsize=1)
def load_game_assets() -> dict[str, Any]:
    return json.loads(GAME_ASSETS_PATH.read_text(encoding="utf-8"))


def _normalize_lookup_key(value: str) -> str:
    return re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龠々ー]+", "", value.casefold())


@lru_cache(maxsize=1)
def _build_asset_indexes() -> dict[str, Any]:
    assets = load_game_assets()

    style_by_name: dict[str, int] = {}
    rune_by_name: dict[str, tuple[int, int, int]] = {}  # name -> (runeId, styleId, slotIndex)
    rune_by_id: dict[int, tuple[int, int]] = {}  # runeId -> (styleId, slotIndex)

    for style in assets.get("runeStyles", []):
        style_id = int(style["id"])
        for key in (style["key"], style["nameEn"], style["nameJa"]):
            style_by_name[_normalize_lookup_key(key)] = style_id

        for slot in style.get("slots", []):
            slot_idx = int(slot["slotIndex"])
            for rune in slot.get("runes", []):
                rune_id = int(rune["id"])
                rune_by_id[rune_id] = (style_id, slot_idx)
                for key in (
                    rune["key"],
                    rune["nameEn"],
                    rune["nameJa"],
                    *rune.get("aliases", []),
                ):
                    rune_by_name[_normalize_lookup_key(key)] = (
                        rune_id,
                        style_id,
                        slot_idx,
                    )
                # Also index short Legend names (e.g. "Alacrity" as well as "Legend: Alacrity")
                if ":" in rune["nameEn"]:
                    short_en = rune["nameEn"].split(":", 1)[1].strip()
                    rune_by_name[_normalize_lookup_key(short_en)] = (
                        rune_id,
                        style_id,
                        slot_idx,
                    )

    spell_by_name: dict[str, str] = {}
    for spell in assets.get("summonerSpells", []):
        spell_id = str(spell["id"])
        for key in (spell["id"], spell["nameEn"], spell["nameJa"]):
            spell_by_name[_normalize_lookup_key(key)] = spell_id

    shard_rows: list[dict[str, int]] = []
    for row in assets.get("statShardRows", []):
        row_lookup: dict[str, int] = {}
        for shard in row:
            shard_id = int(shard["id"])
            for key in (shard["key"], shard["nameEn"], shard["nameJa"]):
                row_lookup[_normalize_lookup_key(key)] = shard_id
        # Common aliases in replay descriptions
        if "healthscaling" in row_lookup:
            row_lookup["scalinghealth"] = row_lookup["healthscaling"]
        if "tenacityandslowresist" in row_lookup:
            row_lookup["tenacity"] = row_lookup["tenacityandslowresist"]
        if "abilityhaste" in row_lookup:
            row_lookup["haste"] = row_lookup["abilityhaste"]
            row_lookup["cdr"] = row_lookup["abilityhaste"]
        shard_rows.append(row_lookup)

    starter_item_by_name: dict[str, str] = {}
    for item in assets.get("starterItems", []):
        item_id = str(item["id"])
        for key in (item["id"], item["nameEn"], item["nameJa"]):
            starter_item_by_name[_normalize_lookup_key(key)] = item_id

    return {
        "style_by_name": style_by_name,
        "rune_by_name": rune_by_name,
        "rune_by_id": rune_by_id,
        "spell_by_name": spell_by_name,
        "shard_rows": shard_rows,
        "starter_item_by_name": starter_item_by_name,
    }


def _parse_spells_from_description(
    description: str, spell_by_name: dict[str, str]
) -> list[str]:
    spells: list[str] = []
    # Match "Spells: Ignite Flash" or "Summoner Spells: Teleport, Flash"
    match = re.search(
        r"(?:Summoner\s+)?Spells\s*[:：]\s*([^\n|]+)",
        description,
        flags=re.IGNORECASE,
    )
    if match:
        tokens = re.split(r"[\s,/|+&・]+", match.group(1).strip())
        for token in tokens:
            spell_id = spell_by_name.get(_normalize_lookup_key(token))
            if spell_id and spell_id not in spells:
                spells.append(spell_id)
            if len(spells) >= 2:
                return spells

    # Compact format fallback: e.g. "Skin: Tahm Kench | Grasp of the Undying + Precision | Ignite Flash"
    header_lines = "\n".join(description.splitlines()[:6])
    for segment in re.split(r"[|\n]+", header_lines):
        tokens = [
            t
            for t in re.split(r"[\s,/|+&・]+", segment.strip())
            if t.strip()
        ]
        if 1 <= len(tokens) <= 3:
            matched_in_segment: list[str] = []
            for token in tokens:
                spell_id = spell_by_name.get(_normalize_lookup_key(token))
                if spell_id and spell_id not in matched_in_segment:
                    matched_in_segment.append(spell_id)
            if len(matched_in_segment) == 2:
                return matched_in_segment

    return spells


def _parse_starter_items_from_description(
    description: str, starter_item_by_name: dict[str, str]
) -> list[str]:
    # Only an explicit "Starter Items:" line counts. The end-of-game "Build:" line
    # is not a reliable source for the starting items, so it is never used.
    items: list[str] = []
    match = re.search(
        r"Starter\s+Items\s*[:：]\s*([^\n]+)", description, flags=re.IGNORECASE
    )
    if not match:
        return items

    for raw_part in match.group(1).split(","):
        item_id = starter_item_by_name.get(_normalize_lookup_key(raw_part.strip()))
        if item_id and item_id not in items:
            items.append(item_id)
    return items


def _parse_runes_from_description(
    description: str, indexes: dict[str, Any]
) -> RuneSelection | None:
    rune_by_name: dict[str, tuple[int, int, int]] = indexes["rune_by_name"]
    style_by_name: dict[str, int] = indexes["style_by_name"]
    shard_rows: list[dict[str, int]] = indexes["shard_rows"]

    primary_style_id: int | None = None
    sub_style_id: int | None = None
    primary_selections: list[int] = []
    sub_selections: list[int] = []
    stat_shards: list[int] = []

    runes_line_match = re.search(
        r"Runes\s*[:：]\s*([^\n]+)", description, flags=re.IGNORECASE
    )
    if runes_line_match:
        runes_line = runes_line_match.group(1).strip()
        segments = [seg.strip() for seg in runes_line.split("|") if seg.strip()]

        for segment in segments:
            # Check if it's a Shards segment: "Shards - Adaptive Force, Adaptive Force, Health"
            if re.match(r"^Shards\b", segment, flags=re.IGNORECASE):
                shard_part = re.sub(
                    r"^Shards\s*[-:：]\s*", "", segment, flags=re.IGNORECASE
                )
                shard_names = [
                    name.strip() for name in shard_part.split(",") if name.strip()
                ]
                for row_idx, shard_name in enumerate(shard_names[:3]):
                    row_map = shard_rows[row_idx]
                    norm_shard = _normalize_lookup_key(shard_name)
                    shard_id = row_map.get(norm_shard)
                    if shard_id is None and norm_shard == "health":
                        shard_id = row_map.get("healthscaling") or row_map.get(
                            "healthflat"
                        )
                    if shard_id is not None:
                        stat_shards.append(shard_id)
                continue

            # Otherwise "<Style> - <Rune 1>, <Rune 2>, ..."
            if " - " in segment:
                style_part, runes_part = segment.split(" - ", 1)
                resolved_style = style_by_name.get(_normalize_lookup_key(style_part))
            else:
                resolved_style = None
                runes_part = segment

            rune_names = [r.strip() for r in runes_part.split(",") if r.strip()]
            matched_runes: list[tuple[int, int, int]] = []
            for r_name in rune_names:
                info = rune_by_name.get(_normalize_lookup_key(r_name))
                if info:
                    matched_runes.append(info)

            if not matched_runes:
                continue

            inferred_style = resolved_style or matched_runes[0][1]
            if primary_style_id is None:
                primary_style_id = inferred_style
                primary_selections = [r[0] for r in matched_runes[:4]]
            elif sub_style_id is None and inferred_style != primary_style_id:
                sub_style_id = inferred_style
                sub_selections = [r[0] for r in matched_runes[:2]]

    # Compact format fallback: e.g. "| Grasp of the Undying + Precision |"
    if primary_style_id is None:
        compact_match = re.search(
            r"\|\s*([^|\n+]+?)\s*\+\s*([^|\n+]+?)\s*\|",
            description,
        )
        if compact_match:
            left_norm = _normalize_lookup_key(compact_match.group(1))
            right_norm = _normalize_lookup_key(compact_match.group(2))
            keystone_info = rune_by_name.get(left_norm)
            sub_style = style_by_name.get(right_norm)
            if keystone_info:
                rune_id, style_id, _ = keystone_info
                primary_style_id = style_id
                primary_selections = [rune_id]
                if sub_style and sub_style != primary_style_id:
                    sub_style_id = sub_style

    # General fallback: scan full description if still not matched
    if primary_style_id is None:
        found_by_style: dict[int, dict[int, int]] = {}
        for norm_name, (rune_id, style_id, slot_idx) in sorted(
            rune_by_name.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if len(norm_name) < 4:
                continue
            if norm_name in _normalize_lookup_key(description):
                style_slots = found_by_style.setdefault(style_id, {})
                style_slots.setdefault(slot_idx, rune_id)

        # Style with a keystone (slot 0) is primary
        for style_id, slots in found_by_style.items():
            if 0 in slots:
                primary_style_id = style_id
                primary_selections = [
                    slots[idx] for idx in sorted(slots) if idx in (0, 1, 2, 3)
                ][:4]
                break

        if primary_style_id is not None:
            for style_id, slots in found_by_style.items():
                if style_id != primary_style_id:
                    sub_slots = [
                        slots[idx] for idx in sorted(slots) if idx in (1, 2, 3)
                    ]
                    if sub_slots:
                        sub_style_id = style_id
                        sub_selections = sub_slots[:2]
                        break

    if primary_style_id is None and not primary_selections:
        return None

    return RuneSelection(
        primaryStyleId=primary_style_id,
        subStyleId=sub_style_id,
        primarySelections=primary_selections,
        subSelections=sub_selections,
        statShards=stat_shards,
    )


KILL_EVENT_PATTERN = re.compile(
    r"\b("
    r"kill|kills|solo\s*kill|first\s*blood|outduel|outduels|outplay|outplays|"
    r"catches|picks\s+off|eliminates|takes\s+down|double\s+kill|triple\s+kill|"
    r"quadra\s+kill|penta\s+kill|1v1|1v2|dive|dives|キル|ソロキル|ファーストブラッド"
    r")\b",
    flags=re.IGNORECASE,
)


def _parse_timestamps_from_description(description: str) -> list[VideoTimestamp]:
    timestamps: list[VideoTimestamp] = []
    seen_seconds: set[int] = set()

    for raw_line in description.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(
            r"^(?:[-*•]\s*)?((?:\d{1,2}:)?\d{1,2}:\d{2})\s*(?:[-–—:|]\s*|\s+)(.+)$",
            line,
        )
        if not match:
            continue

        time_label = match.group(1).strip()
        label = match.group(2).strip()
        if not label:
            continue

        parts = [int(p) for p in time_label.split(":")]
        if len(parts) == 2:
            seconds = parts[0] * 60 + parts[1]
        else:
            seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]

        # Allow multiple events at the same timestamp if labels differ, otherwise deduplicate
        dedup_key = (seconds, label.casefold())
        if dedup_key in seen_seconds:
            continue
        seen_seconds.add(dedup_key)

        is_kill = bool(KILL_EVENT_PATTERN.search(label))
        timestamps.append(
            VideoTimestamp(
                timeSeconds=seconds,
                timeLabel=time_label,
                label=label,
                isKillEvent=is_kill,
            )
        )

    return timestamps


def parse_youtube_description_metadata(description: str) -> VideoMetadataAnalysis:
    indexes = _build_asset_indexes()
    runes = _parse_runes_from_description(description, indexes)
    spells = _parse_spells_from_description(description, indexes["spell_by_name"])
    starter_items = _parse_starter_items_from_description(
        description, indexes["starter_item_by_name"]
    )
    timestamps = _parse_timestamps_from_description(description)

    has_any = bool(runes or spells or starter_items or timestamps)
    return VideoMetadataAnalysis(
        analysisStatus="auto_parsed" if has_any else "unanalyzed",
        runes=runes,
        summonerSpells=spells,
        startingItems=starter_items,
        timestamps=timestamps,
    )


def extract_description_from_watch_html(html_text: str) -> str:
    decoder = json.JSONDecoder()
    for marker in ("var ytInitialPlayerResponse =", "ytInitialPlayerResponse ="):
        marker_idx = html_text.find(marker)
        if marker_idx == -1:
            continue
        brace_idx = html_text.find("{", marker_idx + len(marker))
        if brace_idx == -1:
            continue
        try:
            data, _ = decoder.raw_decode(html_text[brace_idx:])
            short_desc = data.get("videoDetails", {}).get("shortDescription")
            if isinstance(short_desc, str) and short_desc.strip():
                return short_desc
        except json.JSONDecodeError:
            logger.debug(
                "Failed to raw_decode ytInitialPlayerResponse JSON", exc_info=True
            )
    return ""


def fetch_and_analyze_youtube_video(video_url: str) -> VideoMetadataAnalysis:
    parsed = urlparse(video_url)
    video_ids = parse_qs(parsed.query).get("v", [])
    if not video_ids or not video_ids[0].strip():
        return VideoMetadataAnalysis()

    watch_url = f"https://www.youtube.com/watch?v={video_ids[0].strip()}"
    request = Request(
        watch_url,
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            html_text = response.read().decode("utf-8", errors="replace")
    except Exception:
        logger.warning("Failed to fetch YouTube watch page for metadata: %s", watch_url)
        return VideoMetadataAnalysis()

    description = extract_description_from_watch_html(html_text)
    if not description:
        return VideoMetadataAnalysis()

    return parse_youtube_description_metadata(description)
