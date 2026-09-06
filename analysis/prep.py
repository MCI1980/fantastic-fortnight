# analysis/prep.py
# Shot preparation: handedness normalization, validity filters, time windows.
#
# Sign convention AFTER prepare_shots():
#   positive path  = in-to-out for this golfer
#   positive face  = open for this golfer
#   positive ftp   = face open to path (fade/slice side)
#   positive side  = miss on the golfer's fade side (right for RH, left for LH)

from __future__ import annotations

import re
from datetime import timedelta
from typing import List, Optional

import pandas as pd

from integrations.base import SIGNED_FIELDS

SIDE_FIELDS = ["side_yds", "side_total_yds", "curve_yds"]

# Shot roles derived from TPS tags. Tag a set "drill", "warmup" or "game"
# (optionally "game: fairway finder") in TPS before hitting it.
ROLE_NORMAL = "normal"
ROLE_DRILL = "drill"
ROLE_WARMUP = "warmup"
ROLE_GAME = "game"
STATS_ROLES = (ROLE_NORMAL, ROLE_GAME)   # roles that count toward the yardage card and rules


def split_tags(value) -> List[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none"):
        return []
    return [t.strip().lower() for t in re.split(r"[,;|/]+", text) if t.strip()]


def shot_role(tags) -> str:
    for t in split_tags(tags):
        if t.startswith("drill"):
            return ROLE_DRILL
        if t.startswith("warm"):
            return ROLE_WARMUP
        if t.startswith("game"):
            return ROLE_GAME
    return ROLE_NORMAL


def stats_shots(df: pd.DataFrame) -> pd.DataFrame:
    """Shots that should feed the yardage card and coaching rules (no drill/warm-up balls)."""
    if df is None or df.empty or "role" not in df.columns:
        return df if df is not None else pd.DataFrame()
    return df[df["role"].isin(STATS_ROLES)].reset_index(drop=True)


def prepare_shots(df: pd.DataFrame, handedness: str = "right", flip_side_sign: bool = False) -> pd.DataFrame:
    """Return a copy with signs normalized for the golfer's handedness."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if str(handedness).lower().startswith("l"):
        for col in SIGNED_FIELDS:
            if col in out.columns:
                out[col] = -out[col]
    if flip_side_sign:
        for col in SIDE_FIELDS:
            if col in out.columns:
                out[col] = -out[col]
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["role"] = out["tags"].map(shot_role) if "tags" in out.columns else ROLE_NORMAL
    return out


def filter_valid(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that cannot be real full shots (radar glitches, whiffs)."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df
    if "carry_yds" in out.columns:
        out = out[out["carry_yds"].isna() | (out["carry_yds"] > 5)]
    if "smash_factor" in out.columns:
        out = out[out["smash_factor"].isna() | ((out["smash_factor"] > 0.8) & (out["smash_factor"] <= 1.62))]
    if "club" in out.columns:
        out = out[out["club"].astype(str) != "Unknown"]
    return out.reset_index(drop=True)


def recent_shots(df: pd.DataFrame, days: Optional[int] = 60, as_of: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Shots within the last N days (None = all)."""
    if df is None or df.empty or not days or "date" not in df.columns:
        return df if df is not None else pd.DataFrame()
    as_of = as_of or pd.Timestamp(df["date"].max())
    if pd.isna(as_of):
        return df
    cutoff = as_of - timedelta(days=int(days))
    return df[df["date"].isna() | (df["date"] >= cutoff)].reset_index(drop=True)
