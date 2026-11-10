import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen

DATA_DRAGON = "https://ddragon.leagueoflegends.com"
OUTPUT = Path(__file__).resolve().parents[1] / "backend/src/app/data/champions.json"


def fetch_json(url: str) -> Any:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def main() -> None:
    versions = fetch_json(f"{DATA_DRAGON}/api/versions.json")
    if not isinstance(versions, list) or not versions or not isinstance(versions[0], str):
        raise ValueError("Data Dragon returned an invalid version list")
    version = versions[0]

    locale_data = {}
    source_urls = {}
    for locale in ("ja_JP", "en_US"):
        source_url = f"{DATA_DRAGON}/cdn/{version}/data/{locale}/champion.json"
        payload = fetch_json(source_url)
        if payload.get("version") != version or not isinstance(payload.get("data"), dict):
            raise ValueError(f"Data Dragon returned invalid {locale} champion data")
        locale_data[locale] = payload["data"]
        source_urls[locale] = source_url

    japanese = locale_data["ja_JP"]
    english = locale_data["en_US"]
    if japanese.keys() != english.keys():
        raise ValueError("Champion IDs differ between ja_JP and en_US data")

    items = []
    for champion_id in sorted(japanese):
        ja_entry = japanese[champion_id]
        en_entry = english[champion_id]
        image = ja_entry.get("image", {}).get("full")
        if not image or not ja_entry.get("name") or not en_entry.get("name"):
            raise ValueError(f"Incomplete champion data for {champion_id}")
        items.append(
            {
                "id": champion_id,
                "nameJa": ja_entry["name"],
                "nameEn": en_entry["name"],
                "aliases": [],
                "imageUrl": f"{DATA_DRAGON}/cdn/{version}/img/champion/{image}",
                "dataDragonVersion": version,
                "sourceUrl": source_urls["ja_JP"],
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {"dataDragonVersion": version, "items": items},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} champions for Data Dragon {version} to {OUTPUT}")


if __name__ == "__main__":
    main()
