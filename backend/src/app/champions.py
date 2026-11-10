import json
import logging
import unicodedata
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.romanization import normalize_romaji, romanize_japanese

logger = logging.getLogger(__name__)
CATALOG_PATH = Path(__file__).parent / "data" / "champions.json"


class Champion(BaseModel):
    id: str
    nameJa: str
    nameEn: str
    aliases: list[str]
    imageUrl: str
    dataDragonVersion: str
    sourceUrl: str


@lru_cache(maxsize=1)
def load_catalog() -> tuple[str, tuple[Champion, ...]]:
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        version = payload["dataDragonVersion"]
        champions = tuple(Champion.model_validate(item) for item in payload["items"])
        if not isinstance(version, str) or not champions:
            raise ValueError("Champion catalog is empty or has no version")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValidationError, ValueError) as error:
        logger.exception("Failed to load champion catalog")
        raise RuntimeError("Champion catalog is unavailable") from error

    return version, champions


def search_champions(query: str | None = None) -> tuple[str, list[Champion]]:
    version, champions = load_catalog()
    normalized_query = unicodedata.normalize("NFKC", query or "").strip().casefold()
    if not normalized_query:
        return version, list(champions)

    normalized_romaji_query = normalize_romaji(query or "")
    results = [
        champion
        for champion in champions
        if any(
            normalized_query in unicodedata.normalize("NFKC", value).casefold()
            for value in (champion.nameJa, champion.nameEn, *champion.aliases)
        )
        or (
            normalized_romaji_query
            and normalized_romaji_query
            in normalize_romaji(romanize_japanese(champion.nameJa))
        )
    ]
    return version, results
