import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app import database, matchups, video_analysis, youtube_search
from app.champions import load_catalog
from conftest import api_get as get, api_post as post, api_put as put


@pytest.fixture(autouse=True)
def clear_matchup_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test_matchups.db'}", future=True)
    database.set_engine(engine)
    matchups.clear_seeded_cache()
    matchups.load_matchups.cache_clear()
    youtube_search.clear_search_cache()
    monkeypatch.setattr(
        matchups, "search_youtube_matchup_candidates", lambda *args, **kwargs: []
    )
    monkeypatch.setattr(
        matchups,
        "fetch_and_analyze_youtube_video",
        lambda *args, **kwargs: video_analysis.VideoMetadataAnalysis(),
    )
    from app.rate_limit import limiter

    limiter.reset()
    monkeypatch.setenv("RATE_LIMIT_MULTIPLIER", "0")
    yield
    limiter.reset()
    engine.dispose()
    database.set_engine(None)
    matchups.clear_seeded_cache()
    matchups.load_matchups.cache_clear()
    youtube_search.clear_search_cache()


def test_matchup_returns_empty_items_for_valid_champions_without_replays() -> None:
    response = get("/api/v1/matchups/Aatrox/Darius")

    assert response.status_code == 200
    assert response.json() == {
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
        "items": [],
    }


def _offer_as_candidates(monkeypatch: pytest.MonkeyPatch, *videos: dict) -> None:
    offered = {
        (v["playerChampionId"], v["opponentChampionId"], v["videoUrl"]) for v in videos
    }
    monkeypatch.setattr(
        matchups,
        "was_offered_as_candidate",
        lambda player, opponent, url: (player, opponent, url) in offered,
    )


def _seed_item(video_id: str, player: str, opponent: str) -> dict:
    return {
        "id": f"{player.lower()}-vs-{opponent.lower()}-{video_id}",
        "playerChampionId": player,
        "opponentChampionId": opponent,
        "title": f"{player} Top vs {opponent} - KR Master Patch 26.16",
        "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
        "channelName": "Example Channel",
        "channelUrl": "https://www.youtube.com/@example",
        "publishedAt": None,
        "gamePatch": "26.16",
        "verifiedAt": "2026-11-11T11:40:00+09:00",
        "verificationStatus": "verified",
        "embedStatus": "unknown",
        "sourceUrl": "https://www.youtube.com/@example/playlists",
    }


def _use_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, items: list[dict]) -> None:
    data_file = tmp_path / "seed_matchups.json"
    data_file.write_text(json.dumps({"items": items}), encoding="utf-8")
    monkeypatch.setattr(matchups, "MATCHUPS_PATH", data_file)
    matchups.load_matchups.cache_clear()
    matchups.clear_seeded_cache()


def test_shipped_seed_catalog_is_empty_and_valid() -> None:
    payload = json.loads(matchups.MATCHUPS_PATH.read_text(encoding="utf-8"))

    assert payload == {"items": []}
    assert matchups.load_matchups() == ()


def test_matchup_returns_seeded_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_seed(tmp_path, monkeypatch, [_seed_item("seedvideo01", "Darius", "KSante")])

    response = get("/api/v1/matchups/Darius/KSante")

    assert response.status_code == 200
    body = response.json()
    assert body["playerChampionId"] == "Darius"
    assert body["opponentChampionId"] == "KSante"
    assert len(body["items"]) == 1
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
                "videoUrl": "https://www.youtube.com/watch?v=abcdef12345XYZ",
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_seed(tmp_path, monkeypatch, [_seed_item("seedvideo02", "Singed", "TahmKench")])

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "YouTube search must not be called when saved replays already exist"
        )

    monkeypatch.setattr(
        matchups, "search_youtube_matchup_candidates", fail_if_called
    )

    # A single saved replay is enough to skip the YouTube search.
    response = get("/api/v1/matchups/Singed/TahmKench")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["origin"] == "saved"


def test_matchup_fetches_additional_candidates_only_when_explicitly_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_seed(tmp_path, monkeypatch, [_seed_item("seedvideo03", "Singed", "TahmKench")])

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


