import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database import (
    MatchupVideoMetadataRecord,
    MatchupVideoRecord,
    MatchupVideoVoteRecord,
    get_engine,
)

logger = logging.getLogger(__name__)

# YouTube API Services Developer Policies III.E.4.c/d: data obtained from the API may be
# stored for at most 30 calendar days. The default is three weeks: it keeps a margin for a
# stopped job and also keeps the information fresh across game patches.
DEFAULT_RETENTION_DAYS = 21
MAX_RETENTION_DAYS = 30


def retention_days() -> int:
    raw = os.getenv("YOUTUBE_DATA_RETENTION_DAYS", "").strip()
    try:
        days = int(raw) if raw else DEFAULT_RETENTION_DAYS
    except ValueError:
        logger.warning("Invalid YOUTUBE_DATA_RETENTION_DAYS=%r; using the default", raw)
        days = DEFAULT_RETENTION_DAYS
    # Never exceed the policy limit, whatever the environment says.
    return max(1, min(days, MAX_RETENTION_DAYS))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def cutoff_iso(days: int | None = None, now: datetime | None = None) -> datetime:
    moment = now or datetime.now(timezone.utc)
    return moment - timedelta(days=days if days is not None else retention_days())


def parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def purge_expired(
    engine: Engine | None = None, now: datetime | None = None, days: int | None = None
) -> dict[str, int]:
    """Delete videos fetched more than the retention period ago, with their votes and metadata.

    Dates are compared in Python because fetched_at is stored as an ISO 8601 string with an
    offset, and string order is not time order across offsets. A row whose date cannot be
    read is deleted: when the age is unknown the safe choice is to remove it.
    """
    engine = engine or get_engine()
    cutoff = cutoff_iso(days, now)
    with Session(engine) as session:
        rows = session.execute(
            select(MatchupVideoRecord.id, MatchupVideoRecord.fetched_at)
        ).all()
        expired = []
        for record_id, fetched_at in rows:
            fetched = parse_iso(fetched_at)
            if fetched is None or fetched <= cutoff:
                expired.append(record_id)

        counts = {"videos": 0, "votes": 0, "metadata": 0}
        # Delete in batches so one statement never carries an unbounded id list.
        for start in range(0, len(expired), 200):
            batch = expired[start : start + 200]
            counts["votes"] += session.execute(
                delete(MatchupVideoVoteRecord).where(
                    MatchupVideoVoteRecord.video_record_id.in_(batch)
                )
            ).rowcount
            counts["metadata"] += session.execute(
                delete(MatchupVideoMetadataRecord).where(
                    MatchupVideoMetadataRecord.video_record_id.in_(batch)
                )
            ).rowcount
            counts["videos"] += session.execute(
                delete(MatchupVideoRecord).where(MatchupVideoRecord.id.in_(batch))
            ).rowcount
        session.commit()

    logger.info("Retention purge removed %s (limit %s days)", counts, days or retention_days())
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    counts = purge_expired()
    print(f"retention purge ok: {counts}")


if __name__ == "__main__":
    main()
