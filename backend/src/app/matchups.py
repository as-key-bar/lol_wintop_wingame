import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.champions import get_champion_ids, load_catalog
from app.database import (
    Base,
    MatchupVideoRecord,
    MatchupVideoVoteRecord,
    get_engine,
)
from app.youtube_search import (
    extract_rank_tier_score,
    parse_patch_tuple,
    search_youtube_matchup_candidates,
    title_matches_matchup,
)

logger = logging.getLogger(__name__)
MATCHUPS_PATH = Path(__file__).parent / "data" / "matchups.json"
YOUTUBE_WATCH_HOSTS = {"www.youtube.com", "youtube.com"}


class UnknownChampionError(LookupError):
    """Raised when a requested champion ID does not exist in the catalog."""


class InvalidUpvoteError(ValueError):
    """Raised when an upvote payload does not match the target matchup."""


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
    verificationStatus: Literal["verified", "candidate"] = "verified"
    embedStatus: Literal["unknown", "allowed", "disabled"] = "unknown"
    sourceUrl: str = Field(min_length=1)
    origin: Literal["saved", "youtube_search"] = "saved"
    upvoteCount: int = Field(default=0, ge=0)
    upvotedByViewer: bool = False

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


_seeded_engines: set[int] = set()


def clear_seeded_cache() -> None:
    _seeded_engines.clear()


def ensure_database_seeded(engine: Engine, seed_videos: tuple[MatchupVideo, ...]) -> None:
    engine_id = id(engine)
    if engine_id in _seeded_engines:
        return

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        existing_ids = set(session.scalars(select(MatchupVideoRecord.id)).all())
        new_records = [
            MatchupVideoRecord(
                id=video.id,
                player_champion_id=video.playerChampionId,
                opponent_champion_id=video.opponentChampionId,
                title=video.title,
                video_url=video.videoUrl,
                channel_name=video.channelName,
                channel_url=video.channelUrl,
                published_at=video.publishedAt,
                game_patch=video.gamePatch,
                verified_at=video.verifiedAt,
                verification_status=video.verificationStatus,
                embed_status=video.embedStatus,
                source_url=video.sourceUrl,
                upvote_count=video.upvoteCount,
            )
            for video in seed_videos
            if video.id not in existing_ids
        ]
        if new_records:
            session.add_all(new_records)
            session.commit()

    _seeded_engines.add(engine_id)


def _record_to_model(
    record: MatchupVideoRecord, upvoted_ids: set[str]
) -> MatchupVideo:
    return MatchupVideo(
        id=record.id,
        playerChampionId=record.player_champion_id,
        opponentChampionId=record.opponent_champion_id,
        title=record.title,
        videoUrl=record.video_url,
        channelName=record.channel_name,
        channelUrl=record.channel_url,
        publishedAt=record.published_at,
        gamePatch=record.game_patch,
        verifiedAt=record.verified_at,
        verificationStatus=(
            "verified" if record.verification_status == "verified" else "candidate"
        ),
        embedStatus=(
            record.embed_status
            if record.embed_status in ("unknown", "allowed", "disabled")
            else "unknown"
        ),
        sourceUrl=record.source_url,
        origin="saved",
        upvoteCount=record.upvote_count,
        upvotedByViewer=record.id in upvoted_ids,
    )


def _sort_saved_videos(videos: list[MatchupVideo]) -> list[MatchupVideo]:
    return sorted(
        videos,
        key=lambda item: (
            item.upvoteCount,
            parse_patch_tuple(item.gamePatch),
            extract_rank_tier_score(item.title),
        ),
        reverse=True,
    )


def _load_saved_matchup_videos(
    player_champion_id: str,
    opponent_champion_id: str,
    seed_videos: tuple[MatchupVideo, ...],
    voter_hash: str | None = None,
) -> list[MatchupVideo]:
    try:
        engine = get_engine()
        ensure_database_seeded(engine, seed_videos)
        with Session(engine) as session:
            records = session.scalars(
                select(MatchupVideoRecord).where(
                    MatchupVideoRecord.player_champion_id == player_champion_id,
                    MatchupVideoRecord.opponent_champion_id == opponent_champion_id,
                    MatchupVideoRecord.verification_status == "verified",
                )
            ).all()

            upvoted_ids: set[str] = set()
            if voter_hash and records:
                record_ids = [record.id for record in records]
                upvoted_ids = set(
                    session.scalars(
                        select(MatchupVideoVoteRecord.video_record_id).where(
                            MatchupVideoVoteRecord.voter_hash == voter_hash,
                            MatchupVideoVoteRecord.video_record_id.in_(record_ids),
                        )
                    ).all()
                )

            return _sort_saved_videos(
                [_record_to_model(record, upvoted_ids) for record in records]
            )
    except SQLAlchemyError:
        logger.debug(
            "Database unavailable for matchup query; falling back to JSON catalog",
            exc_info=True,
        )
        fallback = [
            video
            for video in seed_videos
            if video.playerChampionId == player_champion_id
            and video.opponentChampionId == opponent_champion_id
            and video.verificationStatus == "verified"
        ]
        return _sort_saved_videos(fallback)