def test_upvote_persists_youtube_candidate_to_database_and_toggles_vote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_payload = {
        "id": "yt-aatrox-vs-darius-live123",
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
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

    _offer_as_candidates(monkeypatch, candidate_payload)

    # 1. Upvote a YouTube candidate video
    upvote_response = post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-token-alpha-12345", "video": candidate_payload},
    )
    assert upvote_response.status_code == 200
    saved_item = upvote_response.json()
    assert saved_item["id"] == "yt-aatrox-vs-darius-live123"
    assert saved_item["origin"] == "saved"
    assert saved_item["upvoteCount"] == 1
    assert saved_item["upvotedByViewer"] is True

    # 2. Subsequent matchup search must return the DB-saved video WITHOUT calling YouTube
    def fail_if_youtube_called(*args, **kwargs):
        raise AssertionError("YouTube must not be queried after candidate is saved to DB")

    monkeypatch.setattr(
        matchups, "search_youtube_matchup_candidates", fail_if_youtube_called
    )

    get_response = get(
        "/api/v1/matchups/Aatrox/Darius?voterToken=voter-token-alpha-12345"
    )
    assert get_response.status_code == 200
    items = get_response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == "yt-aatrox-vs-darius-live123"
    assert items[0]["origin"] == "saved"
    assert items[0]["upvoteCount"] == 1
    assert items[0]["upvotedByViewer"] is True

    # 3. Clicking upvote again with the same voterToken toggles (removes) the vote
    unvote_response = post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-token-alpha-12345", "video": saved_item},
    )
    assert unvote_response.status_code == 200
    unvoted_item = unvote_response.json()
    assert unvoted_item["upvoteCount"] == 0
    assert unvoted_item["upvotedByViewer"] is False


def test_saved_videos_are_sorted_by_upvote_count_descending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    video_older_patch = {
        "id": "yt-aatrox-vs-darius-older",
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
        "title": "Aatrox Top vs Darius - KR Master Patch 26.20",
        "videoUrl": "https://www.youtube.com/watch?v=older20",
        "channelName": "Challenger Replays",
        "channelUrl": "https://www.youtube.com/@ChallengerReplays",
        "publishedAt": None,
        "gamePatch": "26.20",
        "verifiedAt": "2026-11-11T11:40:00+09:00",
        "verificationStatus": "verified",
        "embedStatus": "unknown",
        "sourceUrl": "https://www.youtube.com/results?search_query=Aatrox+Top+vs+Darius",
        "origin": "youtube_search",
    }
    video_newer_patch = {
        "id": "yt-aatrox-vs-darius-newer",
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
        "title": "Aatrox Top vs Darius - KR Challenger Patch 26.22",
        "videoUrl": "https://www.youtube.com/watch?v=newer22",
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

    _offer_as_candidates(monkeypatch, video_older_patch, video_newer_patch)

    # Save newer patch with 1 vote, older patch with 2 votes
    post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-one-12345", "video": video_newer_patch},
    )
    post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-one-12345", "video": video_older_patch},
    )
    post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-two-67890", "video": video_older_patch},
    )

    response = get("/api/v1/matchups/Aatrox/Darius")
    assert response.status_code == 200
    items = response.json()["items"]
    # Stored ids are derived from the YouTube video id, not from the client-supplied id.
    assert [item["id"] for item in items] == [
        "yt-aatrox-vs-darius-older20",
        "yt-aatrox-vs-darius-newer22",
    ]
    assert [item["upvoteCount"] for item in items] == [2, 1]


