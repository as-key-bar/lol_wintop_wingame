import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen

DATA_DRAGON = "https://ddragon.leagueoflegends.com"
OUTPUT = Path(__file__).resolve().parents[1] / "backend/src/app/data/game_assets.json"

# Standard Stat Shards (3 rows x 3 choices in modern League of Legends)
STAT_SHARD_ROWS = [
    [
        {
            "id": 5008,
            "key": "AdaptiveForce",
            "nameJa": "アダプティブフォース",
            "nameEn": "Adaptive Force",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsAdaptiveForceIcon.png",
        },
        {
            "id": 5005,
            "key": "AttackSpeed",
            "nameJa": "攻撃速度",
            "nameEn": "Attack Speed",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsAttackSpeedIcon.png",
        },
        {
            "id": 5007,
            "key": "AbilityHaste",
            "nameJa": "スキルヘイスト",
            "nameEn": "Ability Haste",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsCDRScalingIcon.png",
        },
    ],
    [
        {
            "id": 5008,
            "key": "AdaptiveForce",
            "nameJa": "アダプティブフォース",
            "nameEn": "Adaptive Force",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsAdaptiveForceIcon.png",
        },
        {
            "id": 5010,
            "key": "MoveSpeed",
            "nameJa": "移動速度",
            "nameEn": "Move Speed",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsMovementSpeedIcon.png",
        },
        {
            "id": 5001,
            "key": "HealthScaling",
            "nameJa": "体力（スケーリング）",
            "nameEn": "Health Scaling",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsHealthPlusIcon.png",
        },
    ],
    [
        {
            "id": 5011,
            "key": "HealthFlat",
            "nameJa": "体力",
            "nameEn": "Health",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsHealthScalingIcon.png",
        },
        {
            "id": 5013,
            "key": "Tenacity",
            "nameJa": "行動妨害耐性＆スロウ耐性",
            "nameEn": "Tenacity and Slow Resist",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsTenacityIcon.png",
        },
        {
            "id": 5001,
            "key": "HealthScaling",
            "nameJa": "体力（スケーリング）",
            "nameEn": "Health Scaling",
            "iconUrl": f"{DATA_DRAGON}/cdn/img/perk-images/StatMods/StatModsHealthPlusIcon.png",
        },
    ],
]

# Common starting / early lane items for Top Lane
STARTER_ITEM_IDS = {
    "1054",  # Doran's Shield
    "1055",  # Doran's Blade
    "1056",  # Doran's Ring
    "1082",  # Dark Seal
    "1083",  # Cull
    "1036",  # Long Sword
    "1029",  # Cloth Armor
    "1028",  # Ruby Crystal
    "1027",  # Sapphire Crystal
    "1001",  # Boots
    "2003",  # Health Potion
    "2031",  # Refillable Potion
    "3070",  # Tear of the Goddess
}


# Legacy rune names kept as search aliases so older replay descriptions still resolve
# to the current Data Dragon rune (e.g. "Phase Rush" -> Stormraider's Surge).
RUNE_LEGACY_ALIASES: dict[int, list[str]] = {
    8230: ["Phase Rush", "フェイズラッシュ"],
}


