import pytest
from src.preference_models import Preference, validate_group

def test_empty_duplicate_and_group_limits():
    with pytest.raises(ValueError):
        Preference(name="  ")
    for group in ([], [Preference(name="Alex"), Preference(name=" alex ")], [Preference(name=str(i)) for i in range(7)]):
        with pytest.raises(ValueError):
            validate_group(group)
    validate_group([Preference(name=str(i)) for i in range(6)])

def test_group_stepper_preserves_names_and_limits():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file("../app.py", default_timeout=15).run()
    next(b for b in app.button if "Let’s Find" in b.label).click().run()
    next(w for w in app.text_input if w.label == "Person 2").set_value("Priya").run()
    app.button(key="group_minus").click().run()
    assert app.session_state["group_size"] == 1
    assert app.button(key="group_minus").disabled
    app.button(key="group_plus").click().run()
    assert next(w for w in app.text_input if w.label == "Person 2").value == "Priya"
    for _ in range(4):
        app.button(key="group_plus").click().run()
    assert len(app.text_input) == 6
    assert app.button(key="group_plus").disabled
    assert not app.exception

def test_welcome_group_navigation_and_state(monkeypatch):
    from src import config
    monkeypatch.setattr(config, "TMDB_KEY", "")
    monkeypatch.setattr(config, "TMDB_TOKEN", "")
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file("../app.py", default_timeout=10).run()
    assert not app.exception
    next(b for b in app.button if "Let’s Find" in b.label).click().run()
    assert app.session_state["stage"] == "group"
    next(w for w in app.text_input if w.label == "Person 1").set_value("Alex")
    next(w for w in app.text_input if w.label == "Person 2").set_value("Priya")
    next(b for b in app.button if b.label == "Continue \u2192").click().run()
    assert app.session_state["stage"] == "preferences"
    assert [u.name for u in app.session_state["users"]] == ["Alex", "Priya"]
    assert not app.exception

def test_error_retry_reruns_and_more(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from src import config, tmdb_client, groq_client
    from src.preference_models import Candidate
    calls = []
    monkeypatch.setattr(config, "TMDB_KEY", "test")
    monkeypatch.setattr(tmdb_client, "catalog", lambda region: ({"movie": [{"id": 35, "name": "Comedy"}], "tv": []}, [{"iso_639_1": "en", "english_name": "English"}], {8: "Netflix"}))
    monkeypatch.setattr(tmdb_client, "discover", lambda *a: [Candidate(id=i, media_type="movie", title=f"Mock {i}", language="en") for i in range(1, 7)])
    def fail(*args):
        calls.append(1)
        raise ValueError("Unavailable")
    monkeypatch.setattr(groq_client, "recommend", fail)
    monkeypatch.setattr(groq_client, "celebrate", lambda *a: "Enjoy!")
    app = AppTest.from_file("../app.py", default_timeout=40).run()
    def click(label):
        next(b for b in app.button if b.label == label).click().run()
        assert not app.exception
    click("🍿 Let’s Find Something to Watch!")
    click("Continue \u2192")
    assert len(app.multiselect) == 8
    assert not app.slider
    assert not any("runtime" in w.label.lower() or "mood" in w.label.lower() for w in app.selectbox)
    click("✨ Find Our Top 3 Recommendations")
    assert app.session_state["batch"] == []
    assert not app.session_state["seen"]
    assert app.error
    app.run()
    assert len(calls) == 1
    def recover(rows, users, roast, region):
        calls.append(1)
        return groq_client.Response.model_validate({
            "group_analysis": {"common_interests": [], "conflicting_preferences": [], "group_summary": "Selected"},
            "recommendations": [{"tmdb_id": row["candidate"].id, "media_type": "movie", "reason": "Fits", "user_matches": {u.name: "Open preferences" for u in users}, "compromise_note": ""} for row in rows[:3]], "roast": ""})
    monkeypatch.setattr(groq_client, "recommend", recover)
    click("Retry AI selection")
    assert len(app.session_state["batch"]) == 3
    first = {r["candidate"].key for r in app.session_state["batch"]}
    app.run()
    assert len(calls) == 2
    click("🔄 Show Us 3 More")
    second = {r["candidate"].key for r in app.session_state["batch"]}
    assert not first & second
    assert len(calls) == 3
    click("🏆 Lock This In!")
    assert app.session_state["stage"] == "winner"
    app.button(key="winner_restart").click().run()
    assert not app.exception
    assert app.session_state["stage"] == "welcome"
    assert app.session_state["winner"] is None
    assert not app.session_state["users"]
    assert not app.session_state["seen"]
    assert not any("Tonight’s watch is locked in" in m.value for m in app.markdown)
    # Restore the successful batch to exercise backward navigation independently.
    app.session_state["stage"] = "reveal"
    app.session_state["batch"] = [{"candidate": Candidate(id=int(k.split(":")[1]), media_type="movie", title="Test"), "reason": "Fits", "user_matches": {}} for k in second]
    app.session_state["users"] = [Preference(name="User 1"), Preference(name="User 2")]
    app.session_state["winner"] = app.session_state["batch"][0]
    app.session_state["stage"] = "winner"
    app.session_state["celebration"] = "Enjoy!"
    app.run()
    click("Back to shortlist")
    assert {r["candidate"].key for r in app.session_state["batch"]} == second
    click("Edit Preferences")
    assert len(app.session_state["users"]) == 2

def test_llm_selected_order_is_used_without_python_ranking(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from src import config, tmdb_client, groq_client, recommendation_engine
    from src.preference_models import Candidate
    monkeypatch.setattr(config, "TMDB_KEY", "test")
    monkeypatch.setattr(tmdb_client, "catalog", lambda region: ({"movie": [], "tv": []}, [], {}))
    monkeypatch.setattr(tmdb_client, "discover", lambda *a: [Candidate(id=i, media_type="movie", title=f"Mock {i}") for i in range(1, 49)])
    def no_rank(*a, **k):
        raise AssertionError("Python ranking must not run on successful AI selection")
    monkeypatch.setattr(recommendation_engine, "rank", no_rank)
    def choose(rows, users, roast, region):
        assert len(rows) == 48
        assert all(set(row) == {"candidate"} for row in rows)
        return groq_client.Response.model_validate({
            "group_analysis": {"common_interests": [], "conflicting_preferences": [], "group_summary": "AI selected these"},
            "recommendations": [{"tmdb_id": i, "media_type": "movie", "reason": "Good compromise", "user_matches": {u.name: "Open preferences" for u in users}, "compromise_note": ""} for i in (48, 25, 2)], "roast": ""})
    monkeypatch.setattr(groq_client, "recommend", choose)
    app = AppTest.from_file("../app.py", default_timeout=15).run()
    for label in ("🍿 Let’s Find Something to Watch!", "Continue \u2192", "✨ Find Our Top 3 Recommendations"):
        next(b for b in app.button if b.label == label).click().run()
        assert not app.exception
    assert [r["candidate"].id for r in app.session_state["batch"]] == [48, 25, 2]
    assert not app.get("progress")
    assert all("score" not in row for row in app.session_state["batch"])