def test_upvote_rejects_mismatched_title_for_matchup() -> None:
    bad_video = {
        "id": "yt-bad-matchup",
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
        "title": "Garen Top vs Teemo - KR Challenger Patch 26.22",
        "videoUrl": "https://www.youtube.com/watch?v=badmatch1",
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

    response = post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-one-12345", "video": bad_video},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_upvote"


def test_parse_youtube_description_metadata_extracts_runes_spells_and_kill_timestamps() -> None:
    sample_description = """
#Singed #Top #Grandmaster
Singed Top vs Tahm Kench — 8/5/14 (WIN) | KR Grandmaster 1510 LP
Skin: Astronaut Singed | Spells: Ignite Flash
Runes: Precision - Conqueror, Triumph, Legend: Alacrity, Last Stand | Sorcery - Nimbus Cloak, Celerity | Shards - Adaptive Force, Adaptive Force, Health

Timeline:
0:00 Game Start
03:02 Singed catches Tahm Kench
05:03 Red takes 1st Dragon (Cloud)
06:06 Singed outduels Tahm Kench again
29:56 Victory
"""
    analysis = video_analysis.parse_youtube_description_metadata(sample_description)

    assert analysis.analysisStatus == "auto_parsed"
    assert analysis.summonerSpells == ["SummonerDot", "SummonerFlash"]
    assert analysis.runes is not None
    assert analysis.runes.primaryStyleId == 8000  # Precision
    assert analysis.runes.subStyleId == 8200  # Sorcery
    assert analysis.runes.primarySelections == [8010, 9111, 9104, 8299]
    assert analysis.runes.subSelections == [8275, 8234]
    assert len(analysis.runes.statShards) == 3

    assert len(analysis.timestamps) == 5
    kill_events = [ts for ts in analysis.timestamps if ts.isKillEvent]
    assert [ts.timeSeconds for ts in kill_events] == [182, 366]


def test_extract_description_with_embedded_semicolons_and_compact_format() -> None:
    # Simulate a YouTube player response containing ";}" inside JSON string values
    # and the compact "| Grasp of the Undying + Precision | Ignite Flash" format
    # seen in Tahm Kench vs Gwen.
    fake_player_response = {
        "responseContext": {"nested": "value;}with_semicolon_brace"},
        "videoDetails": {
            "shortDescription": (
                "#TahmKench #Top #Master\n"
                "Tahm Kench Top vs Gwen — 12/1/9 (WIN) | KR Master 437 LP\n"
                "Skin: Tahm Kench | Grasp of the Undying + Precision | Ignite Flash\n"
                "Build: Dusk and Dawn, Randuin's Omen, Heartsteel\n\n"
                "Timeline:\n"
                "00:00 Game Start\n"
                "02:26 First Blood — Tahm Kench kills Gwen\n"
            )
        },
    }
    html = (
        "<script>var ytInitialPlayerResponse = "
        + json.dumps(fake_player_response)
        + ";var other = 1;</script>"
    )
    extracted = video_analysis.extract_description_from_watch_html(html)
    assert "Grasp of the Undying" in extracted

    parsed = video_analysis.parse_youtube_description_metadata(extracted)
    assert parsed.analysisStatus == "auto_parsed"
    assert parsed.summonerSpells == ["SummonerDot", "SummonerFlash"]
    assert parsed.runes is not None
    assert parsed.runes.primaryStyleId == 8400  # Resolve
    assert parsed.runes.subStyleId == 8000  # Precision
    assert parsed.runes.primarySelections == [8437]  # Grasp of the Undying
    assert len(parsed.timestamps) == 2
    assert parsed.timestamps[1].isKillEvent is True


def test_game_assets_and_manual_metadata_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
    assets_response = get("/api/v1/game-assets")
    assert assets_response.status_code == 200
    assets_data = assets_response.json()
    assert len(assets_data["runeStyles"]) == 5
    assert len(assets_data["summonerSpells"]) >= 8
    assert len(assets_data["starterItems"]) >= 10

    video_payload = {
        "id": "yt-aatrox-vs-darius-metavideo01",
        "playerChampionId": "Aatrox",
        "opponentChampionId": "Darius",
        "title": "Aatrox Top vs Darius - KR Challenger Patch 26.22",
        "videoUrl": "https://www.youtube.com/watch?v=metavideo01",
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
    metadata_payload = {
        "analysisStatus": "manual_verified",
        "runes": {
            "primaryStyleId": 8000,
            "subStyleId": 8400,
            "primarySelections": [8010, 9111, 9104, 8299],
            "subSelections": [8473, 8451],
            "statShards": [5008, 5008, 5001],
        },
        "summonerSpells": ["SummonerFlash", "SummonerTeleport"],
        "startingItems": ["1054", "2003"],
        "timestamps": [
            {
                "timeSeconds": 195,
                "timeLabel": "03:15",
                "label": "Aatrox Solo Kill",
                "isKillEvent": True,
            }
        ],
    }

    put_response = put(
        "/api/v1/matchups/Aatrox/Darius/metadata",
        {"video": video_payload, "metadata": metadata_payload},
        headers={"Authorization": "Bearer correct-token"},
    )
    assert put_response.status_code == 200
    assert put_response.json()["analysisStatus"] == "manual_verified"

    get_response = get("/api/v1/matchups/Aatrox/Darius")
    assert get_response.status_code == 200
    items = get_response.json()["items"]
    assert len(items) == 1
    saved_meta = items[0]["metadata"]
    assert saved_meta["analysisStatus"] == "manual_verified"
    assert saved_meta["startingItems"] == ["1054", "2003"]
    assert saved_meta["summonerSpells"] == ["SummonerFlash", "SummonerTeleport"]
    assert saved_meta["timestamps"][0]["timeSeconds"] == 195





def test_sorcery_keystones_match_current_catalog_and_legacy_alias() -> None:
    assets = video_analysis.load_game_assets()
    sorcery = next(style for style in assets["runeStyles"] if style["id"] == 8200)
    keystone_names = [rune["nameJa"] for rune in sorcery["slots"][0]["runes"]]
    assert keystone_names == ["エアリー召喚", "秘儀の彗星", "嵐乗りの勇躍", "死神の残り火"]

    current = video_analysis.parse_youtube_description_metadata(
        "Runes: Sorcery - Deathfire Touch, Manaflow Band, Transcendence, Scorch "
        "| Precision - Triumph, Legend: Haste | Shards - Adaptive Force, Adaptive Force, Health"
    )
    assert current.runes is not None
    assert current.runes.primaryStyleId == 8200
    assert current.runes.primarySelections == [8992, 8226, 8210, 8237]

    surge = video_analysis.parse_youtube_description_metadata(
        "Runes: Sorcery - Stormraider's Surge, Nimbus Cloak, Celerity, Gathering Storm"
    )
    legacy = video_analysis.parse_youtube_description_metadata(
        "Runes: Sorcery - Phase Rush, Nimbus Cloak, Celerity, Gathering Storm"
    )
    assert surge.runes is not None and legacy.runes is not None
    assert surge.runes.primarySelections[0] == 8230
    assert legacy.runes.primarySelections[0] == 8230


VIDEO_PAYLOAD = {
    "id": "yt-aatrox-vs-darius-guardvideo1",
    "playerChampionId": "Aatrox",
    "opponentChampionId": "Darius",
    "title": "Aatrox Top vs Darius - KR Challenger Patch 26.22",
    "videoUrl": "https://www.youtube.com/watch?v=guardvideo1",
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
METADATA_PAYLOAD = {
    "analysisStatus": "manual_verified",
    "runes": None,
    "summonerSpells": ["SummonerFlash", "SummonerTeleport"],
    "startingItems": ["1054"],
    "timestamps": [],
}


def test_put_metadata_is_disabled_without_server_admin_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    response = put(
        "/api/v1/matchups/Aatrox/Darius/metadata",
        {"video": VIDEO_PAYLOAD, "metadata": METADATA_PAYLOAD},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_disabled"
    assert get("/api/v1/matchups/Aatrox/Darius").json()["items"] == []


def test_put_metadata_rejects_missing_or_wrong_admin_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
    body = {"video": VIDEO_PAYLOAD, "metadata": METADATA_PAYLOAD}

    missing = put("/api/v1/matchups/Aatrox/Darius/metadata", body)
    wrong = put(
        "/api/v1/matchups/Aatrox/Darius/metadata",
        body,
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert wrong.json()["detail"]["code"] == "invalid_admin_token"
    assert get("/api/v1/matchups/Aatrox/Darius").json()["items"] == []


def test_put_metadata_accepts_valid_admin_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "correct-token")

    response = put(
        "/api/v1/matchups/Aatrox/Darius/metadata",
        {"video": VIDEO_PAYLOAD, "metadata": METADATA_PAYLOAD},
        headers={"Authorization": "Bearer correct-token"},
    )

    assert response.status_code == 200
    assert response.json()["analysisStatus"] == "manual_verified"


def test_starting_items_come_only_from_explicit_starter_items_line() -> None:
    end_of_game_build = video_analysis.parse_youtube_description_metadata(
        "Spells: Teleport Flash\n"
        "Build: Hextech Rocketbelt, Zhonya's Hourglass, Doran's Ring, Riftmaker\n"
    )
    explicit = video_analysis.parse_youtube_description_metadata(
        "Spells: Teleport Flash\n"
        "Starter Items: Doran's Ring, Health Potion\n"
        "Build: Hextech Rocketbelt\n"
    )

    assert end_of_game_build.startingItems == []
    assert explicit.startingItems == ["1056", "2003"]


def _count_fetches(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def fake_fetch(video_url: str) -> video_analysis.VideoMetadataAnalysis:
        calls.append(video_url)
        return video_analysis.VideoMetadataAnalysis(
            analysisStatus="auto_parsed", summonerSpells=["SummonerFlash"]
        )

    monkeypatch.setattr(matchups, "fetch_and_analyze_youtube_video", fake_fetch)
    return calls


def test_analyze_skips_youtube_when_metadata_already_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _count_fetches(monkeypatch)
    video = {**VIDEO_PAYLOAD, "id": "yt-aatrox-vs-darius-cache1"}
    _offer_as_candidates(monkeypatch, video)
    post_url = "/api/v1/matchups/Aatrox/Darius/upvote"
    assert (
        post(post_url, {"video": video, "voterToken": "voter-cache-12345"}).status_code
        == 200
    )
    assert len(calls) == 1

    cached = post("/api/v1/matchups/Aatrox/Darius/analyze", {"video": video})
    refreshed = post(
        "/api/v1/matchups/Aatrox/Darius/analyze", {"video": video, "refresh": True}
    )

    assert cached.status_code == 200
    assert cached.json()["analysisStatus"] == "auto_parsed"
    assert len(calls) == 2
    assert refreshed.status_code == 200


def test_analyze_never_overwrites_manually_verified_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "correct-token")
    calls = _count_fetches(monkeypatch)
    video = {**VIDEO_PAYLOAD, "id": "yt-aatrox-vs-darius-manual1"}
    put(
        "/api/v1/matchups/Aatrox/Darius/metadata",
        {"video": video, "metadata": METADATA_PAYLOAD},
        headers={"Authorization": "Bearer correct-token"},
    )

    response = post(
        "/api/v1/matchups/Aatrox/Darius/analyze", {"video": video, "refresh": True}
    )

    assert calls == []
    assert response.json()["analysisStatus"] == "manual_verified"
    assert response.json()["startingItems"] == ["1054"]


def test_stat_shard_rows_match_current_game_layout() -> None:
    # Verified against CommunityDragon perkstyles.json (Offense / Flex / Defense) on 2026-11-17.
    rows = video_analysis.load_game_assets()["statShardRows"]

    assert [[shard["id"] for shard in row] for row in rows] == [
        [5008, 5005, 5007],
        [5008, 5010, 5001],
        [5011, 5013, 5001],
    ]


def test_description_is_fetched_via_data_api_when_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "items": [
                        {
                            "snippet": {
                                "description": "Spells: Teleport Flash\n"
                            }
                        }
                    ]
                }
            ).encode()

    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(video_analysis, "urlopen", fake_urlopen)

    analysis = video_analysis.fetch_and_analyze_youtube_video(
        "https://www.youtube.com/watch?v=abcdef12345"
    )

    assert seen["url"].startswith("https://www.googleapis.com/youtube/v3/videos?")
    assert "id=abcdef12345" in seen["url"] and "key=test-key" in seen["url"]
    assert analysis.summonerSpells == ["SummonerTeleport", "SummonerFlash"]


def test_description_fetch_failure_returns_unanalyzed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_urlopen(request, timeout=0):
        raise OSError("blocked")

    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(video_analysis, "urlopen", failing_urlopen)

    analysis = video_analysis.fetch_and_analyze_youtube_video(
        "https://www.youtube.com/watch?v=abcdef12345"
    )

    assert analysis.analysisStatus == "unanalyzed"


def test_cors_origins_are_configurable_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.main import get_cors_origins

    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    assert get_cors_origins() == ["http://localhost:3000", "http://127.0.0.1:3000"]

    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS", " https://wintop.example.com/ ,https://x.vercel.app,"
    )
    assert get_cors_origins() == ["https://wintop.example.com", "https://x.vercel.app"]


def test_upvote_rejects_videos_the_server_never_offered() -> None:
    fabricated = {**VIDEO_PAYLOAD, "videoUrl": "https://www.youtube.com/watch?v=neveroffered"}

    response = post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-abuse-12345", "video": fabricated},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_upvote"
    assert get("/api/v1/matchups/Aatrox/Darius").json()["items"] == []


def test_video_payload_rejects_non_youtube_links_and_oversized_fields() -> None:
    cases = {
        "foreign channel link": {**VIDEO_PAYLOAD, "channelUrl": "https://evil.example.com/x"},
        "foreign source link": {**VIDEO_PAYLOAD, "sourceUrl": "https://evil.example.com/x"},
        "junk video id": {**VIDEO_PAYLOAD, "videoUrl": "https://www.youtube.com/watch?v=../../etc"},
        "oversized title": {**VIDEO_PAYLOAD, "title": "Aatrox Top vs Darius " + "A" * 5000},
        "too many timestamps": {
            **VIDEO_PAYLOAD,
            "metadata": {
                "analysisStatus": "auto_parsed",
                "timestamps": [
                    {"timeSeconds": 1, "timeLabel": "0:01", "label": "x"}
                ]
                * 301,
            },
        },
    }

    for name, video in cases.items():
        response = post(
            "/api/v1/matchups/Aatrox/Darius/analyze", {"video": video}
        )
        assert response.status_code == 422, name


def test_rate_limit_blocks_bursts_and_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.rate_limit import limiter

    limiter.reset()
    monkeypatch.setenv("RATE_LIMIT_MULTIPLIER", "1")
    video = {**VIDEO_PAYLOAD}
    statuses = [
        post("/api/v1/matchups/Aatrox/Darius/analyze", {"video": video}).status_code
        for _ in range(12)
    ]

    assert statuses[:10] == [200] * 10
    assert statuses[10:] == [429, 429]

    monkeypatch.setenv("RATE_LIMIT_MULTIPLIER", "0")
    assert (
        post("/api/v1/matchups/Aatrox/Darius/analyze", {"video": video}).status_code
        == 200
    )
    limiter.reset()


def test_oversized_request_body_is_rejected_with_413() -> None:
    huge = {**VIDEO_PAYLOAD, "title": "Aatrox Top vs Darius " + "A" * 100_000}

    response = post("/api/v1/matchups/Aatrox/Darius/analyze", {"video": huge})

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "payload_too_large"


def test_client_supplied_id_cannot_target_another_saved_video(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = {**VIDEO_PAYLOAD, "videoUrl": "https://www.youtube.com/watch?v=realvideo001"}
    _offer_as_candidates(monkeypatch, real)
    saved = post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-real-12345", "video": real},
    ).json()

    spoofed = {
        **real,
        "id": saved["id"],
        "videoUrl": "https://www.youtube.com/watch?v=neveroffer1",
    }
    response = post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-spoof-12345", "video": spoofed},
    )

    assert response.status_code == 400
    items = get("/api/v1/matchups/Aatrox/Darius").json()["items"]
    assert [item["upvoteCount"] for item in items] == [1]


