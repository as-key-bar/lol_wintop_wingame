import json
from pathlib import Path

import pytest

from app import matchups, youtube_search
from app.champions import load_catalog
from conftest import api_get as get


@pytest.fixture(autouse=True)
def clear_matchup_cache(monkeypatch: pytest.MonkeyPatch):
    matchups.load_matchups.cache_clear()
    youtube_search._cached_youtube_search.cache_clear()
    monkeypatch.setattr(
        matchups, "search_youtube_matchup_candidates", lambda *args, **kwargs: []
    )
    yield
    matchups.load_matchups.cache_clear()
    youtube_search._cached_youtube_search.cache_clear()


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


def test_matchup_does_not_call_youtube_when_saved_replay_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "YouTube search must not be called when saved replays already exist"
        )

    monkeypatch.setattr(
        matchups, "search_youtube_matchup_candidates", fail_if_called
    )

    # Singed vs TahmKench has only 1 saved replay in matchups.json, and must still skip YouTube search.
    response = get("/api/v1/matchups/Singed/TahmKench")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["origin"] == "saved"


def test_matchup_fetches_additional_candidates_only_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        matchups,
        "search_youtube_matchup_candidates",
        lambda player_champion_id, opponent_champion_id, max_results=5: [
            {
                "id": "yt-singed-vs-tahmkench-extra1",
                "playerChampionId": player_champion_id,
                "opponentChampionId": opponent_champion_id,
                "title": "Singed Top vs Tahm Kench - EUW Challenger Patch 26.22",
                "videoUrl": "https://www.youtube.com/watch?v=extra1",
                "channelName": "Challenger Replays",
                "channelUrl": "https://www.youtube.com/@ChallengerReplays",
                "publishedAt": None,
                "gamePatch": "26.22",
                "verifiedAt": "2026-11-11T11:40:00+09:00",
                "verificationStatus": "verified",
                "embedStatus": "unknown",
                "sourceUrl": "https://www.youtube.com/results?search_query=Singed+Top+vs+Tahm+Kench",
                "origin": "youtube_search",
            }
        ],
    )

    response = get("/api/v1/matchups/Singed/TahmKench?includeCandidates=true")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert [item["origin"] for item in items] == ["saved", "youtube_search"]


def test_matchup_includes_youtube_search_candidates_when_saved_replays_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        matchups,
        "search_youtube_matchup_candidates",
        lambda player_champion_id, opponent_champion_id, max_results=5: [
            {
                "id": "yt-aatrox-vs-darius-live123",
                "playerChampionId": player_champion_id,
                "opponentChampionId": opponent_champion_id,
                "title": "Aatrox Top vs Darius - KR Challenger Patch 26.22",
                "videoUrl": "https://www.youtube.com/watch?v=live123",
                "channelName": "Challenger Replays",
                "channelUrl": "https://www.youtube.com/@ChallengerReplays",
                "publishedAt": None,
                "gamePatch": "26.22",
                "verifiedAt": "2026-11-11T11:40:00+09:00",
                "verificationStatus": "verified",
                "embedStatus": "unknown",
                "sourceUrl": "https://www.youtube.com/results?search_query=Aatrox+Top+vs+Darius",
                "origin": "youtube_search",
            }
        ],
    )

    response = get("/api/v1/matchups/Aatrox/Darius")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "yt-aatrox-vs-darius-live123"
    assert items[0]["origin"] == "youtube_search"


def test_parse_youtube_initial_data_filters_by_ordered_matchup() -> None:
    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    aatrox = by_id["Aatrox"]
    darius = by_id["Darius"]

    fake_initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "matchForward1",
                                                "title": {
                                                    "runs": [
                                                        {
                                                            "text": "Aatrox Top vs Darius - KR Challenger Patch 26.22"
                                                        }
                                                    ]
                                                },
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Challenger Replays",
                                                            "navigationEndpoint": {
                                                                "browseEndpoint": {
                                                                    "canonicalBaseUrl": "/@ChallengerReplays"
                                                                }
                                                            },
                                                        }
                                                    ]
                                                },
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "matchReverse2",
                                                "title": {
                                                    "runs": [
                                                        {
                                                            "text": "Darius Top vs Aatrox - KR Challenger Patch 26.22"
                                                        }
                                                    ]
                                                },
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Challenger Replays"
                                                        }
                                                    ]
                                                },
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    html = f"<script>var ytInitialData = {json.dumps(fake_initial_data)};</script>"
    parsed = youtube_search.parse_youtube_initial_data(
        html_text=html,
        player=aatrox,
        opponent=darius,
        source_url="https://www.youtube.com/results?search_query=Aatrox+Top+vs+Darius",
    )

    assert len(parsed) == 1
    assert parsed[0]["videoUrl"] == "https://www.youtube.com/watch?v=matchForward1"
    assert parsed[0]["gamePatch"] == "26.22"
    assert parsed[0]["origin"] == "youtube_search"


