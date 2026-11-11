from conftest import api_get as get


def test_champion_list_includes_version_and_catalog() -> None:
    response = get("/api/v1/champions")

    assert response.status_code == 200
    body = response.json()
    assert body["dataDragonVersion"]
    assert body["items"]
    assert body["items"][0]["id"] == "Aatrox"


def test_champion_search_matches_japanese_and_english_names() -> None:
    japanese = get("/api/v1/champions?q=エイトロ")
    english = get("/api/v1/champions?q=aatrox")

    assert [item["id"] for item in japanese.json()["items"]] == ["Aatrox"]
    assert [item["id"] for item in english.json()["items"]] == ["Aatrox"]


def test_champion_search_matches_romanized_japanese_name() -> None:
    cases = {
        "eitorokkusu": "Aatrox",
        "orerionsoru": "AurelionSol",
        "boribea": "Volibear",
        "kami-ru": "Camille",
        "keitorin": "Caitlyn",
    }

    for query, expected_id in cases.items():
        response = get(f"/api/v1/champions?q={query}")
        assert response.status_code == 200
        assert expected_id in {item["id"] for item in response.json()["items"]}


def test_short_b_search_matches_japanese_b_and_v_names() -> None:
    response = get("/api/v1/champions?q=be")
    result_ids = {item["id"] for item in response.json()["items"]}

    assert {"Belveth", "Velkoz", "Veigar"}.issubset(result_ids)


def test_champion_search_returns_empty_list_when_no_match() -> None:
    response = get("/api/v1/champions?q=not-a-champion")

    assert response.status_code == 200
    assert response.json()["items"] == []
