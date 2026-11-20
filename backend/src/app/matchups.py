import json
import logging
import re
from datetime import datetime, timedelta, timezone
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
from app.retention import now_iso, parse_iso, retention_days
from app.database import (
    Base,
    MatchupVideoMetadataRecord,
    MatchupVideoRecord,
    MatchupVideoVoteRecord,
    get_engine,
)
from app.video_analysis import (
    RuneSelection,
    VideoMetadataAnalysis,
    VideoTimestamp,
    WaveNote,
    fetch_and_analyze_youtube_video,
)
from app.youtube_search import (
    extract_rank_tier_score,
    parse_patch_tuple,
    search_youtube_matchup_candidates,
    title_matches_matchup,
    was_offered_as_candidate,
)

logger = logging.getLogger(__name__)
MATCHUPS_PATH = Path(__file__).parent / "data" / "matchups.json"
YOUTUBE_WATCH_HOSTS = {"www.youtube.com", "youtube.com"}
# Saved videos come first (by votes), then search candidates fill the remaining slots.
MAX_VIDEOS_PER_MATCHUP = 8
YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
YOUTUBE_CHANNEL_HOSTS = {"www.youtube.com", "youtube.com"}
MAX_TEXT_LENGTH = 512


class UnknownChampionError(LookupError):
    """Raised when a requested champion ID does not exist in the catalog."""


class InvalidUpvoteError(ValueError):
    """Raised when an upvote payload does not match the target matchup."""


def canonical_video_record_id(player_champion_id: str, opponent_champion_id: str, video_url: str) -> str:
    video_id = parse_qs(urlparse(video_url).query)["v"][0]
    return f"yt-{player_champion_id.lower()}-vs-{opponent_champion_id.lower()}-{video_id}"


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
    id: str = Field(min_length=1, max_length=191)
    playerChampionId: str = Field(min_length=1, max_length=64)
    opponentChampionId: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    videoUrl: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    channelName: str = Field(min_length=1, max_length=255)
    channelUrl: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    publishedAt: str | None = Field(default=None, max_length=64)
    gamePatch: str | None = Field(default=None, max_length=32)
    verifiedAt: str = Field(min_length=1, max_length=64)
    verificationStatus: Literal["verified", "candidate"] = "verified"
    embedStatus: Literal["unknown", "allowed", "disabled"] = "unknown"
    sourceUrl: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    origin: Literal["saved", "youtube_search"] = "saved"
    upvoteCount: int = Field(default=0, ge=0)
    upvotedByViewer: bool = False
    metadata: VideoMetadataAnalysis | None = None

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
            or not YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_ids[0])
        ):
            raise ValueError("videoUrl must be a YouTube watch page HTTPS URL")
        return value

    @field_validator("channelUrl", "sourceUrl")
    @classmethod
    def validate_youtube_urls(cls, value: str, info) -> str:
        _validate_https_url(value, info.field_name)
        # Links are rendered to visitors, so only YouTube hosts are accepted.
        if urlparse(value).netloc not in YOUTUBE_CHANNEL_HOSTS:
            raise ValueError(f"{info.field_name} must be a YouTube HTTPS URL")
        return value

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
                fetched_at=now_iso(),
            )
            for video in seed_videos
            if video.id not in existing_ids
        ]
        if new_records:
            session.add_all(new_records)
            session.commit()

    _seeded_engines.add(engine_id)


def _metadata_record_to_model(
    meta_record: MatchupVideoMetadataRecord | None,
) -> VideoMetadataAnalysis | None:
    if meta_record is None:
        return None
    try:
        runes = (
            RuneSelection.model_validate(json.loads(meta_record.runes_json))
            if meta_record.runes_json
            else None
        )
        spells = (
            json.loads(meta_record.summoner_spells_json)
            if meta_record.summoner_spells_json
            else []
        )
        items = (
            json.loads(meta_record.starting_items_json)
            if meta_record.starting_items_json
            else []
        )
        timestamps = (
            [
                VideoTimestamp.model_validate(ts)
                for ts in json.loads(meta_record.timestamps_json)
            ]
            if meta_record.timestamps_json
            else []
        )
        waves = (
            [WaveNote.model_validate(w) for w in json.loads(meta_record.waves_json)]
            if meta_record.waves_json
            else []
        )
        status: Literal["unanalyzed", "auto_parsed", "manual_verified"] = (
            meta_record.analysis_status
            if meta_record.analysis_status
            in ("unanalyzed", "auto_parsed", "manual_verified")
            else "auto_parsed"
        )
        return VideoMetadataAnalysis(
            analysisStatus=status,
            runes=runes,
            summonerSpells=spells,
            startingItems=items,
            timestamps=timestamps,
            waves=waves,
        )
    except Exception:
        logger.warning(
            "Failed to deserialize metadata for video %s", meta_record.video_record_id
        )
        return None


