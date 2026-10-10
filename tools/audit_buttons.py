"""Offline button audit. API responses are mocked; app code is not changed."""
import hashlib
import json
from pathlib import Path
from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest
from src import config, groq_client, tmdb_client, wheel_component
from src.preference_models import Candidate, Preference

ROOT = Path(__file__).resolve().parents[1]
users = [Preference(name="Alex"), Preference(name="Priya")]
candidates = [Candidate(id=i, media_type="movie", title=f"Audit title {i}",
    watch_link=f"https://www.themoviedb.org/movie/{i}/watch",
    trailer="https://www.youtube.com/watch?v=audit") for i in range(1, 10)]
rows = [{"candidate": c, "reason": "Fits", "user_matches": {}} for c in candidates[:3]]
signature = hashlib.sha256(json.dumps({"users": [u.model_dump() for u in users], "region": "GB"}, sort_keys=True).encode()).hexdigest()
results = []
link_results = {}

def recommend(pool, people, *args):
    return groq_client.Response.model_validate({
        "group_analysis": {"common_interests": [], "conflicting_preferences": [], "group_summary": "Audit selection"},
        "recommendations": [{"tmdb_id": r["candidate"].id, "media_type": "movie", "reason": "Fits", "user_matches": {u.name: "Fits" for u in people}, "compromise_note": ""} for r in pool[:3]], "roast": ""})

catalog = lambda region: ({"movie": [{"id": 35, "name": "Comedy"}], "tv": []}, [{"iso_639_1": "en", "english_name": "English"}], {8: "Netflix"})

def run_case(name, stage, expected, label=None, key=None, mode=None, index=0):
    with MonkeyPatch.context() as mp:
        mp.setattr(config, "TMDB_KEY", "audit")
        mp.setattr(config, "TMDB_TOKEN", "")
        mp.setattr(tmdb_client, "catalog", catalog)
        mp.setattr(tmdb_client, "discover", lambda *a: candidates)
        mp.setattr(groq_client, "recommend", recommend)
        mp.setattr(groq_client, "celebrate", lambda *a: "Enjoy your pick!")
        mp.setattr(wheel_component, "wheel", lambda *a: {"batch_id": 1, "index": 1, "event": "audit-spin"} if mode in {"wheel", "wheel-lock"} else None)
        if mode == "missing-key":
            mp.setattr(config, "TMDB_KEY", "")
        if mode == "catalog-error":
            def unavailable(*a):
                raise tmdb_client.TMDBError("Audit catalog unavailable")
            mp.setattr(tmdb_client, "catalog", unavailable)
        app = AppTest.from_file(ROOT / "app.py", default_timeout=20)
        seed = {"stage": stage, "users": users.copy(), "region": "GB", "pool": candidates,
            "batch": rows.copy(), "seen": {c.key for c in candidates[:3]}, "signature": signature,
            "request_number": 1, "winner": rows[0], "celebration": "Enjoy!",
            "saved_roast_enabled": True, "wheel_result": None, "wheel_event": None}
        if mode == "ai-error":
            seed.update(notice="AI selection failed: audit", batch=[])
        for k, v in seed.items():
            app.session_state[k] = v
        try:
            app.run()
            assert not app.exception
            if stage in {"reveal", "winner"} and not mode:
                for element in app.get("link_button"):
                    label_text, url = element.proto.label, element.proto.url
                    if "TMDB" in label_text:
                        assert url in {f"https://www.themoviedb.org/movie/{i}" for i in range(1, 4)}
                    elif "trailer" in label_text.lower():
                        assert url == "https://www.youtube.com/watch?v=audit"
                    else:
                        assert url in {f"https://www.themoviedb.org/movie/{i}/watch" for i in range(1, 4)}
                    link_results[(stage, label_text)] = {"screen": stage, "button": label_text, "result": "PASS: configured URL", "scope": "External page not opened; fixture URLs"}
            if mode == "catalog-error":
                mp.setattr(tmdb_client, "catalog", catalog)
            if mode == "invalid-name":
                app.text_input[0].set_value("")
            if key:
                app.button(key=key).click().run()
            elif label:
                [b for b in app.button if b.label == label][index].click().run()
            assert not app.exception, str(app.exception)
            assert app.session_state["stage"] == expected
            if mode == "invalid-name":
                assert app.error
            if mode == "wheel":
                assert app.session_state["wheel_result"] == 1
                assert any("destiny-selection" in m.value for m in app.markdown)
            if mode == "wheel-lock":
                assert app.session_state["winner"]["candidate"].id == 2
            if key and key.startswith("lock_"):
                assert app.session_state["winner"]["candidate"].key == key[5:]
            if key == "group_plus":
                assert app.session_state["group_size"] == 3
            if key == "group_minus":
                assert app.session_state["group_size"] == 1
            if expected == "welcome" and stage in {"winner", "reveal"}:
                assert app.session_state["winner"] is None
                assert not app.session_state["users"]
            if expected == "reveal" and label != "Back to shortlist" and mode != "wheel":
                assert len(app.session_state["batch"]) == 3
            scroll_script = any("scrollTo({top: 0" in str(e.proto) for e in app.get("iframe"))
            results.append({"button": name, "result": "PASS", "destination": expected, "top_script_rendered": scroll_script})
        except Exception as exc:
            results.append({"button": name, "result": "FAIL", "destination": expected, "reason": str(exc)})

