"""Add users and login sessions (Google login for editors)

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("google_sub", sa.String(64), nullable=False, unique=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("created_at", sa.String(64), nullable=False),
        )
    if "login_sessions" not in tables:
        op.create_table(
            "login_sessions",
            sa.Column("token_hash", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.Integer, nullable=False),
            sa.Column("created_at", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.String(64), nullable=False),
        )
        op.create_index("idx_session_user", "login_sessions", ["user_id"])
        op.create_index("idx_session_expires", "login_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("login_sessions")
    op.drop_table("users")