def _fake_data_api(monkeypatch: pytest.MonkeyPatch, search_items: list[dict], durations: dict[str, str]):
    """Stub the two YouTube Data API endpoints and record the requested URLs."""
    urls: list[str] = []

    def fake_fetch(url: str, timeout: float = 8.0) -> str:
        urls.append(url)
        if "/youtube/v3/search?" in url:
            return json.dumps({"items": search_items})
        if "/youtube/v3/videos?" in url:
            return json.dumps(
                {
                    "items": [
                        {"id": vid, "contentDetails": {"duration": iso}}
                        for vid, iso in durations.items()
                    ]
                }
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(youtube_search, "_fetch_text", fake_fetch)
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    return urls


def _search_item(video_id: str, title: str) -> dict:
    return {
        "id": {"videoId": video_id},
        "snippet": {
            "title": title,
            "channelId": "UCexample123",
            "channelTitle": "Example Replays",
            "publishedAt": "2026-11-01T00:00:00Z",
        },
    }


def test_data_api_titles_are_html_unescaped_before_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = _fake_data_api(
        monkeypatch,
        [_search_item("chogath0001", "Cho&#39;Gath Top vs Gwen - KR Master Patch 26.16")],
        {"chogath0001": "PT26M5S"},
    )

    results = youtube_search.search_youtube_matchup_candidates("Chogath", "Gwen")

    assert [r["title"] for r in results] == [
        "Cho'Gath Top vs Gwen - KR Master Patch 26.16"
    ]
    assert results[0]["gamePatch"] == "26.16"
    assert any("/youtube/v3/search?" in u for u in urls)


def test_data_api_does_not_limit_search_to_medium_length_videos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = _fake_data_api(
        monkeypatch,
        [_search_item("longreplay1", "Aatrox Top vs Darius - KR Master Patch 26.21")],
        {"longreplay1": "PT34M12S"},
    )

    results = youtube_search.search_youtube_matchup_candidates("Aatrox", "Darius")

    search_url = next(u for u in urls if "/youtube/v3/search?" in u)
    assert "videoDuration" not in search_url
    assert len(results) == 1


def test_data_api_drops_videos_shorter_than_ten_minutes_or_of_unknown_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_data_api(
        monkeypatch,
        [
            _search_item("shortclip01", "Aatrox Top vs Darius - 3 minute highlight"),
            _search_item("longreplay1", "Aatrox Top vs Darius - KR Master Patch 26.21"),
            _search_item("unknownlen1", "Aatrox Top vs Darius - KR Master Patch 26.20"),
        ],
        {"shortclip01": "PT3M10S", "longreplay1": "PT26M1S"},
    )

    results = youtube_search.search_youtube_matchup_candidates("Aatrox", "Darius")

    assert [r["videoUrl"][-11:] for r in results] == ["longreplay1"]


def test_parse_iso8601_duration() -> None:
    parse = youtube_search.parse_iso8601_duration
    assert parse("PT26M5S") == 26 * 60 + 5
    assert parse("PT1H2M3S") == 3723
    assert parse("PT45S") == 45
    assert parse("P0D") == 0
    assert parse("garbage") is None
    assert parse(None) is None


def test_empty_search_results_are_cached_only_briefly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake_uncached(player_id, opponent_id, max_results):
        calls["n"] += 1
        return ()

    clock = {"t": 1000.0}
    monkeypatch.setattr(youtube_search, "_search_uncached", fake_uncached)
    monkeypatch.setattr(youtube_search.time, "monotonic", lambda: clock["t"])

    youtube_search._cached_youtube_search("Aatrox", "Darius", 5)
    youtube_search._cached_youtube_search("Aatrox", "Darius", 5)
    assert calls["n"] == 1, "an empty result is still reused within the short window"

    clock["t"] += youtube_search.EMPTY_RESULT_TTL_SECONDS + 1
    youtube_search._cached_youtube_search("Aatrox", "Darius", 5)
    assert calls["n"] == 2, "an empty result must expire far sooner than 6 hours"
    assert youtube_search.EMPTY_RESULT_TTL_SECONDS < 600


def test_data_api_failure_is_logged_with_the_reason(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing_fetch(url: str, timeout: float = 8.0) -> str:
        raise OSError("HTTP Error 403: quotaExceeded")

    monkeypatch.setattr(youtube_search, "_fetch_text", failing_fetch)
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")

    with caplog.at_level("WARNING"):
        results = youtube_search.search_youtube_matchup_candidates("Aatrox", "Darius")

    assert results == []
    assert "test-key" not in caplog.text, "the API key must never be written to logs"
    assert "Aatrox" in caplog.text and "quotaExceeded" in caplog.text


# --- retention (YouTube API Services Developer Policies III.E.4: at most 30 days) ---

from datetime import datetime, timedelta, timezone  # noqa: E402

from app import retention  # noqa: E402
from app.database import (  # noqa: E402
    MatchupVideoMetadataRecord,
    MatchupVideoRecord,
    MatchupVideoVoteRecord,
)
from sqlalchemy.orm import Session  # noqa: E402


def _iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def _add_saved_video(video_id: str, fetched_days_ago: float, votes: int = 1) -> str:
    """Insert a saved video with a vote and an auto-extracted build, as the app would."""
    record_id = f"yt-aatrox-vs-darius-{video_id}"
    engine = database.get_engine()
    matchups.ensure_database_seeded(engine, ())
    with Session(engine) as session:
        session.add(
            MatchupVideoRecord(
                id=record_id,
                player_champion_id="Aatrox",
                opponent_champion_id="Darius",
                title="Aatrox Top vs Darius - KR Master Patch 26.21",
                video_url=f"https://www.youtube.com/watch?v={video_id}",
                channel_name="c",
                channel_url="https://www.youtube.com/@c",
                verified_at=_iso_days_ago(fetched_days_ago),
                verification_status="verified",
                embed_status="unknown",
                source_url="https://www.youtube.com/results",
                upvote_count=votes,
                fetched_at=_iso_days_ago(fetched_days_ago),
            )
        )
        for n in range(votes):
            session.add(MatchupVideoVoteRecord(video_record_id=record_id, voter_hash=f"h{n}{video_id}"))
        session.add(
            MatchupVideoMetadataRecord(
                video_record_id=record_id,
                analysis_status="auto_parsed",
                summoner_spells_json='["SummonerFlash"]',
                updated_at=_iso_days_ago(fetched_days_ago),
            )
        )
        session.commit()
    return record_id


def _counts() -> tuple[int, int, int]:
    with Session(database.get_engine()) as session:
        return (
            session.query(MatchupVideoRecord).count(),
            session.query(MatchupVideoVoteRecord).count(),
            session.query(MatchupVideoMetadataRecord).count(),
        )


def test_retention_defaults_to_28_days_and_never_exceeds_the_30_day_policy_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("YOUTUBE_DATA_RETENTION_DAYS", raising=False)
    assert retention.retention_days() == 28

    monkeypatch.setenv("YOUTUBE_DATA_RETENTION_DAYS", "14")
    assert retention.retention_days() == 14

    monkeypatch.setenv("YOUTUBE_DATA_RETENTION_DAYS", "365")
    assert retention.retention_days() == 30, "a larger value must be capped at the policy limit"

    monkeypatch.setenv("YOUTUBE_DATA_RETENTION_DAYS", "0")
    assert retention.retention_days() == 1
    monkeypatch.setenv("YOUTUBE_DATA_RETENTION_DAYS", "not-a-number")
    assert retention.retention_days() == 28


def test_purge_deletes_only_expired_rows_together_with_votes_and_builds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("YOUTUBE_DATA_RETENTION_DAYS", raising=False)
    _add_saved_video("freshvideo1", fetched_days_ago=1, votes=2)
    _add_saved_video("edgefresh01", fetched_days_ago=27, votes=1)
    _add_saved_video("edgestale01", fetched_days_ago=29, votes=3)
    _add_saved_video("oldvideo001", fetched_days_ago=90, votes=1)
    assert _counts() == (4, 7, 4)

    removed = retention.purge_expired()

    assert removed == {"videos": 2, "votes": 4, "metadata": 2}
    assert _counts() == (2, 3, 2)
    with Session(database.get_engine()) as session:
        left = sorted(r.id[-11:] for r in session.query(MatchupVideoRecord))
    assert left == ["edgefresh01", "freshvideo1"]


def test_purge_removes_rows_with_an_unreadable_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_DATA_RETENTION_DAYS", raising=False)
    record_id = _add_saved_video("brokendate1", fetched_days_ago=1)
    with Session(database.get_engine()) as session:
        session.get(MatchupVideoRecord, record_id).fetched_at = "not a date"
        session.commit()

    retention.purge_expired()

    assert _counts() == (0, 0, 0), "an unknown age must be treated as expired"


def test_purge_handles_dates_written_with_different_utc_offsets() -> None:
    record_id = _add_saved_video("offsetvideo", fetched_days_ago=1)
    stale_jst = (
        (datetime.now(timezone.utc) - timedelta(days=29)).astimezone(timezone(timedelta(hours=9)))
    ).isoformat(timespec="seconds")
    with Session(database.get_engine()) as session:
        session.get(MatchupVideoRecord, record_id).fetched_at = stale_jst
        session.commit()

    retention.purge_expired()

    assert _counts()[0] == 0


def test_expired_rows_are_not_served_even_before_the_purge_runs() -> None:
    _add_saved_video("servedfresh", fetched_days_ago=2)
    _add_saved_video("servedstale", fetched_days_ago=40)

    response = get("/api/v1/matchups/Aatrox/Darius")

    urls = [item["videoUrl"][-11:] for item in response.json()["items"]]
    assert urls == ["servedfresh"], "a row past the limit must be hidden at read time"


def test_new_rows_record_when_the_data_was_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    video = {**VIDEO_PAYLOAD, "videoUrl": "https://www.youtube.com/watch?v=stampedvid1"}
    _offer_as_candidates(monkeypatch, video)

    post(
        "/api/v1/matchups/Aatrox/Darius/upvote",
        {"voterToken": "voter-stamp-12345", "video": video},
    )

    with Session(database.get_engine()) as session:
        stamped = session.query(MatchupVideoRecord).one().fetched_at
    age = datetime.now(timezone.utc) - datetime.fromisoformat(stamped)
    assert abs(age) < timedelta(minutes=1)
