# integrations/rounds_csv.py
# Tolerant importer for hole-by-hole round exports from scoring apps
# (Golfity "holes" export, Golf Pad comprehensive export, or a hand-made
# spreadsheet). One row per hole; rows are grouped into rounds by
# (date, course).

from __future__ import annotations

import csv
import io
import re
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from data.rounds import HoleResult, Round


ROUND_ALIASES: Dict[str, List[str]] = {
    "date": ["date", "rounddate", "playedon", "played", "datetime", "startdate", "day"],
    "course": ["course", "coursename", "club", "venue"],
    "tees": ["tees", "tee", "teebox", "teename", "teecolor", "teecolour"],
    "hole": ["hole", "holenumber", "holeno", "holenr", "#"],
    "par": ["par", "holepar"],
    "score": ["score", "strokes", "gross", "grossscore", "shots", "holescore", "total"],
    "putts": ["putts", "putt", "numputts", "puttcount"],
    "fir": ["fir", "fairway", "fairwayhit", "fairwaysinregulation", "fairwayhitmissed", "hitfairway", "fw"],
    "gir": ["gir", "green", "greenhit", "greeninregulation", "greensinregulation", "hitgreen"],
    "penalties": ["penalties", "penalty", "penaltystrokes", "penaltyshots", "numpenalties", "pen"],
    "sand": ["sand", "bunker", "sandshots", "bunkershots", "insand"],
    "up_and_down": ["upanddown", "updown", "scramble", "scrambling", "saved", "chipin"],
}
_ALIAS_INDEX = sorted(
    ((alias, canon) for canon, aliases in ROUND_ALIASES.items() for alias in aliases),
    key=lambda t: -len(t[0]),
)
_EXACT = {a: c for a, c in _ALIAS_INDEX}

TRUE_WORDS = {"1", "true", "yes", "y", "hit", "x", "✓", "✔", "t", "on", "fairway", "green"}
FALSE_WORDS = {"0", "false", "no", "n", "miss", "missed", "f", "off", "left", "right", "long", "short", "rough", "bunker", "sand"}


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9#]", "", str(s).lower())


def map_round_columns(headers: List[str]) -> Tuple[Dict[str, str], List[str]]:
    mapping: Dict[str, str] = {}
    unmapped: List[str] = []
    taken = set()
    for h in headers:
        if h is None or str(h).strip() == "":
            continue
        key = _norm(h)
        canon = _EXACT.get(key)
        if canon is None:
            for alias, c in _ALIAS_INDEX:
                if len(alias) >= 4 and key.startswith(alias):
                    canon = c
                    break
        if canon is None or canon in taken:
            unmapped.append(str(h))
            continue
        mapping[str(h)] = canon
        taken.add(canon)
    return mapping, unmapped


def _to_bool(v) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("", "-", "n/a", "na", "nan", "none", "null"):
        return None
    if s in TRUE_WORDS:
        return True
    if s in FALSE_WORDS:
        return False
    try:
        return float(s) > 0
    except ValueError:
        return None


def _to_int(v, default: Optional[int] = None) -> Optional[int]:
    if v is None:
        return default
    s = str(v).strip()
    if s == "" or s.lower() in ("-", "n/a", "na", "nan", "none"):
        return default
    try:
        return int(round(float(s.replace(",", "."))))
    except ValueError:
        return default


def _sniff(text: str) -> str:
    head = "\n".join(text.splitlines()[:10])
    try:
        return csv.Sniffer().sniff(head, delimiters=",;\t").delimiter
    except Exception:
        return ","


def parse_rounds_csv(source: Union[str, bytes], source_name: str = "rounds.csv") -> Tuple[List[Round], List[str]]:
    """
    Parse a hole-by-hole CSV into Round objects.

    Returns (rounds, warnings). Rows are grouped by (date, course).
    """
    warnings: List[str] = []
    text = source.decode("utf-8-sig", errors="replace") if isinstance(source, bytes) else source
    if not text.strip():
        return [], ["File is empty."]

    delim = _sniff(text)
    try:
        raw = pd.read_csv(io.StringIO(text), sep=delim, dtype=str, keep_default_na=False, engine="python", on_bad_lines="skip")
    except Exception as exc:
        return [], [f"CSV read failed: {exc}"]

    mapping, unmapped = map_round_columns(list(raw.columns))
    needed = {"hole", "score"}
    if not needed <= set(mapping.values()):
        return [], ["Need at least 'hole' and 'score' columns (one row per hole). Found: " + ", ".join(raw.columns[:10])]
    if unmapped:
        warnings.append("Ignored columns: " + ", ".join(unmapped[:10]))

    df = pd.DataFrame({canon: raw[orig] for orig, canon in mapping.items()})
    if "date" not in df.columns:
        df["date"] = ""
        warnings.append("No date column - all holes treated as one round dated today.")
    if "course" not in df.columns:
        df["course"] = ""

    parsed_dates = pd.to_datetime(df["date"].astype(str).str.strip(), errors="coerce")
    if parsed_dates.isna().mean() > 0.5:
        alt = pd.to_datetime(df["date"].astype(str).str.strip(), errors="coerce", dayfirst=True)
        if alt.notna().sum() > parsed_dates.notna().sum():
            parsed_dates = alt
    df["_date"] = parsed_dates.dt.strftime("%Y-%m-%d").fillna(pd.Timestamp.today().strftime("%Y-%m-%d"))

    rounds: List[Round] = []
    for (date_str, course), group in df.groupby(["_date", "course"], sort=True):
        holes: List[HoleResult] = []
        for _, row in group.iterrows():
            hole = _to_int(row.get("hole"))
            score = _to_int(row.get("score"))
            if hole is None or score is None or score <= 0:
                continue
            holes.append(HoleResult(
                hole=hole,
                par=_to_int(row.get("par"), 4) or 4,
                score=score,
                putts=_to_int(row.get("putts")),
                fir=_to_bool(row.get("fir")),
                gir=_to_bool(row.get("gir")),
                penalties=_to_int(row.get("penalties"), 0) or 0,
                sand=_to_bool(row.get("sand")),
                up_and_down=_to_bool(row.get("up_and_down")),
            ))
        if not holes:
            continue
        holes.sort(key=lambda h: h.hole)
        tees = str(group["tees"].iloc[0]).strip() if "tees" in group.columns else ""
        rounds.append(Round.create(
            date=date_str,
            course=str(course).strip() or "Unknown course",
            tees=tees,
            holes=holes,
            source=source_name,
        ))

    if not rounds:
        warnings.append("No usable hole rows found.")
    return rounds, warnings
