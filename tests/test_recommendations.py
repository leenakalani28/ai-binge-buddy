import pytest
from src.preference_models import Candidate, Preference
from src.recommendation_engine import eligible, rank, runtime_match
from src.groq_client import validate_response

def movie(identifier=1, **kwargs):
    return Candidate(id=identifier, media_type="movie", title="Test", **kwargs)

def test_region_subscription_is_hard_and_rent_is_not_streaming():
    user = Preference(name="Alex", providers=[8])
    assert not eligible(movie(providers={"rent": [{"provider_id": 8}]}), [user])
    assert eligible(movie(providers={"flatrate": [{"provider_id": 8}]}), [user])
    assert not eligible(movie(), [user])

def test_shared_subscription_and_content_conflict():
    users = [Preference(name="A", providers=[8]), Preference(name="B", providers=[9])]
    assert eligible(movie(providers={"flatrate": [{"provider_id": 9}]}), users)
    users[1].content = ["TV Series"]
    assert not eligible(movie(), users)

def test_documentary_category():
    assert eligible(movie(genres=["Documentary"]), [Preference(name="A", content=["Documentaries"])])
    assert not eligible(movie(), [Preference(name="A", content=["Documentaries"])])

@pytest.mark.parametrize("count", [1, 6])
def test_any_defaults_and_exclusion(count):
    users = [Preference(name=f"User {i}") for i in range(count)]
    rows = rank([movie(1), movie(2)], users, {"movie:1"})
    assert len(rows) == 1
    assert rows[0]["score"] == 100
    assert rows[0]["candidate"].id == 2

def test_runtime_unknown_and_unlimited():
    assert runtime_match(None, "No Maximum Limit") == 1
    assert runtime_match(None, "Under 90") == 0
    assert runtime_match(100, "90–120") == 1
    assert runtime_match(170, "Over 150") == 1

def test_fairness_penalizes_severe_mismatch():
    users = [Preference(name="A", genres=["Comedy"], languages=["en"]), Preference(name="B", genres=["Drama"], languages=["hi"])]
    rows = rank([movie(1, genres=["Comedy"], language="en"), movie(2, genres=["Comedy", "Drama"], language="hi")], users)
    assert rows[0]["candidate"].id == 2
    assert rows[0]["score"] > rows[1]["score"]

def response(keys):
    return {"group_analysis": {"common_interests": [], "conflicting_preferences": [], "group_summary": "Test"},
        "recommendations": [{"tmdb_id": i, "media_type": "movie", "reason": "Matches", "user_matches": {}, "compromise_note": ""} for i in keys], "roast": ""}

def test_groq_rejects_invented_duplicate_or_missing_candidates():
    shortlist = rank([movie(i) for i in range(1, 4)], [Preference(name="A")])
    assert len(validate_response(response([1, 2, 3]), shortlist, 3).recommendations) == 3
    for keys in ([1, 1, 2], [1, 2, 999], [1, 2]):
        with pytest.raises(ValueError):
            validate_response(response(keys), shortlist, 3)

def test_movie_tv_ids_remain_distinct():
    tv = Candidate(id=1, media_type="tv", title="Series")
    assert len(rank([movie(1), tv], [Preference(name="A")], {"movie:1"})) == 1

def test_tmdb_enrichment_region_and_missing_metadata(monkeypatch):
    from src import tmdb_client
    monkeypatch.setattr(tmdb_client, "request", lambda *a, **k: {"id": 1, "title": "Title", "watch/providers": {"results": {"GB": {"flatrate": [{"provider_id": 8, "provider_name": "Netflix"}]}, "US": {"rent": [{"provider_id": 9, "provider_name": "Rent"}]}}}})
    uk = tmdb_client.enrich("movie", 1, "GB")
    us = tmdb_client.enrich("movie", 1, "US")
    assert uk.poster is None and uk.runtime is None
    assert eligible(uk, [Preference(name="A", providers=[8])])
    assert not eligible(us, [Preference(name="A", providers=[8])])

def test_groq_failure_and_celebration_fallback(monkeypatch):
    from src import groq_client
    monkeypatch.setattr(groq_client, "GROQ_KEY", "")
    assert groq_client.celebrate("Title") == "Popcorn ready. Debate officially adjourned."
    with pytest.raises(ValueError):
        groq_client.recommend(rank([movie()], [Preference(name="A")]), [Preference(name="A")], False)

