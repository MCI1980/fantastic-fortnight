# analysis/games.py
# Scored practice games computed straight from imported TrackMan shots.

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml

from analysis.tendencies import expected_smash
from integrations.trackman import club_category


def load_games(path: Optional[Path] = None) -> List[Dict]:
    path = path or Path(__file__).resolve().parent.parent / "data" / "games.yaml"
    try:
        games = yaml.safe_load(path.read_text(encoding="utf-8"))
        return games if isinstance(games, list) else []
    except Exception:
        return []


def games_for_tags(tags: List[str], games: List[Dict]) -> List[Dict]:
    tagset = set(tags or [])
    return [g for g in games if tagset & set(g.get("tags", []))]


def game_applies_to_club(game: Dict, club: str) -> bool:
    want = str(game.get("club_category", "any")).lower()
    cat = club_category(club).lower()
    if want == "any":
        return True
    if want == "iron":
        return cat.endswith("iron") or club == "PW"
    if want == "wedge":
        return cat == "wedge"
    return cat == want


def score_game(game: Dict, shots: pd.DataFrame, club: str) -> Dict:
    """
    Score a game against the last N shots of `club` in `shots`.
    Returns points, max_points, pct and a per-shot detail frame.
    """
    n = int(game.get("shots", 10))
    metric = game.get("metric")
    rule = game.get("rule", "abs_within")
    threshold = float(game.get("threshold", 0))

    sub = shots[shots["club"] == club] if (shots is not None and not shots.empty and "club" in shots.columns) else pd.DataFrame()
    if "date" in sub.columns:
        sub = sub.sort_values(["date", "shot_number"] if "shot_number" in sub.columns else "date")
    sub = sub.tail(n)
    if sub.empty or metric not in sub.columns:
        return {"game": game.get("name"), "club": club, "points": 0, "max_points": n, "pct": 0.0, "shots_used": 0, "detail": pd.DataFrame(), "ready": False}

    vals = sub[metric].astype(float)
    if rule == "abs_within":
        hits = vals.abs() <= threshold
    elif rule == "at_least":
        hits = vals >= threshold
    elif rule == "at_most":
        hits = vals <= threshold
    elif rule == "at_least_expected":
        hits = vals >= (expected_smash(club) + threshold)
    elif rule == "within_pct_of_median":
        med = float(vals.median())
        hits = (vals - med).abs() <= abs(threshold) * med
    else:
        hits = pd.Series(False, index=vals.index)

    detail = pd.DataFrame({"shot": range(1, len(vals) + 1), metric: vals.values, "hit": hits.values})
    points = int(hits.fillna(False).sum())
    return {
        "game": game.get("name"),
        "club": club,
        "points": points,
        "max_points": n,
        "pct": round(points / n * 100, 0),
        "shots_used": int(len(vals)),
        "detail": detail,
        "ready": len(vals) >= n,
    }