cases = [
    ("Home: Let's Find Something to Watch", "welcome", "group", None, "home_cta"),
    ("Group: +", "group", "group", None, "group_plus"),
    ("Group: minus", "group", "group", None, "group_minus"),
    ("Group: Back", "group", "welcome", None, "group_back"),
    ("Group: Continue", "group", "preferences", None, "group_continue"),
    ("Group: Continue with empty name", "group", "group", None, "group_continue", "invalid-name"),
    ("Preferences: Back", "preferences", "group", "Back"),
    ("Preferences: Find Our Top 3", "preferences", "reveal", "✨ Find Our Top 3 Recommendations"),
    ("Missing credentials: Back to group", "preferences", "group", "Back to group", None, "missing-key"),
    ("Catalog error: Retry", "preferences", "preferences", "Retry loading preferences", None, "catalog-error"),
    ("Catalog error: Back to group", "preferences", "group", "Back to group", None, "catalog-error"),
    ("AI error: Retry AI selection", "reveal", "reveal", "Retry AI selection", None, "ai-error"),
    ("AI error: Edit Preferences", "reveal", "preferences", "Edit Preferences", None, "ai-error"),
    *[(f"Shortlist: Lock card {i}", "reveal", "winner", None, f"lock_movie:{i}") for i in range(1, 4)],
    ("Shortlist: Show Us 3 More", "reveal", "reveal", "🔄 Show Us 3 More"),
    ("Shortlist: Edit Preferences", "reveal", "preferences", "Edit Preferences"),
    ("Shortlist: Start over", "reveal", "welcome", None, "reveal_restart"),
    ("Wheel: result received", "reveal", "reveal", None, None, "wheel"),
    ("Wheel: Lock choice", "reveal", "winner", "🏆 Lock in the wheel’s choice", None, "wheel-lock"),
    ("Winner: Back to shortlist", "winner", "reveal", "Back to shortlist"),
    ("Winner: Find Something Else", "winner", "reveal", "Find Something Else"),
    ("Winner: Start over", "winner", "welcome", None, "winner_restart"),
    ("Winner sidebar: Start Over", "winner", "welcome", "Start Over"),
]
for case in cases:
    run_case(*case)
out = ROOT / "button-audit-results.json"
out.write_text(json.dumps({"scope": "Offline AppTest with mocked TMDB/Groq; viewport positions not measured", "cases": results, "external_links": list(link_results.values())}, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
raise SystemExit(any(r["result"] == "FAIL" for r in results))
