"""Add wave notes and the first-wave time to matchup_video_metadata

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("matchup_video_metadata")}
    with op.batch_alter_table("matchup_video_metadata") as batch:
        if "waves_json" not in columns:
            batch.add_column(sa.Column("waves_json", sa.Text, nullable=True))
        if "first_wave_seconds" not in columns:
            batch.add_column(sa.Column("first_wave_seconds", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("matchup_video_metadata") as batch:
        batch.drop_column("first_wave_seconds")
        batch.drop_column("waves_json")
