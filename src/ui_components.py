from html import escape
import streamlit as st

def commentary(title, message, tone="analysis"):
    tone = tone if tone in {"analysis", "roast", "winner"} else "analysis"
    st.markdown(
        f'<section class="commentary commentary-{tone}"><div class="commentary-label">'
        f'{escape(title)}</div><div class="commentary-copy">{escape(message)}</div></section>',
        unsafe_allow_html=True,
    )

def wheel_selection(row, message):
    c = row["candidate"]
    poster = (f'<img class="destiny-poster" src="{escape(c.poster, quote=True)}" alt="{escape(c.title, quote=True)} poster">'
              if c.poster else '<div class="destiny-poster destiny-placeholder">🎬</div>')
    duration = f"{c.runtime} min" + (" / episode" if c.media_type == "tv" else "") if c.runtime else ""
    metadata = " · ".join(filter(None, [c.year, c.category, duration]))
    st.markdown(
        f'<section class="destiny-selection">{poster}<div class="destiny-details">'
        '<div class="destiny-eyebrow">✦ THE WHEEL HAS SPOKEN</div>'
        f'<h2>{escape(c.title)}</h2><div class="destiny-meta">{escape(metadata)}</div>'
        f'<div class="destiny-message">{escape(message)}</div>'
        '<div class="destiny-hint">Your movie-night pick is ready. Lock it in below, or spin again.</div>'
        '</div></section>', unsafe_allow_html=True,
    )

def journey(stage):
    active = {"welcome": 0, "group": 0, "preferences": 1, "reveal": 2, "winner": 2}[stage]
    labels = ["01 · Gather the gang", "02 · Set your preferences", "03 · Choose your winner"]
    items = ''.join(f'<div class="step {"active" if i == active else ""}">{label}</div>' for i, label in enumerate(labels))
    st.markdown(f'<div class="steps" aria-label="Your progress">{items}</div>', unsafe_allow_html=True)

def card(row, region, label=None):
    c = row["candidate"]
    with st.container(border=True):
        if label:
            st.markdown(f'<div class="kicker">{escape(label)}</div>', unsafe_allow_html=True)
        if c.poster:
            st.markdown(f'<img class="poster" src="{escape(c.poster, quote=True)}" alt="{escape(c.title, quote=True)} poster" loading="lazy">', unsafe_allow_html=True)
        else:
            st.markdown('<div class="poster poster-fallback">Poster unavailable</div>', unsafe_allow_html=True)
        st.subheader(c.title)
        st.caption(f"{c.year} · {c.category} · Original language: {c.language or 'unreported'}")
        st.caption(f"★ {c.rating:.1f}/10 · {c.votes:,} TMDB votes")
        duration = f"{c.runtime} min" if c.runtime else "Duration unreported"
        if c.media_type == "tv":
            duration += " per episode"
            if c.seasons is not None:
                duration += f" · {c.seasons} seasons"
        st.write(duration)
        st.caption(" · ".join(c.genres) or "Genres unreported")
        st.write(c.overview if len(c.overview) <= 180 else c.overview[:177].rsplit(' ', 1)[0] + '…')
        labels = {"flatrate": "Subscription", "free": "Free", "ads": "With ads", "rent": "Rent", "buy": "Buy"}
        found = False
        for access, providers in c.providers.items():
            if access != "flatrate":
                continue
            if providers:
                found = True
                st.caption(f"{labels[access]} ({region}): " + ", ".join(p["provider_name"] for p in providers))
        if not found:
            st.caption(f"No watch-provider availability reported for {region}.")
        with st.expander("Why this matches your group"):
            commentary("Why we picked this", row.get("reason", ""))
            if row.get("user_matches"):
                for name, reason in row["user_matches"].items():
                    st.write(f"{name}: {reason}")
            if row.get("compromise_note"):
                st.write(row["compromise_note"])
        with st.expander("Synopsis, cast & viewing options"):
            st.write(c.overview)
            for access, providers in c.providers.items():
                if providers:
                    st.write(f"**{labels[access]} ({region}):** " + ", ".join(p["provider_name"] for p in providers))
            if c.watch_link:
                st.link_button("Viewing options · JustWatch", c.watch_link, use_container_width=True)
            st.caption("Cast: " + (", ".join(c.cast) or "Unreported"))
            st.caption(("Director: " if c.media_type == "movie" else "Creator: ") + (", ".join(c.makers) or "Unreported"))
            st.link_button("View on TMDB", f"https://www.themoviedb.org/{c.media_type}/{c.id}", use_container_width=True)
        if c.trailer:
            st.link_button("Watch Trailer", c.trailer, use_container_width=True)