def _upsert_metadata_record(
    session: Session,
    video_record_id: str,
    analysis: VideoMetadataAnalysis,
) -> MatchupVideoMetadataRecord:
    """Writes the build fields. Waves are a separate input with their own save
    (save_video_waves), so saving a build never changes them."""
    now_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    meta_record = session.get(MatchupVideoMetadataRecord, video_record_id)
    if meta_record is None:
        meta_record = MatchupVideoMetadataRecord(
            video_record_id=video_record_id,
            analysis_status=analysis.analysisStatus,
            updated_at=now_iso,
        )
        session.add(meta_record)

    meta_record.analysis_status = analysis.analysisStatus
    meta_record.runes_json = (
        json.dumps(analysis.runes.model_dump(), ensure_ascii=False)
        if analysis.runes
        else None
    )
    meta_record.summoner_spells_json = json.dumps(
        analysis.summonerSpells, ensure_ascii=False
    )
    meta_record.starting_items_json = json.dumps(
        analysis.startingItems, ensure_ascii=False
    )
    meta_record.timestamps_json = json.dumps(
        [ts.model_dump() for ts in analysis.timestamps], ensure_ascii=False
    )
    meta_record.updated_at = now_iso
    return meta_record


def _resolve_matchup(player_champion_id: str, opponent_champion_id: str):
    """Returns (player, opponent) or raises UnknownChampionError."""
    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    player = by_id.get(player_champion_id)
    opponent = by_id.get(opponent_champion_id)
    if not player or not opponent:
        raise UnknownChampionError(
            f"Unknown champion in matchup: {player_champion_id} vs {opponent_champion_id}"
        )
    return player, opponent


def _require_video_for_matchup(
    player_champion_id: str, opponent_champion_id: str, video: MatchupVideo
) -> None:
    """Checks a submitted video against the route's matchup (champion ids and title)."""
    player, opponent = _resolve_matchup(player_champion_id, opponent_champion_id)
    if (
        video.playerChampionId != player_champion_id
        or video.opponentChampionId != opponent_champion_id
    ):
        raise InvalidUpvoteError("Video champion IDs do not match the route matchup")
    if not title_matches_matchup(video.title, player, opponent):
        raise InvalidUpvoteError(
            "Video title does not match the specified top-lane matchup"
        )


def _new_video_record(
    player_champion_id: str,
    opponent_champion_id: str,
    video: MatchupVideo,
    upvote_count: int = 0,
) -> MatchupVideoRecord:
    """A row for a video the server offered. The id is derived from the YouTube video id,
    never taken from the client."""
    return MatchupVideoRecord(
        id=canonical_video_record_id(
            player_champion_id, opponent_champion_id, video.videoUrl
        ),
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
        upvote_count=upvote_count,
        fetched_at=now_iso(),
    )


