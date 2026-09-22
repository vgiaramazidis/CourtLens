"""Database-backed game labels and player identities for Quiz Ball."""

import re

from .search_answers import profile_answer, value


def game_stage(row):
    phase, group = value(row, "phase"), value(row, "phaseGroup")
    label = re.sub(r"[^a-z0-9]+", " ", group.lower()).strip()
    if label in {"championship game", "final", "finals"}:
        return "Final"
    if "semi" in label:
        return "Semi-final"
    if label in {"third place game", "third place", "3rd place game", "3rd place"}:
        return "Third-place game"
    if "play in" in label:
        return "Play-in"
    normalized = re.sub(r"[^a-z0-9]+", " ", phase.lower()).strip()
    known = {
        "regular season": "Regular season",
        "playoffs": "Playoffs",
        "play offs": "Playoffs",
        "final four": "Final Four",
        "play in": "Play-in",
        "play in showdown": "Play-in",
    }
    return known.get(normalized, phase.strip())


def quiz_player_profile(player_id, data):
    rows = (data or {}).get("results", {}).get("bindings", [])
    if not rows or not value(rows[0], "name"):
        return {"id": player_id, "name": ""}
    row = dict(rows[0])
    row["player"] = f"https://www.euroleaguebasketball.net/euroleague/players/-/{player_id}"
    row["achievements"] = row.get("achievements_text", "")
    row["country"] = value(row, "country").rsplit("/", 1)[-1]
    profile = profile_answer([row], value(row, "name"))["profiles"][0]
    return dict(profile, id=player_id, img=profile["image"])


def missing_lineup(profiles, secret_index):
    """Illustrative arrangement by listed role, without inventing PG/SG assignments."""
    order = {"Center": 0, "Forward": 1, "Guard": 2}
    arranged = sorted(
        enumerate(profiles),
        key=lambda item: min(
            (order.get(role, 3) for role in item[1].get("position", "").split(" / ")), default=3
        ),
    )
    return [
        {
            "missing": index == secret_index,
            "position": profile.get("position", ""),
            "player": None
            if index == secret_index
            else {key: profile.get(key, "") for key in ("id", "name", "img", "position")},
        }
        for index, profile in arranged
    ]