def test_parse_youtube_initial_data_filters_lane_duration_and_sorts_by_patch_and_rank() -> None:
    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    aatrox = by_id["Aatrox"]
    darius = by_id["Darius"]

    def make_renderer(
        video_id: str,
        title: str,
        duration: str = "28:15",
        channel: str = "Challenger Replays",
    ) -> dict:
        return {
            "videoRenderer": {
                "videoId": video_id,
                "lengthText": {"simpleText": duration},
                "title": {"runs": [{"text": title}]},
                "ownerText": {"runs": [{"text": channel}]},
            }
        }

    fake_initial_data = {
        "contents": {
            "sectionListRenderer": {
                "contents": [
                    {
                        "itemSectionRenderer": {
                            "contents": [
                                # Excluded: Mid lane instead of Top
                                make_renderer(
                                    "midLane1",
                                    "Aatrox Mid vs Darius - KR Challenger Patch 26.22",
                                ),
                                # Excluded: Missing Top keyword
                                make_renderer(
                                    "noLane1",
                                    "Aatrox vs Darius - KR Challenger Patch 26.22",
                                ),
                                # Excluded: Shorter than 10 minutes (clip/short)
                                make_renderer(
                                    "shortClip1",
                                    "Aatrox Top vs Darius - KR Challenger Patch 26.22",
                                    duration="3:45",
                                ),
                                # Excluded: Montage/Highlights
                                make_renderer(
                                    "montage1",
                                    "Aatrox Top vs Darius Highlights - Patch 26.22",
                                    duration="12:00",
                                ),
                                # Included (Rank #3: no patch)
                                make_renderer(
                                    "noPatchOld",
                                    "Aatrox Top vs Darius - KR Challenger",
                                    duration="25:00",
                                ),
                                # Included (Rank #2: Patch 26.21 Challenger)
                                make_renderer(
                                    "patch2621Chall",
                                    "Aatrox Top vs Darius - KR Challenger Patch 26.21",
                                    duration="26:30",
                                ),
                                # Included (Rank #2b: Patch 26.22 Master)
                                make_renderer(
                                    "patch2622Master",
                                    "Aatrox Top vs Darius - KR Master Patch 26.22",
                                    duration="29:10",
                                ),
                                # Included (Rank #1: Patch 26.22 Challenger)
                                make_renderer(
                                    "patch2622Chall",
                                    "Aatrox Top vs Darius - KR Challenger Patch 26.22",
                                    duration="31:00",
                                ),
                            ]
                        }
                    }
                ]
            }
        }
    }

    html = f"<script>var ytInitialData = {json.dumps(fake_initial_data)};</script>"
    parsed = youtube_search.parse_youtube_initial_data(
        html_text=html,
        player=aatrox,
        opponent=darius,
        source_url="https://www.youtube.com/results?search_query=Aatrox+Top+vs+Darius",
    )

    assert [item["videoUrl"].split("v=")[1] for item in parsed] == [
        "patch2622Chall",
        "patch2622Master",
        "patch2621Chall",
        "noPatchOld",
    ]


def test_title_matches_matchup_uses_word_boundaries_for_short_champion_names() -> None:
    _, champions = load_catalog()
    by_id = {champion.id: champion for champion in champions}
    vi = by_id["Vi"]
    darius = by_id["Darius"]

    assert not youtube_search.title_matches_matchup(
        "Riven Top vs Darius - KR Challenger Patch 26.22", vi, darius
    )
    assert youtube_search.title_matches_matchup(
        "Vi Top vs Darius - KR Challenger Patch 26.22", vi, darius
    )

