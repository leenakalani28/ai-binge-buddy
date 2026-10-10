import hashlib
import json
from html import escape
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from src import config, groq_client, tmdb_client
from src.preference_models import Preference, CONTENT, validate_group
from src.recommendation_engine import eligible
from src.session_manager import initialize, reset, goto
from src.ui_components import card, commentary, wheel_selection
from src.wheel_component import wheel

st.set_page_config(page_title="AI Binge Buddy", page_icon="🍿", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'assets/styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
initialize()
s = st.session_state

def generate():
    validate_group(s.users)
    signature = hashlib.sha256(json.dumps({"users": [u.model_dump() for u in s.users], "region": s.region}, sort_keys=True).encode()).hexdigest()
    if signature != s.signature:
        s.pool, s.seen, s.discovery_page = [], set(), 1
        s.signature = signature
    with st.status("Negotiating with your collective taste buds…", expanded=True) as status:
        ranked = [{"candidate": c} for c in s.pool if c.key not in s.seen and eligible(c, s.users)]
        if len(ranked) < 3:
            st.write("Checking real titles and regional subscription availability…")
            fetched = tmdb_client.discover(s.users, s.region, s.genres_catalog, s.seen, s.discovery_page)
            s.discovery_page += 2
            pool = {c.key: c for c in s.pool + fetched}
            s.pool = list(pool.values())
            ranked = [{"candidate": c} for c in s.pool if c.key not in s.seen and eligible(c, s.users)]
        s.batch = []
        s.roast, s.analysis, s.notice = "", None, ""
        if ranked:
            st.write("Asking AI to save your friendships…")
            try:
                response = groq_client.recommend(ranked, s.users, s.saved_roast_enabled, s.region)
                lookup = {row["candidate"].key: row for row in ranked}
                selected = []
                for pick in response.recommendations:
                    row = lookup[f"{pick.media_type}:{pick.tmdb_id}"].copy()
                    # Names are validated against the submitted group as well.
                    if not set(pick.user_matches) <= {u.name for u in s.users}:
                        raise ValueError("Unknown name in AI response")
                    row.update(reason=pick.reason, ai=True, user_matches=pick.user_matches, compromise_note=pick.compromise_note)
                    selected.append(row)
                s.batch = selected
                s.analysis = response.group_analysis.model_dump()
                s.roast = response.roast if s.saved_roast_enabled else ""
            except ValueError as exc:
                s.notice = "AI selection could not be completed. No recommendations were selected."
                from pydantic import ValidationError
                s.notice += " Reason: " + ("AI response did not match the required structure." if isinstance(exc, ValidationError) else str(exc)[:160])
        s.seen.update(row["candidate"].key for row in s.batch)
        s.request_number += 1
        s.wheel_result, s.wheel_event = None, None
        status.update(label="AI selection failed." if s.notice else "Your shortlist is ready.", state="error" if s.notice else "complete", expanded=False)
    goto("reveal")

def lock(row, from_wheel=False):
    s.winner = row
    s.celebrate_pending = True
    with st.spinner("Rolling the end credits on this debate…"):
        s.celebration = groq_client.celebrate(row["candidate"].title, from_wheel)
    goto("winner")

with st.sidebar:
    st.markdown("## 🍿 Binge Buddy")
    st.caption("Less scrolling. More watching. Zero arguments. (Well, almost.)")
    st.caption("YOUR MOVIE NIGHT")
    st.write({"welcome": "Welcome", "group": "1 · Your group", "preferences": "2 · Your preferences", "reveal": "3 · Your shortlist", "winner": "Tonight’s winner"}[s.stage])
    if s.stage not in {"welcome", "group", "preferences", "reveal"} and st.button("Start Over", use_container_width=True):
        reset()
        st.rerun()
    if s.users:
        st.caption("Tonight's crew: " + ", ".join(u.name for u in s.users))
    st.caption("This product uses the TMDB API but is not endorsed or certified by TMDB.")
    st.markdown("Metadata: [TMDB](https://www.themoviedb.org/) · Availability: [JustWatch](https://www.justwatch.com/)")
    st.caption("Availability may change. Confirm with the provider before watching. Original language does not confirm subtitles or dubbing.")

if s.stage not in {"welcome", "group", "preferences", "reveal", "winner"}:
    _, restart_column = st.columns([3, 1])
    if restart_column.button("↺ Start Over", use_container_width=True, key="restart_main"):
        reset()
        st.rerun()

if s.stage == "welcome":
    st.markdown('<div class="hero"><div class="eyebrow">MOVIE NIGHT. PEACE RESTORED.</div><h1>AI Binge Buddy<span style="color:#f2c879">.</span></h1><p>Your friendships are too important to be destroyed by 45 minutes of scrolling.</p><p>Tell us what everyone’s in the mood for. We’ll find your next obsession, roast your questionable taste, and settle the movie-night debate.</p></div>', unsafe_allow_html=True)
    if st.button("🍿 Let’s Find Something to Watch!", type="primary", key="home_cta"):
        goto("group")

elif s.stage == "group":
    with st.container(key="group_panel"):
        st.markdown('<div class="setup-meta"><span>MOVIE NIGHT</span><span>Step 1 of 3</span></div><div class="setup-progress" aria-label="Step 1 of 3"><i></i><i></i><i></i></div>', unsafe_allow_html=True)
        st.title("Gather your gang")
        st.write("Who's joining movie night? Set up your group to get started.")
        st.divider()
        if "group_size" not in s:
            s.group_size = len(s.users) or 2
        def resize_group(delta):
            # Preserve names when their widgets disappear after removing people.
            for index in range(s.group_size):
                s[f"saved_name_{index}"] = s.get(f"name_{index}", f"User {index + 1}")
            s.group_size = max(1, min(6, s.group_size + delta))
        label, stepper = st.columns([3, 2], vertical_alignment="center")
        label.markdown("**Number of people**")
        with stepper:
            minus, value, plus = st.columns(3, vertical_alignment="center")
            minus.button("−", key="group_minus", help="Remove one person", disabled=s.group_size == 1, on_click=resize_group, args=(-1,), use_container_width=True)
            value.markdown(f'<div class="setup-count">{s.group_size}</div>', unsafe_allow_html=True)
            plus.button("+", key="group_plus", help="Add one person", disabled=s.group_size == 6, on_click=resize_group, args=(1,), use_container_width=True)
        st.subheader("Who's watching?")
        names = []
        for i in range(s.group_size):
            avatar, field = st.columns([1, 12], vertical_alignment="center")
            avatar.markdown('<div class="setup-avatar" aria-hidden="true"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8" r="3"/><path d="M6 21v-2a6 6 0 0 1 12 0v2"/></svg></div>', unsafe_allow_html=True)
            previous = s.get(f"saved_name_{i}", s.users[i].name if i < len(s.users) else f"User {i + 1}")
            name = field.text_input(f"Person {i + 1}", value=previous, key=f"name_{i}", max_chars=40, label_visibility="collapsed")
            names.append(name)
            s[f"saved_name_{i}"] = name
        regions = {"GB": "United Kingdom", "US": "United States", "IN": "India", "CA": "Canada", "AU": "Australia", "DE": "Germany", "FR": "France", "ES": "Spain", "JP": "Japan", "KR": "South Korea"}
        s.region = st.selectbox("Streaming region", list(regions), index=list(regions).index(s.region), format_func=regions.get, key="region_select")
        st.caption("ⓘ We'll use your region to find titles available to your group. Any subscription declared by the group can provide access.")
        st.divider()
        back, _, proceed = st.columns([1, 2, 1.5])
        if back.button("Back", key="group_back", use_container_width=True):
            goto("welcome")
        if proceed.button("Continue →", type="primary", key="group_continue", use_container_width=True):
            try:
                users = [Preference(**{**(s.users[i].model_dump() if i < len(s.users) else {}), "name": name}) for i, name in enumerate(names)]
                validate_group(users)
                s.users = users
                goto("preferences")
            except ValueError as exc:
                st.error(str(exc))

elif s.stage == "preferences":
    with st.container(key="preferences_panel"):
        st.markdown('<div class="setup-meta"><span>MOVIE NIGHT</span><span>Step 2 of 3</span></div><div class="setup-progress preferences-progress" aria-label="Step 2 of 3"><i></i><i></i><i></i></div>', unsafe_allow_html=True)
        st.title("Set your watch preferences")
        st.write("A little about everyone’s taste. We’ll find your next movie-night match.")
        st.divider()
        if not (config.TMDB_KEY or config.TMDB_TOKEN):
            st.info("Add TMDB_API_KEY or TMDB_BEARER_TOKEN to .env, then restart the app. See README for setup. No sample titles are substituted.")
            if st.button("Back to group"):
                goto("group")
            st.stop()
        try:
            genres, languages, providers = tmdb_client.catalog(s.region)
        except tmdb_client.TMDBError as exc:
            st.error(str(exc))
            if st.button("Retry loading preferences"):
                st.rerun()
            if st.button("Back to group"):
                goto("group")
            st.stop()
        s.genres_catalog = genres
        genre_options = sorted({g["name"] for entries in genres.values() for g in entries})
        language_names = {l["iso_639_1"]: l.get("english_name") or l["iso_639_1"] for l in languages}
        preferred = ["en", "hi", "ta", "te", "ml", "ko", "ja", "es", "fr", "de"]
        language_options = [l for l in preferred if l in language_names] + sorted(set(language_names) - set(preferred))
        st.write("Choose a tab for each person. Leave anything blank to keep your options open.")
        st.caption("Selected content types must work for everyone. Save all preferences together to find your shortlist.")
        with st.form("taste_profiles", border=False):
            tabs = st.tabs([u.name for u in s.users])
            for i, (tab, user) in enumerate(zip(tabs, s.users)):
                with tab:
                    prefix = f"pref_{i}_"
                    st.subheader(f"{user.name}'s preferences")
                    a, b = st.columns(2)
                    content = a.multiselect("What would you like to watch?", CONTENT, default=user.content, key=prefix+"content", placeholder="Any type / surprise me")
                    chosen_genres = b.multiselect("Favourite genres", genre_options, default=user.genres, key=prefix+"genres", placeholder="Any genre")
                    a, b = st.columns(2)
                    chosen_languages = a.multiselect("Original languages", language_options, default=user.languages, format_func=language_names.get, key=prefix+"languages", placeholder="Any language")
                    service_key = prefix+"providers"
                    if service_key in s and any(p not in providers for p in s[service_key]):
                        s[service_key] = [p for p in s[service_key] if p in providers]
                    chosen_providers = b.multiselect("Streaming subscriptions", sorted(providers, key=providers.get), default=[p for p in user.providers if p in providers], format_func=providers.get, key=service_key, placeholder="Any platform")
                    s.users[i] = Preference(name=user.name, content=content, genres=chosen_genres, languages=chosen_languages, providers=chosen_providers)
                    st.caption(f"{user.name}: {', '.join(content) or 'any content'} · {', '.join(chosen_genres) or 'any genre'} · {', '.join(language_names[l] for l in chosen_languages) or 'any language'} · {len(chosen_providers)} declared subscriptions")
            st.toggle("🔥 Roast Our Movie Taste", value=s.get("saved_roast_enabled", True), key="roast_enabled")
            s.saved_roast_enabled = s.roast_enabled
            st.divider()
            back_col, _, continue_col = st.columns([1.5, .5, 4])
            back_clicked = back_col.form_submit_button("Back", use_container_width=True)
            submitted = continue_col.form_submit_button("✨ Find Our Top 3 Recommendations", type="primary", use_container_width=True)
        if back_clicked:
            goto("group")
        if submitted:
            try:
                generate()
            except (tmdb_client.TMDBError, ValueError) as exc:
                st.error(str(exc))

elif s.stage == "reveal":
    with st.container(key="reveal_panel"):
        st.markdown('<div class="setup-meta"><span>MOVIE NIGHT</span><span>Step 3 of 3</span></div><div class="setup-progress reveal-progress" aria-label="Step 3 of 3"><i></i><i></i><i></i></div>', unsafe_allow_html=True)
        st.title("Your movie-night shortlist")
        st.caption("Compare your matches, then choose your winner. Details and viewing options are one click away.")
        st.divider()
        if s.notice:
            st.error(s.notice)
            retry_col, edit_col = st.columns(2)
            if retry_col.button("Retry AI selection", type="primary", use_container_width=True):
                try:
                    generate()
                except (tmdb_client.TMDBError, ValueError) as exc:
                    st.error(str(exc))
            if edit_col.button("Edit Preferences", use_container_width=True):
                goto("preferences")
            st.stop()
        if s.roast:
            commentary("🔥 THE FRIENDLY ROAST", s.roast, "roast")
        if s.analysis:
            commentary("✦ YOUR GROUP, DECODED", s.analysis["group_summary"])
            with st.expander("Group overlaps & compromises"):
                for key in ("common_interests", "conflicting_preferences"):
                    st.write(key.replace("_", " ").title() + ": " + ("; ".join(s.analysis[key]) or "None reported"))
        if len(s.batch) < 3:
            st.warning(f"Found {len(s.batch)} eligible unseen titles in this discovery batch. Relax content/subscription filters, change region, or search further. No titles were invented.")
        labels = ["🥇 Best Overall Match", "🥈 Strong Alternative", "🥉 Wildcard Pick"]
        if s.batch:
            for col, row, label in zip(st.columns(len(s.batch)), s.batch, labels):
                with col:
                    card(row, s.region, label)
            for col, row in zip(st.columns(len(s.batch)), s.batch):
                with col:
                    if st.button("🏆 Lock This In!", key="lock_"+row["candidate"].key, type="primary", use_container_width=True):
                        lock(row)
        st.divider()
        a, b = st.columns(2)
        if a.button("🔄 Show Us 3 More", use_container_width=True):
            try:
                generate()
            except (tmdb_client.TMDBError, ValueError) as exc:
                st.error(str(exc))
        if b.button("Edit Preferences", use_container_width=True):
            goto("preferences")
        st.divider()
        if len(s.batch) == 3:
            st.subheader("🎡 Still negotiating? Let destiny decide.")
            result = wheel([r["candidate"].title for r in s.batch], s.request_number, [r["candidate"].poster for r in s.batch])
            if isinstance(result, dict) and result.get("batch_id") == s.request_number and isinstance(result.get("index"), int) and 0 <= result["index"] < 3:
                if result.get("event") != s.wheel_event:
                    s.wheel_event = result["event"]
                    s.wheel_result = result["index"]
                    s.wheel_comment = groq_client.celebrate(s.batch[result["index"]]["candidate"].title, True)
            if s.wheel_result is not None:
                row = s.batch[s.wheel_result]
                wheel_selection(row, s.wheel_comment)
                if st.button("🏆 Lock in the wheel’s choice", type="primary", use_container_width=True):
                    lock(row, True)
        st.divider()
        st.caption("Ready for a fresh movie night? Start over to clear your group and preferences.")
        if st.button("↺ Start over", key="reveal_restart", type="secondary"):
            reset()
            st.rerun()

elif s.stage == "winner":
    party_markup = ""
    if s.get("celebrate_pending", False):
        components.html("""<script>
        function scrollToWinnerTop() {
            const doc = window.parent.document;
            const main = doc.querySelector('[data-testid="stMain"]')
                || doc.querySelector('[data-testid="stAppViewContainer"]');
            if (main) main.scrollTo({top: 0, behavior: 'instant'});
            window.parent.scrollTo({top: 0, behavior: 'instant'});
        }
        requestAnimationFrame(scrollToWinnerTop);
        setTimeout(scrollToWinnerTop, 150);
        setTimeout(scrollToWinnerTop, 400);
        </script>""", height=0)
        colors = ["#f2c879", "#edabbc", "#accde8", "#c3d9ac"]
        balloons = ''.join(
            f'<div class="party-balloon" style="left:{[2, 8, 86, 92][i]}%;--party-color:{colors[i % 4]};--delay:{i * .3}s;--drift:{[-12, 10, -10, 12][i]}px"><span></span></div>'
            for i in range(4)
        )
        ribbons = ''.join(
            f'<i class="party-piece {"party-curl" if i % 4 == 0 else "party-confetti"}" style="left:{[5, 12, 19, 81, 88, 95][i % 6]}%;--party-color:{colors[i % 4]};--delay:{i % 4 * .1}s;--drift:{(i % 3 - 1) * 16}px;--duration:{2.4 + i % 3 * .25}s"></i>'
            for i in range(18)
        )
        party_markup = f'<div class="winner-party" aria-hidden="true">{balloons}{ribbons}</div>'
        s.celebrate_pending = False
    with st.container(key="winner_panel"):
        st.markdown('<div class="winner-heading">' + party_markup + '<div class="winner-trophy">🏆</div><div class="destiny-eyebrow">THE DEBATE IS OFFICIALLY OVER</div><h1>Tonight’s watch is locked in.</h1><p>Good company. Great stories. Pass the popcorn.</p></div>', unsafe_allow_html=True)
        chosen = s.winner["candidate"]
        poster_col, details = st.columns([1, 1.8], gap="large")
        with poster_col:
            if chosen.poster:
                st.markdown(f'<img class="winner-poster" src="{escape(chosen.poster, quote=True)}" alt="{escape(chosen.title, quote=True)} poster">', unsafe_allow_html=True)
            else:
                st.markdown('<div class="winner-poster winner-placeholder">🎬<br>Poster unavailable</div>', unsafe_allow_html=True)
        with details:
            st.caption("YOUR WINNER")
            st.subheader(chosen.title)
            duration = f"{chosen.runtime} min" + (" / episode" if chosen.media_type == "tv" else "") if chosen.runtime else "Duration unreported"
            st.caption(f"{chosen.year} · {chosen.category} · {duration}")
            st.write(f"★ **{chosen.rating:.1f}/10** · {chosen.votes:,} TMDB votes")
            st.markdown(f'<div class="winner-quote">{escape(s.celebration)}</div>', unsafe_allow_html=True)
            subscription = chosen.providers.get("flatrate", [])
            st.markdown("**Where to watch**")
            st.write(", ".join(p["provider_name"] for p in subscription) if subscription else "Subscription availability unreported.")
            st.caption(f"Availability in {s.region}. Confirm viewing options before watching.")
            if chosen.watch_link:
                st.link_button("Find where to watch ↗", chosen.watch_link, type="primary", use_container_width=True)
            if chosen.trailer:
                st.link_button("▶ Watch trailer", chosen.trailer, use_container_width=True)
            with st.expander("About your pick"):
                st.write(chosen.overview)
                st.write(s.winner.get("reason", ""))
                st.link_button("View on TMDB", f"https://www.themoviedb.org/{chosen.media_type}/{chosen.id}")
        st.divider()
        back, more, restart = st.columns(3)
        if back.button("Back to shortlist", use_container_width=True):
            goto("reveal")
        if more.button("Find Something Else", use_container_width=True):
            try:
                generate()
            except (tmdb_client.TMDBError, ValueError) as exc:
                st.error(str(exc))
        restart.button("↺ Start over", key="winner_restart", use_container_width=True, on_click=reset)