def get_matchup_videos(
    player_champion_id: str,
    opponent_champion_id: str,
    include_candidates: bool = False,
    voter_hash: str | None = None,
) -> list[MatchupVideo]:
    valid_champion_ids = get_champion_ids()

    if (
        player_champion_id not in valid_champion_ids
        or opponent_champion_id not in valid_champion_ids
    ):
        raise UnknownChampionError(
            f"Unknown champion in matchup: {player_champion_id} vs {opponent_champion_id}"
        )

    seed_videos = load_matchups()
    saved_videos = _load_saved_matchup_videos(
        player_champion_id=player_champion_id,
        opponent_champion_id=opponent_champion_id,
        seed_videos=seed_videos,
        voter_hash=voter_hash,
    )

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


def toggle_matchup_video_upvote(
    player_champion_id: str,
    opponent_champion_id: str,
    video: MatchupVideo,
    voter_hash: str | None,
) -> MatchupVideo:
    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    player = by_id.get(player_champion_id)
    opponent = by_id.get(opponent_champion_id)
    if not player or not opponent:
        raise UnknownChampionError(
            f"Unknown champion in matchup: {player_champion_id} vs {opponent_champion_id}"
        )

    if not voter_hash:
        raise InvalidUpvoteError("voterToken is required to upvote a video")

    if (
        video.playerChampionId != player_champion_id
        or video.opponentChampionId != opponent_champion_id
    ):
        raise InvalidUpvoteError("Video champion IDs do not match the route matchup")

    if not title_matches_matchup(video.title, player, opponent):
        raise InvalidUpvoteError(
            "Video title does not match the specified top-lane matchup"
        )

    seed_videos = load_matchups()
    try:
        engine = get_engine()
        ensure_database_seeded(engine, seed_videos)
        with Session(engine) as session:
            record = session.scalar(
                select(MatchupVideoRecord).where(
                    (MatchupVideoRecord.id == video.id)
                    | (
                        (MatchupVideoRecord.player_champion_id == player_champion_id)
                        & (
                            MatchupVideoRecord.opponent_champion_id
                            == opponent_champion_id
                        )
                        & (MatchupVideoRecord.video_url == video.videoUrl)
                    )
                )
            )
            if record is None:
                record = MatchupVideoRecord(
                    id=video.id,
                    player_champion_id=player_champion_id,
                    opponent_champion_id=opponent_champion_id,
                    title=video.title,
                    video_url=video.videoUrl,
                    channel_name=video.channelName,
                    channel_url=video.channelUrl,
                    published_at=video.publishedAt,
                    game_patch=video.gamePatch,
                    verified_at=video.verifiedAt,
                    verification_status="verified",
                    embed_status=video.embedStatus,
                    source_url=video.sourceUrl,
                    upvote_count=0,
                )
                session.add(record)
                session.flush()

            existing_vote = session.scalar(
                select(MatchupVideoVoteRecord).where(
                    MatchupVideoVoteRecord.video_record_id == record.id,
                    MatchupVideoVoteRecord.voter_hash == voter_hash,
                )
            )
            if existing_vote is None:
                session.add(
                    MatchupVideoVoteRecord(
                        video_record_id=record.id,
                        voter_hash=voter_hash,
                    )
                )
                record.upvote_count = max(0, record.upvote_count) + 1
                upvoted_by_viewer = True
            else:
                session.delete(existing_vote)
                record.upvote_count = max(0, record.upvote_count - 1)
                upvoted_by_viewer = False

            session.commit()
            session.refresh(record)
            return _record_to_model(
                record, {record.id} if upvoted_by_viewer else set()
            )
    except SQLAlchemyError as error:
        logger.exception("Failed to persist matchup video upvote")
        raise RuntimeError("Database is unavailable for upvoting") from error
