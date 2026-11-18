import hashlib
import os

from dotenv import load_dotenv
from sqlalchemy import Integer, String, Text, UniqueConstraint, create_engine, Index
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv()

DEFAULT_DATABASE_URL = (
    "mysql+pymysql://wintop:local_only_password@127.0.0.1:3306/wintop"
)


class Base(DeclarativeBase):
    pass


class MatchupVideoRecord(Base):
    __tablename__ = "matchup_videos"
    __table_args__ = (
        Index("idx_matchup_pair", "player_champion_id", "opponent_champion_id"),
    )

    id: Mapped[str] = mapped_column(String(191), primary_key=True)
    player_champion_id: Mapped[str] = mapped_column(String(64), nullable=False)
    opponent_champion_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    video_url: Mapped[str] = mapped_column(String(512), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_url: Mapped[str] = mapped_column(String(512), nullable=False)
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    game_patch: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verified_at: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="verified"
    )
    embed_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    upvote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MatchupVideoVoteRecord(Base):
    __tablename__ = "matchup_video_votes"
    __table_args__ = (
        UniqueConstraint("video_record_id", "voter_hash", name="uq_video_voter"),
        Index("idx_vote_video", "video_record_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_record_id: Mapped[str] = mapped_column(String(191), nullable=False)
    voter_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class MatchupVideoMetadataRecord(Base):
    __tablename__ = "matchup_video_metadata"

    video_record_id: Mapped[str] = mapped_column(String(191), primary_key=True)
    analysis_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unanalyzed"
    )
    runes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summoner_spells_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    starting_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamps_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        _engine = create_engine(database_url, pool_pre_ping=True)
    return _engine


def set_engine(engine: Engine | None) -> None:
    global _engine
    _engine = engine


def compute_voter_hash(voter_token: str | None) -> str | None:
    token = (voter_token or "").strip()
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

