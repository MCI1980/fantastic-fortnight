# analysis/gapping.py
# Per-club distance profile, bag gapping and the yardage card.

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from integrations.trackman import club_sort_key


def consistency_score(carry_std: float, carry_med: float, side_std: float) -> float:
    """
    0-100 consistency score. Roughly: a scratch player's 7-iron scores ~85,
    a typical 18-handicap ~60-70, a wild driver ~40.
    """
    if not carry_med or np.isnan(carry_med) or carry_med <= 0:
        return float("nan")
    cv = (carry_std / carry_med) if carry_std is not None and not np.isnan(carry_std) else 0.0
    side = side_std if side_std is not None and not np.isnan(side_std) else 0.0
    score = 100.0 - 250.0 * cv - 1.2 * side
    return float(max(0.0, min(100.0, score)))


def _p(q):
    def f(s):
        s = s.dropna()
        return float(np.percentile(s, q)) if len(s) else np.nan
    f.__name__ = f"p{q}"
    return f


def club_summary(df: pd.DataFrame, min_shots: int = 3) -> pd.DataFrame:
    """
    One row per club with distance, dispersion, delivery and strike stats.
    Index: club (sorted Driver -> wedges).
    """
    if df is None or df.empty or "club" not in df.columns:
        return pd.DataFrame()

    g = df.groupby("club")
    out = pd.DataFrame({"shots": g.size()})

    def add(col_out: str, col_in: str, fn):
        if col_in in df.columns:
            out[col_out] = g[col_in].agg(fn)
        else:
            out[col_out] = np.nan

    add("carry_med", "carry_yds", "median")
    add("carry_mean", "carry_yds", "mean")
    add("carry_std", "carry_yds", "std")
    add("carry_p20", "carry_yds", _p(20))
    add("carry_p80", "carry_yds", _p(80))
    add("carry_max", "carry_yds", "max")
    add("total_med", "total_yds", "median")
    add("side_mean", "side_yds", "mean")
    add("side_std", "side_yds", "std")
    add("side_abs_mean", "side_yds", lambda s: s.abs().mean())
    add("ball_speed_mean", "ball_speed_mph", "mean")
    add("club_speed_mean", "club_speed_mph", "mean")
    add("smash_mean", "smash_factor", "mean")
    add("smash_std", "smash_factor", "std")
    add("launch_mean", "launch_angle_deg", "mean")
    add("spin_mean", "spin_rate_rpm", "mean")
    add("attack_mean", "attack_angle_deg", "mean")
    add("path_mean", "club_path_deg", "mean")
    add("face_mean", "face_angle_deg", "mean")
    add("ftp_mean", "face_to_path_deg", "mean")
    add("ftp_std", "face_to_path_deg", "std")
    add("spin_loft_mean", "spin_loft_deg", "mean")
    add("dyn_loft_mean", "dynamic_loft_deg", "mean")
    add("height_mean", "height_yds", "mean")
    add("land_angle_mean", "landing_angle_deg", "mean")
    add("impact_offset_mean", "impact_offset_mm", "mean")
    add("impact_offset_std", "impact_offset_mm", "std")
    add("impact_height_mean", "impact_height_mm", "mean")
    add("impact_height_std", "impact_height_mm", "std")
    add("impact_n", "impact_offset_mm", "count")
    add("last_date", "date", "max")

    out["carry_cv"] = out["carry_std"] / out["carry_med"]
    out["consistency"] = [
        consistency_score(r.carry_std, r.carry_med, r.side_std) for r in out.itertuples()
    ]
    out = out[out["shots"] >= max(1, int(min_shots))]
    out = out.loc[sorted(out.index, key=club_sort_key)]
    return out


def bag_gaps(summary: pd.DataFrame, overlap_yds: float = 6.0, hole_yds: float = 18.0) -> pd.DataFrame:
    """
    Carry gaps between adjacent clubs (longest to shortest).
    status: 'overlap' (< overlap_yds), 'gap' (> hole_yds) or 'ok'.
    """
    if summary is None or summary.empty or "carry_med" not in summary.columns:
        return pd.DataFrame(columns=["from_club", "to_club", "gap_yds", "status"])
    s = summary["carry_med"].dropna()
    clubs = list(s.index)
    rows = []
    for a, b in zip(clubs[:-1], clubs[1:]):
        gap = float(s[a] - s[b])
        status = "overlap" if gap < overlap_yds else ("gap" if gap > hole_yds else "ok")
        rows.append({"from_club": a, "to_club": b, "gap_yds": round(gap, 1), "status": status})
    return pd.DataFrame(rows)


def yardage_card(summary: pd.DataFrame, handedness: str = "right") -> pd.DataFrame:
    """
    Phone-friendly yardage card.
      Safe  = 20th percentile carry (use to clear trouble)
      Plan  = median carry (normal club selection)
      Max   = 80th percentile carry
      Miss  = average offline bias with direction
      ±     = one-sigma side dispersion
    """
    if summary is None or summary.empty:
        return pd.DataFrame()
    fade_word, draw_word = ("R", "L") if not str(handedness).lower().startswith("l") else ("L", "R")
    rows = []
    for club, r in summary.iterrows():
        bias = r.get("side_mean", np.nan)
        if bias is None or np.isnan(bias):
            miss = "-"
        elif abs(bias) < 2:
            miss = "centre"
        else:
            miss = f"{abs(bias):.0f} {fade_word if bias > 0 else draw_word}"
        rows.append({
            "Club": club,
            "Shots": int(r["shots"]),
            "Safe": _r(r.get("carry_p20")),
            "Plan": _r(r.get("carry_med")),
            "Max": _r(r.get("carry_p80")),
            "Total": _r(r.get("total_med")),
            "Miss": miss,
            "±": _r(r.get("side_std")),
            "Consistency": _r(r.get("consistency")),
        })
    return pd.DataFrame(rows)


def _r(v) -> Optional[int]:
    try:
        if v is None or np.isnan(v):
            return None
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None
