"""Add matchup_videos.fetched_at to enforce the YouTube data retention limit

Existing rows get the time of this migration, so every row expires at most one
retention period after it runs.

Revision ID: 0002
Revises: 0001
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("matchup_videos")}
    if "fetched_at" in columns:
        return
    # batch mode lets SQLite (tests) and MySQL share one code path; the default only
    # backfills existing rows, new rows always set fetched_at explicitly.
    with op.batch_alter_table("matchup_videos") as batch:
        batch.add_column(
            sa.Column("fetched_at", sa.String(64), nullable=False, server_default=now)
        )
    op.create_index("idx_matchup_fetched_at", "matchup_videos", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("idx_matchup_fetched_at", table_name="matchup_videos")
    with op.batch_alter_table("matchup_videos") as batch:
        batch.drop_column("fetched_at")
