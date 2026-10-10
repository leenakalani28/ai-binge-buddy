import math
from src.config import WEIGHTS

def runtime_match(value, choice):
    if choice == "No Maximum Limit":
        return 1.0
    if not value:
        return 0.0
    if choice.startswith("Under"):
        return float(value < int(choice.split()[-1]))
    if choice.startswith("Over"):
        return float(value > int(choice.split()[-1]))
    lo, hi = map(int, choice.split("–"))
    return float(lo <= value <= hi)

def eligible(candidate, users):
    available = {p["provider_id"] for p in candidate.providers.get("flatrate", [])}
    # A shared viewing session can use any explicitly declared group subscription.
    services = {p for u in users for p in u.providers}
    return all(not u.content or candidate.category in u.content for u in users) and (not services or bool(services & available))

def user_score(candidate, user, weights=WEIGHTS):
    available = {p["provider_id"] for p in candidate.providers.get("flatrate", [])}
    parts = {"genre": len(set(user.genres) & set(candidate.genres)) / len(user.genres) if user.genres else 1,
        "content": float(not user.content or candidate.category in user.content),
        "language": float(not user.languages or candidate.language in user.languages),
        "streaming": float(not user.providers or bool(set(user.providers) & available))}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one scoring weight must be positive.")
    return round(100 * sum(weights[k] * v for k, v in parts.items()) / total, 1)

def rank(candidates, users, excluded=(), weights=WEIGHTS):
    ranked = []
    for c in candidates:
        if c.key in excluded or not eligible(c, users):
            continue
        scores = {u.name: user_score(c, u, weights) for u in users}
        values = list(scores.values())
        score = max(0, round(.7 * sum(values) / len(values) + .3 * min(values) - 5 * sum(v < 40 for v in values) / len(values), 1))
        quality = c.rating * math.log10(1 + c.votes)
        ranked.append({"candidate": c, "score": score, "user_scores": scores, "quality": quality})
    return sorted(ranked, key=lambda r: (-r["score"], -r["quality"], -r["candidate"].popularity, r["candidate"].key))

def explain(row, users):
    c = row["candidate"]
    details = []
    for u in users:
        matches = sorted(set(u.genres) & set(c.genres))
        notes = ["shared genres: " + ", ".join(matches)] if matches else ["a compromise on genre" if u.genres else "open genre preferences"]
        if u.languages and c.language not in u.languages:
            notes.append("original language differs from their preference")
        details.append(f"{u.name} — {'; '.join(notes)}.")
    return " ".join(details)
