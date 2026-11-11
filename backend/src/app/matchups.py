import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.champions import get_champion_ids
from app.youtube_search import search_youtube_matchup_candidates

logger = logging.getLogger(__name__)
MATCHUPS_PATH = Path(__file__).parent / "data" / "matchups.json"
YOUTUBE_WATCH_HOSTS = {"www.youtube.com", "youtube.com"}


class UnknownChampionError(LookupError):
    """Raised when a requested champion ID does not exist in the catalog."""


def _validate_https_url(value: str, field_name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field_name} must be an HTTPS URL")
    return value


def _validate_iso_datetime(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid ISO 8601 timestamp") from error
    return normalized


class MatchupVideo(BaseModel):
    id: str = Field(min_length=1)
    playerChampionId: str = Field(min_length=1)
    opponentChampionId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    videoUrl: str = Field(min_length=1)
    channelName: str = Field(min_length=1)
    channelUrl: str = Field(min_length=1)
    publishedAt: str | None = None
    gamePatch: str | None = None
    verifiedAt: str = Field(min_length=1)
    verificationStatus: Literal["verified", "candidate"]
    embedStatus: Literal["unknown", "allowed", "disabled"]
    sourceUrl: str = Field(min_length=1)
    origin: Literal["saved", "youtube_search"] = "saved"

    @field_validator("videoUrl")
    @classmethod
    def validate_video_url(cls, value: str) -> str:
        _validate_https_url(value, "videoUrl")
        parsed = urlparse(value)
        video_ids = parse_qs(parsed.query).get("v", [])
        if (
            parsed.netloc not in YOUTUBE_WATCH_HOSTS
            or parsed.path != "/watch"
            or not video_ids
            or not video_ids[0].strip()
        ):
            raise ValueError("videoUrl must be a YouTube watch page HTTPS URL")
        return value

    @field_validator("channelUrl", "sourceUrl")
    @classmethod
    def validate_https_urls(cls, value: str, info) -> str:
        return _validate_https_url(value, info.field_name)

    @field_validator("verifiedAt")
    @classmethod
    def validate_verified_at(cls, value: str) -> str:
        return _validate_iso_datetime(value, "verifiedAt")

    @field_validator("publishedAt")
    @classmethod
    def validate_published_at(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_iso_datetime(value, "publishedAt")


@lru_cache(maxsize=1)
def load_matchups() -> tuple[MatchupVideo, ...]:
    valid_champion_ids = get_champion_ids()

    try:
        payload = json.loads(MATCHUPS_PATH.read_text(encoding="utf-8"))
        raw_items = payload["items"]
        if not isinstance(raw_items, list):
            raise ValueError("Matchup items must be a list")

        videos = tuple(MatchupVideo.model_validate(item) for item in raw_items)
        seen_ids: set[str] = set()
        for video in videos:
            if video.id in seen_ids:
                raise ValueError(f"Duplicate matchup video id: {video.id}")
            seen_ids.add(video.id)

            if (
                video.playerChampionId not in valid_champion_ids
                or video.opponentChampionId not in valid_champion_ids
            ):
                raise ValueError(
                    f"Matchup video {video.id} references an unknown champion ID"
                )
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValidationError,
        ValueError,
    ) as error:
        logger.exception("Failed to load matchup catalog")
        raise RuntimeError("Matchup catalog is unavailable") from error

    return videos


def get_matchup_videos(
    player_champion_id: str,
    opponent_champion_id: str,
    include_candidates: bool = False,
) -> list[MatchupVideo]:
    valid_champion_ids = get_champion_ids()

    if (
        player_champion_id not in valid_champion_ids
        or opponent_champion_id not in valid_champion_ids
    ):
        raise UnknownChampionError(
            f"Unknown champion in matchup: {player_champion_id} vs {opponent_champion_id}"
        )

    videos = load_matchups()
    saved_videos = [
        video
        for video in videos
        if video.playerChampionId == player_champion_id
        and video.opponentChampionId == opponent_champion_id
        and video.verificationStatus == "verified"
    ]

    if saved_videos and not include_candidates:
        return saved_videos

    if len(saved_videos) >= 5:
        return saved_videos

    seen_urls = {video.videoUrl for video in saved_videos}
    candidates = search_youtube_matchup_candidates(
        player_champion_id=player_champion_id,
        opponent_champion_id=opponent_champion_id,
        max_results=5,
    )
    combined = list(saved_videos)
    for raw_candidate in candidates:
        try:
            candidate_video = MatchupVideo.model_validate(raw_candidate)
        except ValidationError:
            continue
        if candidate_video.videoUrl in seen_urls:
            continue
        seen_urls.add(candidate_video.videoUrl)
        combined.append(candidate_video)
        if len(combined) >= 5:
            break

    return combined

