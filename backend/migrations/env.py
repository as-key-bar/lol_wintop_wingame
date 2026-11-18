import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

from app.database import DEFAULT_DATABASE_URL, Base

load_dotenv()

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url())
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
