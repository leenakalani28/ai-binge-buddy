# AI Binge Buddy

Less scrolling. More watching. Zero arguments. (Well, almost.)

A working Streamlit movie-night app for 1–6 people, using real TMDB titles and regional watch providers, LLM-led selection, optional Groq commentary, and an animated three-title decision wheel.

## Run on Windows

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then open PowerShell in this folder:

```powershell
Copy-Item .env.example .env
# Edit .env with your server-side credentials.
uv sync
uv run streamlit run app.py
```

This workspace also has uv at `C:\OM AI Learning\tools\uv\uv.exe`. If uv is not on PATH, use `& 'C:\OM AI Learning\tools\uv\uv.exe'` in place of `uv`.

Create a TMDB account and request an API key under [account API settings](https://www.themoviedb.org/settings/api). Set `TMDB_API_KEY`, or use the API read-access token as `TMDB_BEARER_TOKEN`. Create a [Groq API key](https://console.groq.com/keys) and set `GROQ_API_KEY`. `GROQ_MODEL` defaults to `openai/gpt-oss-120b`; you can change it to a supported JSON-mode chat model. Restart Streamlit after changing credentials. Credentials stay server-side. `.env` is ignored.

TMDB and Groq are required for recommendations. If Groq fails or its response is invalid, the app displays an error and Retry AI selection button while preserving preferences. No Python fallback titles are shown.

## How it works

1. Name the group and choose the viewing region (UK by default).
2. Set each person's content, genres, original languages and subscriptions. Empty multiselects mean Any / Surprise Me. Runtime and mood are no longer preference inputs; runtime remains factual information on cards.
3. Find the shortlist, inspect details, choose a winner, request unseen titles or spin the wheel.

Content categories are hard constraints for every person: documentaries are TMDB genre 99 combined with movie/TV media type. A candidate must have confirmed `flatrate` availability on at least one subscription declared by the group when subscriptions are supplied. This assumes a shared viewing session using any group member's service. Rent/buy/free/ads are displayed separately and do not count as subscription access. With no declared services, availability is unrestricted and clearly reported.

Normal selection is LLM-led. Every retrieved candidate that passes content, shared regional subscription and unseen-title eligibility goes to Groq, without Python scoring, a 12-title cap or an eight-point cutoff. Compact metadata includes ID/type, title, genres, original language, a short supplied synopsis, rating/vote count and confirmed subscription providers. Groq evaluates all four user preferences, balances the group, orders up to three picks and explains each person's fit and compromises. No match percentages are generated or displayed.

Python validates the response structure, exact count, unique supplied media-type/ID pairs and personalised explanations for every submitted name. It displays TMDB metadata rather than AI-generated facts. If Groq fails or validation rejects its response, no titles are selected. The error screen lets you retry with cached candidates or edit preferences. Python scoring is not used for selection.

Discovery combines general popularity, preferred genres and original languages over two pages per query. Discovery queries run concurrently and reuse HTTP connections. The initial pass enriches up to 48 titles with eight workers, expanding to at most 120 only when fewer than three eligible titles remain. Further searches reuse cached details and advance discovery pages if the existing pool has fewer than three unseen eligible candidates. This bounded search is practical rather than an exhaustive catalogue search; an empty result does not prove no matching title exists. All previously displayed `media_type:id` keys are excluded until preferences/region change or Start Over is used.

TMDB requests are cached for one hour; clients use bounded timeouts and backoff for transient errors (three TMDB attempts and two Groq attempts). State retains user preferences, exclusions, analysis, roast, winner and wheel events across reruns. Groq is called on an explicit recommendation request or new winner/wheel event, not ordinary widget reruns. No artificial loading delays are added.

The wheel is a bundled, dependency-free Streamlit HTML component. Browser cryptographic rejection sampling gives each of exactly three titles equal probability. Its animation targets the chosen sector, checks the final pointer sector, and sends that index and a unique event to Python. The spin button is disabled during animation; another spin is allowed. Python checks the current batch and result bounds. The LLM only comments on the result.

Metadata is sourced from TMDB; watch-provider data is supplied by JustWatch via TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB. Availability may change; provider links let you confirm. Original language does not verify dubbing or subtitles. Posters, official YouTube trailers, cast, directors and creators are shown only when returned by TMDB. Missing metadata is labelled rather than invented.

API references: [TMDB discovery](https://developer.themoviedb.org/reference/discover-movie), [regional watch providers and JustWatch attribution](https://developer.themoviedb.org/reference/tv-series-watch-providers), [Groq JSON mode](https://console.groq.com/docs/structured-outputs), [model documentation](https://console.groq.com/docs/models).

## Verification

```powershell
uv run pytest
```

Automated checks use mocked external metadata and cover group limits, duplicate names, region-specific subscription eligibility, documentary types, conflicts, Any choices, unlimited/unknown runtime, fairness, fewer than three results, duplicate exclusion, model response validation, Groq failure, wheel geometry/equal-probability sampling and Streamlit navigation/session persistence. A real credentialed TMDB/Groq end-to-end run and visual browser wheel test still require API keys and a browser.

## Interface

The responsive dark interface uses high-contrast labels, two-column preference fields and compact poster cards. Preferences are batched in a form to avoid server reruns for every change. Submit all profiles together with the recommendation button. Full synopses, personalised explanations, credits and viewing options are expandable. The progress strip is removed; Start Over remains available.
