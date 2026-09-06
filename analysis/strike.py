# analysis/strike.py
# Impact location on the club face (TrackMan "Impact Offset" / "Impact Height").
#
# Sign convention (TrackMan): Impact Offset positive = toward the toe,
# negative = toward the heel; Impact Height positive = above face centre.
# Flip IMPACT_TOE_POSITIVE if a future export proves otherwise.

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

IMPACT_TOE_POSITIVE = True

# Thresholds in millimetres
OFFSET_BIAS_MM = 8.0          # average heel/toe bias worth flagging
LOW_BIAS_MM = {"Driver": -6.0, "default": -10.0}
SCATTER_MM = 12.0             # one-sigma heel/toe spread worth flagging


def impact_summary(df: pd.DataFrame, club: str) -> Dict:
    """Average strike location and spread for one club, in mm from face centre."""
    sub = df[df["club"] == club] if (df is not None and not df.empty and "club" in df.columns) else pd.DataFrame()
    if sub.empty or "impact_offset_mm" not in sub.columns:
        return {"club": club, "n": 0}
    off = pd.to_numeric(sub["impact_offset_mm"], errors="coerce")
    hgt = pd.to_numeric(sub.get("impact_height_mm"), errors="coerce") if "impact_height_mm" in sub.columns else pd.Series(np.nan, index=sub.index)
    valid = off.notna()
    n = int(valid.sum())
    if n == 0:
        return {"club": club, "n": 0}
    off_v = off[valid]
    hgt_v = hgt[valid]
    off_mean = float(off_v.mean())
    toe_sign = 1.0 if IMPACT_TOE_POSITIVE else -1.0
    horiz = "toe" if off_mean * toe_sign > 0 else "heel"
    hgt_mean = float(hgt_v.mean()) if hgt_v.notna().any() else float("nan")
    vert = "high" if (not np.isnan(hgt_mean) and hgt_mean > 0) else "low"
    return {
        "club": club,
        "n": n,
        "offset_mean": off_mean,
        "offset_std": float(off_v.std()) if n > 1 else float("nan"),
        "height_mean": hgt_mean,
        "height_std": float(hgt_v.std()) if hgt_v.notna().sum() > 1 else float("nan"),
        "horizontal": horiz,
        "vertical": vert,
        "label": _label(off_mean, hgt_mean, horiz, vert),
        "points": pd.DataFrame({
            "Heel (-)  →  Toe (+)  mm": off_v.values * toe_sign,
            "Low (-)  →  High (+)  mm": hgt_v.values,
        }),
    }


def _label(off_mean: float, hgt_mean: float, horiz: str, vert: str) -> str:
    parts = []
    if abs(off_mean) >= 4:
        parts.append(f"{abs(off_mean):.0f} mm {horiz}")
    if not np.isnan(hgt_mean) and abs(hgt_mean) >= 4:
        parts.append(f"{abs(hgt_mean):.0f} mm {vert}")
    return ", ".join(parts) if parts else "centre"
