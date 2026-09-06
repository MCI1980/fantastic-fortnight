# analysis/tendencies.py
# Shot-shape classification, miss patterns and strike quality.
# Assumes sign-normalized shots (see analysis.prep): positive = fade side.

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from integrations.trackman import club_category

START_T = 2.0       # deg of face angle before we call it a push/pull
CURVE_T = 2.0       # deg of face-to-path before we call it a fade/draw
BIG_CURVE_T = 5.0   # deg of face-to-path before we call it a slice/hook

# Solid-strike smash factor expectations by club (amateur-realistic)
EXPECTED_SMASH: Dict[str, float] = {
    "Driver": 1.47,
    "Wood": 1.44,
    "Hybrid": 1.41,
    "Long Iron": 1.39,
    "Mid Iron": 1.36,
    "Short Iron": 1.31,
    "Wedge": 1.22,
    "PW": 1.27,
    "Other": 1.35,
}


def expected_smash(club: str) -> float:
    if club == "PW":
        return EXPECTED_SMASH["PW"]
    return EXPECTED_SMASH.get(club_category(club), EXPECTED_SMASH["Other"])


def classify_shot(face: Optional[float], ftp: Optional[float]) -> Tuple[str, str, str]:
    """
    Returns (start, curve, label) for a right-handed convention:
      start: 'push' | 'pull' | 'straight'
      curve: 'slice' | 'fade' | 'straight' | 'draw' | 'hook'
    Words are handedness-neutral in meaning (push = starts on the fade side).
    """
    if face is None or ftp is None or (isinstance(face, float) and np.isnan(face)) or (isinstance(ftp, float) and np.isnan(ftp)):
        return ("unknown", "unknown", "unknown")
    start = "push" if face > START_T else ("pull" if face < -START_T else "straight")
    if ftp > BIG_CURVE_T:
        curve = "slice"
    elif ftp > CURVE_T:
        curve = "fade"
    elif ftp < -BIG_CURVE_T:
        curve = "hook"
    elif ftp < -CURVE_T:
        curve = "draw"
    else:
        curve = "straight"
    if start == "straight" and curve == "straight":
        label = "straight"
    elif start == "straight":
        label = curve
    elif curve == "straight":
        label = start
    else:
        label = f"{start}-{curve}"
    return (start, curve, label)


def shot_labels(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty or "face_to_path_deg" not in df.columns:
        return pd.Series(dtype=str)
    face = df["face_angle_deg"] if "face_angle_deg" in df.columns else pd.Series(np.nan, index=df.index)
    return pd.Series(
        [classify_shot(f, p)[2] for f, p in zip(face, df["face_to_path_deg"])],
        index=df.index,
    )


def miss_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Counts and percentages of each shot-shape label."""
    labels = shot_labels(df)
    labels = labels[labels != "unknown"]
    if labels.empty:
        return pd.DataFrame(columns=["label", "count", "pct"])
    counts = labels.value_counts()
    out = pd.DataFrame({"label": counts.index, "count": counts.values})
    out["pct"] = (out["count"] / out["count"].sum() * 100).round(0)
    return out.reset_index(drop=True)


def club_tendencies(df: pd.DataFrame, club: str) -> Dict:
    """Summary of how one club tends to miss."""
    sub = df[df["club"] == club] if (df is not None and not df.empty) else pd.DataFrame()
    if sub.empty:
        return {"club": club, "n": 0}
    pattern = miss_pattern(sub)
    top = pattern.iloc[0] if not pattern.empty else None

    def m(col):
        return float(sub[col].mean()) if col in sub.columns and sub[col].notna().any() else float("nan")

    def sd(col):
        return float(sub[col].std()) if col in sub.columns and sub[col].notna().sum() > 1 else float("nan")

    return {
        "club": club,
        "n": int(len(sub)),
        "top_miss": None if top is None else str(top["label"]),
        "top_miss_pct": None if top is None else float(top["pct"]),
        "path_mean": m("club_path_deg"),
        "face_mean": m("face_angle_deg"),
        "ftp_mean": m("face_to_path_deg"),
        "ftp_std": sd("face_to_path_deg"),
        "side_mean": m("side_yds"),
        "side_std": sd("side_yds"),
        "pattern": pattern,
    }


def strike_quality(df: pd.DataFrame, club: str) -> Dict:
    sub = df[df["club"] == club] if (df is not None and not df.empty) else pd.DataFrame()
    exp = expected_smash(club)
    if sub.empty or "smash_factor" not in sub.columns or sub["smash_factor"].notna().sum() == 0:
        return {"club": club, "n": 0, "expected": exp}
    s = sub["smash_factor"].dropna()
    solid = (s >= exp - 0.04).mean() * 100
    return {
        "club": club,
        "n": int(len(s)),
        "expected": exp,
        "smash_mean": float(s.mean()),
        "smash_std": float(s.std()) if len(s) > 1 else float("nan"),
        "pct_solid": float(solid),
    }