def _record_to_model(
    record: MatchupVideoRecord,
    upvoted_ids: set[str],
    meta_record: MatchupVideoMetadataRecord | None = None,
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
        metadata=_metadata_record_to_model(meta_record),
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
            # Never serve a row past the retention limit, even if the purge job is late.
            limit = datetime.now(timezone.utc) - timedelta(days=retention_days())
            records = [
                r
                for r in records
                if (parse_iso(r.fetched_at) or datetime.min.replace(tzinfo=timezone.utc))
                > limit
            ]

            upvoted_ids: set[str] = set()
            meta_by_id: dict[str, MatchupVideoMetadataRecord] = {}
            if records:
                record_ids = [record.id for record in records]
                meta_records = session.scalars(
                    select(MatchupVideoMetadataRecord).where(
                        MatchupVideoMetadataRecord.video_record_id.in_(record_ids)
                    )
                ).all()
                meta_by_id = {m.video_record_id: m for m in meta_records}
                if voter_hash:
                    upvoted_ids = set(
                        session.scalars(
                            select(MatchupVideoVoteRecord.video_record_id).where(
                                MatchupVideoVoteRecord.voter_hash == voter_hash,
                                MatchupVideoVoteRecord.video_record_id.in_(record_ids),
                            )
                        ).all()
                    )

            return _sort_saved_videos(
                [
                    _record_to_model(record, upvoted_ids, meta_by_id.get(record.id))
                    for record in records
                ]
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

    # Saved (upvoted) videos no longer hide the search results: both are shown together so
    # a vote does not make every other candidate disappear. The search itself is cached
    # (see youtube_search.SEARCH_CACHE_TTL_SECONDS) to protect the YouTube API quota.
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
        if len(combined) >= MAX_VIDEOS_PER_MATCHUP:
            break

    return combined


def toggle_matchup_video_upvote(
    player_champion_id: str,
    opponent_champion_id: str,
    video: MatchupVideo,
    voter_hash: str | None,
) -> MatchupVideo:
    _resolve_matchup(player_champion_id, opponent_champion_id)
    if not voter_hash:
        raise InvalidUpvoteError("voterToken is required to upvote a video")
    _require_video_for_matchup(player_champion_id, opponent_champion_id, video)

    seed_videos = load_matchups()
    try:
        engine = get_engine()
        ensure_database_seeded(engine, seed_videos)
        with Session(engine) as session:
            # Look the row up by the server-derived key only; a client-supplied id must
            # never select a row whose video differs from the submitted videoUrl.
            record = session.scalar(
                select(MatchupVideoRecord).where(
                    MatchupVideoRecord.player_champion_id == player_champion_id,
                    MatchupVideoRecord.opponent_champion_id == opponent_champion_id,
                    MatchupVideoRecord.video_url == video.videoUrl,
                )
            )
            if record is None:
                # Only videos this server itself offered (via its YouTube search) may
                # become new rows; otherwise anyone could inject arbitrary videos.
                if not was_offered_as_candidate(
                    player_champion_id, opponent_champion_id, video.videoUrl
                ):
                    raise InvalidUpvoteError(
                        "Only videos offered by the matchup search can be upvoted"
                    )
                record = _new_video_record(
                    player_champion_id, opponent_champion_id, video
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
            meta_record = session.get(MatchupVideoMetadataRecord, record.id)
            if meta_record is None and upvoted_by_viewer:
                if video.metadata and video.metadata.analysisStatus != "unanalyzed":
                    meta_record = _upsert_metadata_record(
                        session, record.id, video.metadata
                    )
                    session.commit()
                else:
                    analyzed = fetch_and_analyze_youtube_video(record.video_url)
                    if analyzed.analysisStatus != "unanalyzed":
                        meta_record = _upsert_metadata_record(
                            session, record.id, analyzed
                        )
                        session.commit()

            return _record_to_model(
                record,
                {record.id} if upvoted_by_viewer else set(),
                meta_record,
            )
    except SQLAlchemyError as error:
        logger.exception("Failed to persist matchup video upvote")
        raise RuntimeError("Database is unavailable for upvoting") from error


def analyze_matchup_video_metadata(
    player_champion_id: str,
    opponent_champion_id: str,
    video: MatchupVideo,
    refresh: bool = False,
) -> VideoMetadataAnalysis:
    valid_champion_ids = get_champion_ids()
    if (
        player_champion_id not in valid_champion_ids
        or opponent_champion_id not in valid_champion_ids
    ):
        raise UnknownChampionError(
            f"Unknown champion in matchup: {player_champion_id} vs {opponent_champion_id}"
        )

    seed_videos = load_matchups()
    try:
        engine = get_engine()
        ensure_database_seeded(engine, seed_videos)
        with Session(engine) as session:
            record = session.get(
                MatchupVideoRecord,
                canonical_video_record_id(
                    player_champion_id, opponent_champion_id, video.videoUrl
                ),
            ) or session.get(MatchupVideoRecord, video.id)
            existing_model: VideoMetadataAnalysis | None = None
            if record is not None:
                existing_model = _metadata_record_to_model(
                    session.get(MatchupVideoMetadataRecord, record.id)
                )

            if existing_model is not None and existing_model.analysisStatus != "unanalyzed":
                # Manually verified data is never overwritten by automatic parsing.
                if existing_model.analysisStatus == "manual_verified" or not refresh:
                    return existing_model

            analyzed = fetch_and_analyze_youtube_video(video.videoUrl)
            if record is not None and analyzed.analysisStatus != "unanalyzed":
                _upsert_metadata_record(session, record.id, analyzed)
                session.commit()
            return analyzed
    except SQLAlchemyError:
        logger.debug(
            "Database unavailable while caching analyzed video metadata",
            exc_info=True,
        )

    return fetch_and_analyze_youtube_video(video.videoUrl)


def save_manual_video_metadata(
    player_champion_id: str,
    opponent_champion_id: str,
    video: MatchupVideo,
    metadata: VideoMetadataAnalysis,
) -> VideoMetadataAnalysis:
    _require_video_for_matchup(player_champion_id, opponent_champion_id, video)

    verified_metadata = VideoMetadataAnalysis(
        analysisStatus="manual_verified",
        runes=metadata.runes,
        summonerSpells=metadata.summonerSpells[:2],
        startingItems=metadata.startingItems[:6],
        timestamps=metadata.timestamps,
    )

    seed_videos = load_matchups()
    try:
        engine = get_engine()
        ensure_database_seeded(engine, seed_videos)
        with Session(engine) as session:
            record = session.get(
                MatchupVideoRecord,
                canonical_video_record_id(
                    player_champion_id, opponent_champion_id, video.videoUrl
                ),
            )
            if record is None:
                record = _new_video_record(
                    player_champion_id,
                    opponent_champion_id,
                    video,
                    upvote_count=video.upvoteCount,
                )
                session.add(record)
                session.flush()

            _upsert_metadata_record(session, record.id, verified_metadata)
            session.commit()
            # Return what is stored, so the waves (saved separately) stay in the response.
            return (
                _metadata_record_to_model(session.get(MatchupVideoMetadataRecord, record.id))
                or verified_metadata
            )
    except SQLAlchemyError as error:
        logger.exception("Failed to save manual video metadata")
        raise RuntimeError("Database is unavailable for saving metadata") from error


def save_video_waves(
    player_champion_id: str,
    opponent_champion_id: str,
    video: MatchupVideo,
    waves: list[WaveNote],
) -> VideoMetadataAnalysis:
    """Saves only the wave notes; the build fields are left as they are."""
    _require_video_for_matchup(player_champion_id, opponent_champion_id, video)
    numbers = [wave.waveNumber for wave in waves]
    if len(set(numbers)) != len(numbers):
        raise InvalidUpvoteError("Each wave number can appear only once")

    seed_videos = load_matchups()
    try:
        engine = get_engine()
        ensure_database_seeded(engine, seed_videos)
        with Session(engine) as session:
            record = session.get(
                MatchupVideoRecord,
                canonical_video_record_id(
                    player_champion_id, opponent_champion_id, video.videoUrl
                ),
            )
            if record is None:
                # Same rule as a vote: only videos this server offered may become rows.
                if not was_offered_as_candidate(
                    player_champion_id, opponent_champion_id, video.videoUrl
                ):
                    raise InvalidUpvoteError(
                        "Only videos offered by the matchup search can be edited"
                    )
                record = _new_video_record(
                    player_champion_id, opponent_champion_id, video
                )
                session.add(record)
                session.flush()

            meta_record = session.get(MatchupVideoMetadataRecord, record.id)
            if meta_record is None:
                meta_record = MatchupVideoMetadataRecord(
                    video_record_id=record.id,
                    analysis_status="unanalyzed",
                    updated_at=now_iso(),
                )
                session.add(meta_record)
            meta_record.waves_json = json.dumps(
                [w.model_dump() for w in sorted(waves, key=lambda w: w.waveNumber)],
                ensure_ascii=False,
            )
            meta_record.updated_at = now_iso()
            session.commit()
            return _metadata_record_to_model(meta_record) or VideoMetadataAnalysis()
    except SQLAlchemyError as error:
        logger.exception("Failed to save wave notes")
        raise RuntimeError("Database is unavailable for saving waves") from error