def fetch_json(url: str) -> Any:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def build_rune_styles(version: str) -> list[dict[str, Any]]:
    ja_styles = fetch_json(
        f"{DATA_DRAGON}/cdn/{version}/data/ja_JP/runesReforged.json"
    )
    en_styles = fetch_json(
        f"{DATA_DRAGON}/cdn/{version}/data/en_US/runesReforged.json"
    )
    en_by_id = {style["id"]: style for style in en_styles}

    en_runes_by_id: dict[int, dict[str, Any]] = {}
    for style in en_styles:
        for slot in style.get("slots", []):
            for rune in slot.get("runes", []):
                en_runes_by_id[rune["id"]] = rune

    styles: list[dict[str, Any]] = []
    for ja_style in ja_styles:
        style_id = ja_style["id"]
        en_style = en_by_id[style_id]
        slots: list[dict[str, Any]] = []
        for slot_index, ja_slot in enumerate(ja_style.get("slots", [])):
            runes = []
            for ja_rune in ja_slot.get("runes", []):
                rune_id = ja_rune["id"]
                en_rune = en_runes_by_id[rune_id]
                runes.append(
                    {
                        "id": rune_id,
                        "key": ja_rune["key"],
                        "nameJa": ja_rune["name"],
                        "nameEn": en_rune["name"],
                        "aliases": RUNE_LEGACY_ALIASES.get(rune_id, []),
                        "iconUrl": f"{DATA_DRAGON}/cdn/img/{ja_rune['icon']}",
                        "slotIndex": slot_index,
                    }
                )
            slots.append({"slotIndex": slot_index, "runes": runes})

        styles.append(
            {
                "id": style_id,
                "key": ja_style["key"],
                "nameJa": ja_style["name"],
                "nameEn": en_style["name"],
                "iconUrl": f"{DATA_DRAGON}/cdn/img/{ja_style['icon']}",
                "slots": slots,
            }
        )

    return styles


def build_summoner_spells(version: str) -> list[dict[str, Any]]:
    ja_data = fetch_json(f"{DATA_DRAGON}/cdn/{version}/data/ja_JP/summoner.json")[
        "data"
    ]
    en_data = fetch_json(f"{DATA_DRAGON}/cdn/{version}/data/en_US/summoner.json")[
        "data"
    ]

    spells: list[dict[str, Any]] = []
    for spell_id, ja_entry in sorted(ja_data.items()):
        modes = ja_entry.get("modes", [])
        if "CLASSIC" not in modes:
            continue
        en_entry = en_data.get(spell_id, ja_entry)
        image_full = ja_entry.get("image", {}).get("full")
        if not image_full:
            continue
        spells.append(
            {
                "id": spell_id,
                "key": ja_entry["key"],
                "nameJa": ja_entry["name"],
                "nameEn": en_entry["name"],
                "iconUrl": f"{DATA_DRAGON}/cdn/{version}/img/spell/{image_full}",
            }
        )
    return spells


def build_starter_items(version: str) -> list[dict[str, Any]]:
    ja_data = fetch_json(f"{DATA_DRAGON}/cdn/{version}/data/ja_JP/item.json")["data"]
    en_data = fetch_json(f"{DATA_DRAGON}/cdn/{version}/data/en_US/item.json")["data"]

    items: list[dict[str, Any]] = []
    for item_id in sorted(STARTER_ITEM_IDS):
        ja_entry = ja_data.get(item_id)
        en_entry = en_data.get(item_id)
        if not ja_entry or not en_entry:
            continue
        image_full = ja_entry.get("image", {}).get("full")
        if not image_full:
            continue
        items.append(
            {
                "id": item_id,
                "nameJa": ja_entry["name"],
                "nameEn": en_entry["name"],
                "gold": ja_entry.get("gold", {}).get("total", 0),
                "iconUrl": f"{DATA_DRAGON}/cdn/{version}/img/item/{image_full}",
            }
        )
    return items


def main() -> None:
    versions = fetch_json(f"{DATA_DRAGON}/api/versions.json")
    if not isinstance(versions, list) or not versions or not isinstance(versions[0], str):
        raise ValueError("Data Dragon returned an invalid version list")
    version = versions[0]

    rune_styles = build_rune_styles(version)
    summoner_spells = build_summoner_spells(version)
    starter_items = build_starter_items(version)

    payload = {
        "dataDragonVersion": version,
        "sourceUrl": f"{DATA_DRAGON}/cdn/{version}/data/ja_JP/runesReforged.json",
        "runeStyles": rune_styles,
        "statShardRows": STAT_SHARD_ROWS,
        "summonerSpells": summoner_spells,
        "starterItems": starter_items,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(rune_styles)} rune styles, {len(summoner_spells)} summoner spells, "
        f"and {len(starter_items)} starter items for Data Dragon {version} to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
