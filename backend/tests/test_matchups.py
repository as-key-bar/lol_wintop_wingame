import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app import matchups
from app.main import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


@pytest.fixture(autouse=True)
def clear_matchup_cache():
    matchups.load_matchups.cache_clear()
    yield
    matchups.load_matchups.cache_clear()


def test_matchup_returns_empty_items_for_valid_champions_without_replays() -> None:
    response = get("/api/v1/matchups/Aatrox/Darius")

    assert response.status_code == 200
    assert response.json() == {
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
        "items": [],
    }


def test_matchup_returns_catalog_entries_from_playlist() -> None:
    response = get("/api/v1/matchups/Darius/KSante")

    assert response.status_code == 200
    body = response.json()
    assert body["playerChampionId"] == "Darius"
    assert body["opponentChampionId"] == "KSante"
    assert len(body["items"]) >= 1
    assert all(item["verificationStatus"] == "verified" for item in body["items"])


def test_matchup_returns_404_for_unknown_champion() -> None:
    unknown_player = get("/api/v1/matchups/NotAChampion/Darius")
    unknown_opponent = get("/api/v1/matchups/Aatrox/NotAChampion")

    for response in (unknown_player, unknown_opponent):
        assert response.status_code == 404
        assert response.json() == {
            "detail": {
                "code": "unknown_champion",
                "message": "指定されたチャンピオンが見つかりません。",
            }
        }


def test_matchup_returns_only_verified_ordered_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_data = {
        "items": [
            {
                "id": "aatrox-vs-darius-verified",
                "playerChampionId": "Aatrox",
                "opponentChampionId": "Darius",
                "title": "Aatrox Top vs Darius - KR Challenger",
                "videoUrl": "https://www.youtube.com/watch?v=abc123XYZ",
                "channelName": "Challenger Replays",
                "channelUrl": "https://www.youtube.com/@ChallengerReplays",
                "publishedAt": "2026-11-01T12:00:00Z",
                "gamePatch": "16.22",
                "verifiedAt": "2026-11-10T18:00:00+09:00",
                "verificationStatus": "verified",
                "embedStatus": "unknown",
                "sourceUrl": "https://www.youtube.com/@ChallengerReplays/playlists",
            },
            {
                "id": "aatrox-vs-darius-candidate",
                "playerChampionId": "Aatrox",
                "opponentChampionId": "Darius",
                "title": "Unverified Aatrox vs Darius",
                "videoUrl": "https://www.youtube.com/watch?v=candidate999",
                "channelName": "Challenger Replays",
                "channelUrl": "https://www.youtube.com/@ChallengerReplays",
                "publishedAt": None,
                "gamePatch": None,
                "verifiedAt": "2026-11-10T18:00:00+09:00",
                "verificationStatus": "candidate",
                "embedStatus": "unknown",
                "sourceUrl": "https://www.youtube.com/@ChallengerReplays/playlists",
            },
            {
                "id": "darius-vs-aatrox-reverse",
                "playerChampionId": "Darius",
                "opponentChampionId": "Aatrox",
                "title": "Darius Top vs Aatrox - KR Challenger",
                "videoUrl": "https://www.youtube.com/watch?v=reverse456",
                "channelName": "Challenger Replays",
                "channelUrl": "https://www.youtube.com/@ChallengerReplays",
                "publishedAt": None,
                "gamePatch": "16.22",
                "verifiedAt": "2026-11-10T18:00:00+09:00",
                "verificationStatus": "verified",
                "embedStatus": "allowed",
                "sourceUrl": "https://www.youtube.com/@ChallengerReplays/playlists",
            },
        ]
    }
    data_file = tmp_path / "matchups.json"
    data_file.write_text(json.dumps(sample_data), encoding="utf-8")
    monkeypatch.setattr(matchups, "MATCHUPS_PATH", data_file)

    forward = get("/api/v1/matchups/Aatrox/Darius")
    reverse = get("/api/v1/matchups/Darius/Aatrox")

    assert forward.status_code == 200
    assert [item["id"] for item in forward.json()["items"]] == [
        "aatrox-vs-darius-verified"
    ]
    assert reverse.status_code == 200
    assert [item["id"] for item in reverse.json()["items"]] == [
        "darius-vs-aatrox-reverse"
    ]


def test_matchup_returns_503_when_data_source_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid_data = {
        "items": [
            {
                "id": "bad-video-url",
                "playerChampionId": "Aatrox",
                "opponentChampionId": "Darius",
                "title": "Direct MP4 link is forbidden",
                "videoUrl": "https://example.com/replay.mp4",
                "channelName": "Challenger Replays",
                "channelUrl": "https://www.youtube.com/@ChallengerReplays",
                "publishedAt": None,
                "gamePatch": None,
                "verifiedAt": "2026-11-10T18:00:00+09:00",
                "verificationStatus": "verified",
                "embedStatus": "unknown",
                "sourceUrl": "https://www.youtube.com/@ChallengerReplays/playlists",
            }
        ]
    }
    data_file = tmp_path / "matchups.json"
    data_file.write_text(json.dumps(invalid_data), encoding="utf-8")
    monkeypatch.setattr(matchups, "MATCHUPS_PATH", data_file)

    response = get("/api/v1/matchups/Aatrox/Darius")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "matchup_data_unavailable",
            "message": "マッチアップデータを読み込めませんでした。",
        }
    }

