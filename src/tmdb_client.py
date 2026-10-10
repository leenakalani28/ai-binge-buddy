import time
from concurrent.futures import ThreadPoolExecutor
import httpx
import streamlit as st
from src.config import TMDB_KEY, TMDB_TOKEN
from src.preference_models import Candidate

class TMDBError(Exception):
    pass

@st.cache_resource
def client():
    # Reuse TLS connections instead of establishing one for each title.
    return httpx.Client(timeout=12, limits=httpx.Limits(max_connections=12, max_keepalive_connections=12))

@st.cache_data(ttl=3600, show_spinner=False)
def request(path, **params):
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}"} if TMDB_TOKEN else {}
    if not TMDB_TOKEN:
        params["api_key"] = TMDB_KEY
    for attempt in range(3):
        try:
            response = client().get(f"https://api.themoviedb.org/3/{path}", params=params, headers=headers)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    time.sleep(min(float(response.headers.get("Retry-After", 2 ** attempt)), 5))
                    continue
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                raise TMDBError("TMDB could not complete the request. Check your credentials or try again shortly.") from None
            time.sleep(2 ** attempt)
    raise TMDBError("TMDB is temporarily unavailable.")

@st.cache_data(ttl=86400, show_spinner="Loading genres, languages and streaming services…")
def catalog(region):
    # These independent reference endpoints used to block the form sequentially.
    queries = [
        ("genre/movie/list", {}), ("genre/tv/list", {}),
        ("configuration/languages", {}),
        ("watch/providers/movie", {"watch_region": region}),
        ("watch/providers/tv", {"watch_region": region}),
    ]
    def fetch(query):
        path, params = query
        return request(path, **params)
    with ThreadPoolExecutor(max_workers=5) as pool:
        movie_genres, tv_genres, languages, movie_providers, tv_providers = list(pool.map(fetch, queries))
    genres = {"movie": movie_genres["genres"], "tv": tv_genres["genres"]}
    providers = {}
    for response in (movie_providers, tv_providers):
        for item in response["results"]:
            providers[item["provider_id"]] = item["provider_name"]
    return genres, languages, providers

def enrich(media, identifier, region):
    data = request(f"{media}/{identifier}", append_to_response="credits,videos,watch/providers")
    watch = data.get("watch/providers", {}).get("results", {}).get(region, {})
    videos = data.get("videos", {}).get("results", [])
    trailer = next((v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("official")), None)
    credits = data.get("credits", {})
    runtime = data.get("runtime") if media == "movie" else next(iter(data.get("episode_run_time", [])), None)
    if media == "tv" and not runtime:
        runtime = (data.get("last_episode_to_air") or {}).get("runtime")
    return Candidate(id=identifier, media_type=media, title=data.get("title") or data.get("name"),
        year=(data.get("release_date") or data.get("first_air_date") or "Unknown")[:4],
        genres=[g["name"] for g in data.get("genres", [])], language=data.get("original_language", ""),
        runtime=runtime, seasons=data.get("number_of_seasons"), rating=data.get("vote_average", 0),
        votes=data.get("vote_count", 0), popularity=data.get("popularity", 0), overview=data.get("overview") or "Synopsis unavailable.",
        poster=f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get("poster_path") else None,
        providers={k: watch.get(k, []) for k in ("flatrate", "free", "ads", "rent", "buy")}, watch_link=watch.get("link"),
        trailer=f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None,
        cast=[c["name"] for c in credits.get("cast", [])[:5]],
        makers=[c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"][:3] if media == "movie" else [c["name"] for c in data.get("created_by", [])])

def discover(users, region, genres, excluded, start_page=1):
    """Bounded diverse discovery; detailed provider responses are authoritative."""
    tasks = {}
    queries = []
    services = sorted({p for u in users for p in u.providers})
    for media in ("movie", "tv"):
        categories = {"Movies", "Documentaries"} if media == "movie" else {"TV Series", "Documentary Series"}
        if any(u.content and not categories.intersection(u.content) for u in users):
            continue
        base = {"watch_region": region, "include_adult": "false", "sort_by": "popularity.desc", "vote_count.gte": 30}
        if services:
            base.update(with_watch_providers="|".join(map(str, services)), with_watch_monetization_types="flatrate")
        desired_genres = {g for u in users for g in u.genres}
        if any(u.content and set(u.content) <= {"Documentaries", "Documentary Series"} for u in users):
            desired_genres = {"Documentary"}
            base["with_genres"] = 99
        variants = [base]
        for genre in genres[media]:
            if genre["name"] in desired_genres:
                variants.append({**base, "with_genres": genre["id"]})
        for language in sorted({l for u in users for l in u.languages}):
            variants.append({**base, "with_original_language": language})
        for variant in variants[:10]:
            for page in range(start_page, start_page + 2):
                queries.append((media, page, variant))
    def search(query):
        media, page, variant = query
        return media, request(f"discover/{media}", page=page, **variant).get("results", [])
    with ThreadPoolExecutor(max_workers=6) as pool:
        for media, rows in pool.map(search, queries):
            for position, row in enumerate(rows):
                if f"{media}:{row['id']}" not in excluded:
                    key = (media, row["id"])
                    # Interleave top results from every preference query.
                    tasks[key] = min(tasks.get(key, 100), position)
    errors = []
    def load(task):
        try:
            return enrich(*task, region)
        except TMDBError:
            errors.append(task)
            return None
    ordered = sorted(tasks, key=lambda key: (tasks[key], key))[:120]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [c for c in pool.map(load, ordered[:48]) if c]
        from src.recommendation_engine import eligible
        if sum(eligible(c, users) for c in results) < 3:
            results.extend(c for c in pool.map(load, ordered[48:]) if c)
    if tasks and not results and errors:
        raise TMDBError("TMDB title details could not be loaded. Please retry.")
    return results
