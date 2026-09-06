# analysis/scoring.py
# Round statistics and a "strokes lost" comparison against a target
# scoring level. Benchmarks are approximate per-round averages compiled
# from published amateur shot-tracking data; they are meant to point at
# the biggest leak, not to be precise to the stroke.

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from data.rounds import Round

# Per-round averages by typical 18-hole scoring level.
BENCHMARKS: Dict[int, Dict[str, float]] = {
    100: {"putts": 37.5, "three_putts": 3.6, "penalties": 2.6, "fir_pct": 33, "gir_pct": 8,  "doubles_plus": 7.0, "scrambling_pct": 9},
    95:  {"putts": 36.5, "three_putts": 3.0, "penalties": 2.0, "fir_pct": 38, "gir_pct": 12, "doubles_plus": 5.5, "scrambling_pct": 12},
    90:  {"putts": 35.5, "three_putts": 2.3, "penalties": 1.5, "fir_pct": 43, "gir_pct": 18, "doubles_plus": 4.0, "scrambling_pct": 17},
    85:  {"putts": 34.5, "three_putts": 1.6, "penalties": 1.0, "fir_pct": 48, "gir_pct": 26, "doubles_plus": 2.5, "scrambling_pct": 23},
    80:  {"putts": 33.5, "three_putts": 1.0, "penalties": 0.6, "fir_pct": 52, "gir_pct": 36, "doubles_plus": 1.3, "scrambling_pct": 30},
    75:  {"putts": 32.5, "three_putts": 0.6, "penalties": 0.3, "fir_pct": 56, "gir_pct": 47, "doubles_plus": 0.6, "scrambling_pct": 40},
}

CATEGORY_LABELS = {
    "penalties": "Penalty strokes / round",
    "three_putts": "Three-putts / round",
    "putts": "Putts / round",
    "gir_pct": "Greens in regulation %",
    "fir_pct": "Fairways hit %",
    "doubles_plus": "Double bogey or worse / round",
    "scrambling_pct": "Scrambling (up & down) %",
}


def benchmark_for(target_score: int) -> Dict[str, float]:
    """Linear interpolation between the benchmark rows."""
    keys = sorted(BENCHMARKS)
    t = float(target_score)
    if t <= keys[0]:
        return dict(BENCHMARKS[keys[0]])
    if t >= keys[-1]:
        return dict(BENCHMARKS[keys[-1]])
    for lo, hi in zip(keys[:-1], keys[1:]):
        if lo <= t <= hi:
            w = (t - lo) / (hi - lo)
            return {k: BENCHMARKS[lo][k] + w * (BENCHMARKS[hi][k] - BENCHMARKS[lo][k]) for k in BENCHMARKS[lo]}
    return dict(BENCHMARKS[85])


def _scale18(value: float, holes: int) -> float:
    """Scale a per-round count to an 18-hole equivalent."""
    return value * 18.0 / holes if holes else value


def round_stats(rnd: Round) -> Dict:
    holes = rnd.holes_played or 18
    putts = rnd.putts
    return {
        "id": rnd.id,
        "date": rnd.date,
        "course": rnd.course,
        "tees": rnd.tees,
        "holes": holes,
        "score": rnd.total,
        "score18": _scale18(rnd.total, holes),
        "par": rnd.par,
        "to_par": rnd.to_par,
        "putts": putts,
        "putts18": _scale18(putts, holes) if putts is not None else None,
        "three_putts": _scale18(rnd.three_putts, holes) if putts is not None else None,
        "penalties": _scale18(rnd.penalties, holes),
        "fir_pct": (rnd.fir_hit / rnd.fir_opps * 100) if rnd.fir_opps else None,
        "gir_pct": (rnd.gir_hit / rnd.gir_opps * 100) if rnd.gir_opps else None,
        "doubles_plus": _scale18(rnd.doubles_plus, holes),
        "birdies": rnd.birdies_or_better,
        "pars": rnd.pars,
        "bogeys": rnd.bogeys,
        "scrambling_pct": (rnd.scramble_saves / rnd.scramble_attempts * 100) if rnd.scramble_attempts else None,
        "scramble_attempts": rnd.scramble_attempts,
    }


def rounds_frame(rounds: List[Round]) -> pd.DataFrame:
    if not rounds:
        return pd.DataFrame()
    df = pd.DataFrame([round_stats(r) for r in rounds])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def aggregate_rounds(rounds: List[Round], last_n: Optional[int] = 10) -> Dict:
    """Average per-round stats over the most recent rounds."""
    if not rounds:
        return {"n_rounds": 0}
    df = rounds_frame(rounds)
    if last_n:
        df = df.tail(int(last_n))

    def mean(col):
        return float(df[col].dropna().mean()) if col in df.columns and df[col].notna().any() else None

    return {
        "n_rounds": int(len(df)),
        "score": mean("score18"),
        "best": float(df["score18"].min()) if "score18" in df.columns else None,
        "worst": float(df["score18"].max()) if "score18" in df.columns else None,
        "putts": mean("putts18"),
        "three_putts": mean("three_putts"),
        "penalties": mean("penalties"),
        "fir_pct": mean("fir_pct"),
        "gir_pct": mean("gir_pct"),
        "doubles_plus": mean("doubles_plus"),
        "scrambling_pct": mean("scrambling_pct"),
        "scramble_attempts": float(df["scramble_attempts"].sum()) if "scramble_attempts" in df.columns else 0.0,
        "birdies": mean("birdies"),
        "pars": mean("pars"),
        "bogeys": mean("bogeys"),
    }


def strokes_lost(agg: Dict, target_score: int = 85) -> pd.DataFrame:
    """
    Compare your averages with a target scoring level and estimate strokes
    per round attributable to each category. Estimates are indicative.
    """
    if not agg or not agg.get("n_rounds"):
        return pd.DataFrame(columns=["category", "you", "benchmark", "est_strokes", "note"])
    bench = benchmark_for(target_score)
    rows = []

    def add(key, weight, note, higher_is_worse=True, fmt="{:.1f}"):
        you = agg.get(key)
        if you is None:
            return
        b = bench[key]
        diff = (you - b) if higher_is_worse else (b - you)
        est = max(0.0, diff * weight)
        rows.append({
            "category": CATEGORY_LABELS.get(key, key),
            "you": you,
            "benchmark": b,
            "est_strokes": round(est, 1),
            "note": note,
        })

    # weights: approximate strokes per unit of difference (per round)
    add("penalties", 1.0, "Each penalty is at least one stroke, usually more with the recovery.")
    add("three_putts", 0.9, "A three-putt is close to a full stroke lost every time.")
    add("putts", 0.35, "Putts beyond the benchmark, discounted for overlap with three-putts.")
    add("gir_pct", 0.18 * 0.55, "Each missed green costs roughly half a stroke on average.", higher_is_worse=False)
    add("fir_pct", 0.18 * 0.25, "A missed fairway costs about a quarter stroke on average.", higher_is_worse=False)
    add("scrambling_pct", 0.10 * 0.6, "Failed up-and-downs, scaled by typical attempts per round.", higher_is_worse=False)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("est_strokes", ascending=False).reset_index(drop=True)
    return out