def test_wheel_stopping_position_for_every_outcome():
    import math
    tau = 2 * math.pi
    for chosen in range(3):
        for start in (0, .5, 3, 20):
            target = -math.pi / 2 - (chosen + .5) * tau / 3
            delta = 6 * tau + (target - start) % tau
            angle = (start + delta) % tau
            actual = math.floor(((-math.pi / 2 - angle) % tau) / (tau / 3))
            assert actual == chosen
    # Rejection sampling removes the one excess value before modulo three.
    assert (2**32 - 1) % 3 == 0

def test_discovery_limits_detail_work_and_expands_for_access(monkeypatch):
    from src import tmdb_client
    loaded = []
    monkeypatch.setattr(tmdb_client, "request", lambda path, **kw: {"results": [{"id": kw["page"] * 100 + i} for i in range(40)]})
    def enrich(media, identifier, region):
        loaded.append(identifier)
        return Candidate(id=identifier, media_type=media, title="Test")
    monkeypatch.setattr(tmdb_client, "enrich", enrich)
    user = Preference(name="A", content=["Movies"])
    result = tmdb_client.discover([user], "GB", {"movie": [], "tv": []}, set())
    assert len(result) == len(loaded) == 48
    loaded.clear()
    user.providers = [8]
    tmdb_client.discover([user], "GB", {"movie": [], "tv": []}, set())
    assert len(loaded) == 80

def test_catalog_parallel_loading_and_complete_cache(monkeypatch):
    from threading import Barrier
    from src import tmdb_client
    barrier = Barrier(5)
    calls = []
    def mock_request(path, **params):
        calls.append((path, params))
        barrier.wait(timeout=5)
        if path.startswith("genre/"):
            return {"genres": [{"id": 35, "name": "Comedy"}]}
        if path == "configuration/languages":
            return [{"iso_639_1": "en", "english_name": "English"}]
        return {"results": [{"provider_id": 8, "provider_name": "Netflix"}]}
    tmdb_client.catalog.clear()
    monkeypatch.setattr(tmdb_client, "request", mock_request)
    try:
        first = tmdb_client.catalog("GB")
        second = tmdb_client.catalog("GB")
        assert first == second
        assert len(calls) == 5
        assert first[2] == {8: "Netflix"}
        assert all(params["watch_region"] == "GB" for path, params in calls if path.startswith("watch/"))
    finally:
        tmdb_client.catalog.clear()

def test_llm_receives_every_eligible_candidate_without_scores(monkeypatch):
    from src import groq_client
    captured = {}
    def chat(system, payload, temperature=.2):
        captured.update(payload)
        data = response([48, 30, 1])
        for pick in data["recommendations"]:
            pick["user_matches"] = {"A": "Fits your open preferences"}
        return data
    monkeypatch.setattr(groq_client, "chat", chat)
    users = [Preference(name="A")]
    rows = [{"candidate": movie(i, overview="A supplied synopsis")} for i in range(1, 49)]
    result = groq_client.recommend(rows, users, False, "IN")
    assert len(captured["candidates"]) == 48
    assert captured["region"] == "IN"
    assert {p.tmdb_id for p in result.recommendations} == {48, 30, 1}
    assert set(captured["users"][0]) == {"name", "content", "genres", "languages", "providers"}
    assert all("group_score" not in c and "user_scores" not in c for c in captured["candidates"])
    assert captured["candidates"][0]["synopsis"] == "A supplied synopsis"

def test_llm_requires_personalised_explanation_for_all_users(monkeypatch):
    from src import groq_client
    monkeypatch.setattr(groq_client, "chat", lambda *a: response([1]))
    with pytest.raises(ValueError):
        groq_client.recommend([{"candidate": movie()}], [Preference(name="A")], False)

def test_oversized_request_uses_llm_rounds_for_all_candidates(monkeypatch):
    from src import groq_client
    rounds = []
    def chat(system, payload):
        ids = [c["tmdb_id"] for c in payload["candidates"]]
        rounds.append((ids, payload["roast_enabled"]))
        if len(ids) > 24:
            raise ValueError("Groq HTTP 413")
        data = response(ids[:3])
        for pick in data["recommendations"]:
            pick["user_matches"] = {"A": "Matches"}
        return data
    monkeypatch.setattr(groq_client, "chat", chat)
    result = groq_client.recommend([{"candidate": movie(i)} for i in range(1, 49)], [Preference(name="A")], True)
    assert len(result.recommendations) == 3
    assert set(rounds[1][0] + rounds[2][0]) == set(range(1, 49))
    assert not rounds[1][1] and not rounds[2][1]
    assert rounds[-1][1] and len(rounds[-1][0]) == 6
