"""Baseline: matchup_videos, matchup_video_votes, matchup_video_metadata

Databases created before Alembic was introduced already contain these tables
(created at runtime by Base.metadata.create_all), so each table is only
created when it is missing.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "matchup_videos" not in existing:
        op.create_table(
            "matchup_videos",
            sa.Column("id", sa.String(191), primary_key=True),
            sa.Column("player_champion_id", sa.String(64), nullable=False),
            sa.Column("opponent_champion_id", sa.String(64), nullable=False),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("video_url", sa.String(512), nullable=False),
            sa.Column("channel_name", sa.String(255), nullable=False),
            sa.Column("channel_url", sa.String(512), nullable=False),
            sa.Column("published_at", sa.String(64), nullable=True),
            sa.Column("game_patch", sa.String(32), nullable=True),
            sa.Column("verified_at", sa.String(64), nullable=False),
            sa.Column("verification_status", sa.String(32), nullable=False),
            sa.Column("embed_status", sa.String(32), nullable=False),
            sa.Column("source_url", sa.String(512), nullable=False),
            sa.Column("upvote_count", sa.Integer, nullable=False),
        )
        op.create_index(
            "idx_matchup_pair",
            "matchup_videos",
            ["player_champion_id", "opponent_champion_id"],
        )

    if "matchup_video_votes" not in existing:
        op.create_table(
            "matchup_video_votes",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("video_record_id", sa.String(191), nullable=False),
            sa.Column("voter_hash", sa.String(64), nullable=False),
            sa.UniqueConstraint("video_record_id", "voter_hash", name="uq_video_voter"),
        )
        op.create_index("idx_vote_video", "matchup_video_votes", ["video_record_id"])

    if "matchup_video_metadata" not in existing:
        op.create_table(
            "matchup_video_metadata",
            sa.Column("video_record_id", sa.String(191), primary_key=True),
            sa.Column("analysis_status", sa.String(32), nullable=False),
            sa.Column("runes_json", sa.Text, nullable=True),
            sa.Column("summoner_spells_json", sa.Text, nullable=True),
            sa.Column("starting_items_json", sa.Text, nullable=True),
            sa.Column("timestamps_json", sa.Text, nullable=True),
            sa.Column("updated_at", sa.String(64), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("matchup_video_metadata")
    op.drop_table("matchup_video_votes")
    op.drop_table("matchup_videos")
