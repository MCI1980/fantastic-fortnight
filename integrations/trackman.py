# integrations/trackman.py
# Tolerant importer for TrackMan Performance Studio (TPS) CSV exports.
#
# TPS export path: Shot Analysis -> View Selector -> Table View ->
# File Options -> "Trackman CSV". Formats vary by TPS version, locale and
# unit settings, so this parser:
#   - sniffs the delimiter (comma / semicolon / tab)
#   - finds the header row even if there is a preamble
#   - accepts a units row under the header, or units in the header text
#   - converts km/h, m/s, metres and feet to mph / yards
#   - understands "5.2 R" / "L 3.1" style side values
#   - drops summary rows (Average, Std Dev, Consistency ...)
#   - normalizes club names ("7i", "Iron 7", "7-iron" -> "7 Iron")

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .base import NUMERIC_FIELDS, REQUIRED_ANY, SHOT_FIELDS


# ---------------------------------------------------------------------------
# Column aliases (normalized: lowercase, alphanumerics only)
# ---------------------------------------------------------------------------

COLUMN_ALIASES: Dict[str, List[str]] = {
    "shot_number": ["shot", "shotnumber", "shotno", "shotnr", "no", "nr", "index", "id"],
    "date": ["date", "datetime", "timestamp", "shotdate", "time_stamp", "createdat", "shottime"],
    "time": ["time", "timeofday"],
    "player": ["player", "playername", "name", "golfer"],
    "club": ["club", "clubname", "clubtype", "clubused"],
    "ball_type": ["balltype", "ball", "ballmodel"],
    "tags": ["tags", "tag", "note", "notes", "comment", "comments"],

    "club_speed_mph": ["clubspeed", "clubheadspeed", "chs", "clubspd"],
    "attack_angle_deg": ["attackangle", "attackang", "angleofattack", "aoa", "attack"],
    "club_path_deg": ["clubpath", "path"],
    "face_angle_deg": ["faceangle", "faceang", "face", "clubface"],
    "face_to_path_deg": ["facetopath", "facepath", "ftp", "face2path"],
    "dynamic_loft_deg": ["dynamicloft", "dynloft", "dloft"],
    "spin_loft_deg": ["spinloft"],
    "swing_plane_deg": ["swingplane", "plane"],
    "swing_direction_deg": ["swingdirection", "swingdir"],
    "low_point_in": ["lowpoint", "lowpointdistance"],
    "impact_height_mm": ["impactheight", "impactvertical"],
    "impact_offset_mm": ["impactoffset", "impacthorizontal", "impactheeltoe"],

    "ball_speed_mph": ["ballspeed", "ballspd", "bs"],
    "smash_factor": ["smashfactor", "smash", "efficiency"],
    "launch_angle_deg": ["launchangle", "launchang", "verticallaunch", "vla", "launch"],
    "launch_direction_deg": ["launchdirection", "launchdir", "horizontallaunch", "hla"],
    "spin_rate_rpm": ["spinrate", "totalspin", "spin", "backspin"],
    "spin_axis_deg": ["spinaxis", "axis", "spintilt"],

    "height_yds": ["height", "maxheight", "apex", "peakheight", "apexheight", "maxheightheight"],
    "carry_yds": ["carry", "carrydistance", "carrydist", "carryyds", "carryflatlength", "carryflat"],
    "total_yds": ["total", "totaldistance", "totaldist", "totalyds", "esttotalflatlength", "totalflatlength", "esttotalflat", "esttotal", "estimatedtotal"],
    "side_yds": ["side", "carryside", "sidecarry", "offline", "lateral", "carryoffline", "sidecarrydist", "carryflatside"],
    "side_total_yds": ["sidetotal", "totalside", "offlinetotal", "totaloffline", "sidetot", "esttotalflatside", "totalflatside", "esttotalside"],
    "landing_angle_deg": ["landangle", "landingangle", "descentangle", "landang", "landing", "carryflatlandangle", "carryflatlandingangle"],
    "hang_time_s": ["hangtime", "flighttime", "airtime", "carryflattime"],
    "curve_yds": ["curve", "curvature"],
    "use_in_stat": ["useinstat", "includeinstats", "usedinstats"],
}

# Normalized header keys that must never be mapped (TPS bookkeeping and
# columns that would otherwise prefix-match a measurement).
IGNORE_KEYS = {
    "tmdno", "tmdfilename", "email", "condition", "dynamiclie",
    "maxheightdist", "maxheightside",
    "lastdatapointlength", "lastdatapointside", "lastdatapointheight", "lastdatapointtime",
    "carryflatballspeed", "spinratetype",
    "ballspeeddiff", "smashindex", "spinratediff", "spinindex", "gyroangle", "dplanetilt",
    "swingradius", "lowpointheight", "lowpointside",
}

# Longest aliases first so prefix matching prefers the most specific alias.
_ALIAS_INDEX: List[Tuple[str, str]] = sorted(
    ((alias, canon) for canon, aliases in COLUMN_ALIASES.items() for alias in aliases),
    key=lambda t: -len(t[0]),
)
_EXACT_ALIAS: Dict[str, str] = {alias: canon for alias, canon in _ALIAS_INDEX}

UNIT_ALIASES = {
    "mph": "mph", "mi/h": "mph", "mile/h": "mph",
    "kmh": "kmh", "km/h": "kmh", "kph": "kmh",
    "m/s": "ms", "ms": "ms", "mps": "ms",
    "yds": "yds", "yd": "yds", "yards": "yds", "yard": "yds", "y": "yds",
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "ft": "ft", "feet": "ft", "foot": "ft",
    "deg": "deg", "°": "deg", "degrees": "deg", "degree": "deg", "º": "deg",
    "rpm": "rpm", "s": "s", "sec": "s", "seconds": "s",
    "in": "in", "inch": "in", "inches": "in", "mm": "mm", "cm": "cm",
    "-": "", "": "",
}
SPEED_TO_MPH = {"mph": 1.0, "kmh": 0.621371, "ms": 2.236936}
DIST_TO_YDS = {"yds": 1.0, "m": 1.093613, "ft": 1.0 / 3.0}
SMALL_TO_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4}
SPEED_FIELDS = {"club_speed_mph", "ball_speed_mph"}
DIST_FIELDS = {"carry_yds", "total_yds", "side_yds", "side_total_yds", "height_yds", "curve_yds"}
MM_FIELDS = {"impact_height_mm", "impact_offset_mm"}

SUMMARY_ROW_RE = re.compile(
    r"^\s*(average|avg|mean|median|std|st\.?\s*dev|standard|consist|min|max|total\s*avg|summary|count)\b",
    re.I,
)
NUMBER_LR_RE = re.compile(r"^\s*([LR])?\s*([-+]?\d+(?:[.,]\d+)?)\s*([LR])?\s*$", re.I)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    df: pd.DataFrame
    source_name: str = ""
    delimiter: str = ","
    column_map: Dict[str, str] = field(default_factory=dict)   # original -> canonical
    units: Dict[str, str] = field(default_factory=dict)        # canonical -> detected unit
    unmapped_columns: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    n_rows_raw: int = 0

    @property
    def n_shots(self) -> int:
        return int(len(self.df))

    @property
    def ok(self) -> bool:
        return self.n_shots > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _split_unit(header: str) -> Tuple[str, Optional[str]]:
    """'Carry (yds)' -> ('Carry', 'yds'); 'Club Speed [km/h]' -> ('Club Speed', 'kmh')."""
    h = str(header).strip()
    m = re.match(r"^(.*?)\s*[\(\[]\s*([^\)\]]+?)\s*[\)\]]\s*$", h)
    if m:
        unit = UNIT_ALIASES.get(m.group(2).strip().lower())
        return m.group(1).strip(), unit
    # Trailing unit without brackets, e.g. "Carry yds"
    m = re.match(r"^(.*?)[\s_]+(mph|km/h|kmh|m/s|yds|yards|m|ft|deg|rpm)$", h, re.I)
    if m:
        return m.group(1).strip(), UNIT_ALIASES.get(m.group(2).lower())
    return h, None


def map_columns(headers: List[str]) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
    """Map raw headers to canonical names. Returns (mapping, units, unmapped)."""
    mapping: Dict[str, str] = {}
    units: Dict[str, str] = {}
    unmapped: List[str] = []
    taken = set()

    # Measured columns first; "(Sim)" duplicates only fill slots still free.
    ordered = sorted(
        [h for h in headers if h is not None and str(h).strip() != ""],
        key=lambda h: 1 if "(sim)" in str(h).lower() else 0,
    )
    for header in ordered:
        name, unit = _split_unit(header)
        key = _norm(name)
        if key in IGNORE_KEYS or _norm(header) in IGNORE_KEYS:
            unmapped.append(str(header))
            continue
        canon = _EXACT_ALIAS.get(key)
        if canon is None:
            for alias, c in _ALIAS_INDEX:
                if len(alias) >= 4 and key.startswith(alias):
                    canon = c
                    break
        if canon is None or canon in taken:
            unmapped.append(str(header))
            continue
        mapping[str(header)] = canon
        taken.add(canon)
        if unit:
            units[canon] = unit
    return mapping, units, unmapped


def parse_number(value) -> float:
    """Parse '5.2', '5,2', '5.2 R', 'L 3.1', '-' -> float (NaN when not a number)."""
    if value is None:
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    s = str(value).strip()
    if s == "" or s in ("-", "--", "n/a", "N/A", "NaN", "nan"):
        return np.nan
    m = NUMBER_LR_RE.match(s)
    if not m:
        # Strip stray unit text like "142.3 mph"
        m2 = re.match(r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*[a-zA-Z/°º]*\s*$", s)
        if not m2:
            return np.nan
        return float(m2.group(1).replace(",", "."))
    side = (m.group(1) or m.group(3) or "").upper()
    val = float(m.group(2).replace(",", "."))
    if side == "L":
        return -abs(val)
    if side == "R":
        return abs(val)
    return val


def normalize_club(raw) -> str:
    """Normalize the many ways a club can be written into a canonical label."""
    if raw is None:
        return "Unknown"
    s = str(raw).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return "Unknown"
    s = s.lower().replace("°", " deg").replace("º", " deg").replace("-", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()

    if re.fullmatch(r"(driver|dr|d|1w|1 w|1 wood|drv)", s):
        return "Driver"

    m = re.fullmatch(r"(\d{1,2}) ?(w|wd|wood|fw|fairway|fairway wood)", s) or \
        re.fullmatch(r"(?:wood|w|fw|fairway) ?(\d{1,2})", s)
    if m:
        n = int(m.group(1))
        if n == 1:
            return "Driver"
        if n <= 11:
            return f"{n} Wood"

    m = re.fullmatch(r"(\d) ?(h|hy|hyb|hybrid|rescue|u|ut|utility|di)", s) or \
        re.fullmatch(r"(?:hybrid|h|rescue|utility|u) ?(\d)", s)
    if m:
        return f"{m.group(1)} Hybrid"
    if s in ("hybrid", "rescue", "utility"):
        return "Hybrid"

    m = re.fullmatch(r"(\d) ?(i|iron|ir)", s) or re.fullmatch(r"(?:iron|i|ir) ?(\d)", s)
    if m:
        return f"{m.group(1)} Iron"

    if re.fullmatch(r"(pw|p|pitching wedge|pitching|pitch|pitch wedge|p wedge|wedge p)", s):
        return "PW"
    if re.fullmatch(r"(gw|g|gap wedge|gap|aw|a|approach wedge|approach|uw|u wedge|utility wedge|g wedge|a wedge)", s):
        return "GW"
    if re.fullmatch(r"(sw|sand wedge|sand|s wedge|s)", s):
        return "SW"
    if re.fullmatch(r"(lw|lob wedge|lob|l wedge|l)", s):
        return "LW"

    m = re.fullmatch(r"(\d{2}) ?(deg|degree|degrees)? ?(wedge|w)?", s)
    if m and 44 <= int(m.group(1)) <= 64:
        return f"{int(m.group(1))}° Wedge"

    return str(raw).strip().title()


def club_sort_key(club: str) -> Tuple[int, float, str]:
    """Sort clubs longest to shortest: Driver, woods, hybrids, irons, wedges."""
    c = str(club)
    if c == "Driver":
        return (0, 0, c)
    m = re.fullmatch(r"(\d+) Wood", c)
    if m:
        return (1, int(m.group(1)), c)
    m = re.fullmatch(r"(\d+) Hybrid", c)
    if m:
        return (2, int(m.group(1)), c)
    if c == "Hybrid":
        return (2, 9, c)
    m = re.fullmatch(r"(\d+) Iron", c)
    if m:
        return (3, int(m.group(1)), c)
    wedge_loft = {"PW": 45, "GW": 50, "SW": 56, "LW": 60}
    if c in wedge_loft:
        return (4, wedge_loft[c], c)
    m = re.fullmatch(r"(\d+)° Wedge", c)
    if m:
        return (4, int(m.group(1)) + 0.5, c)
    return (9, 0, c)


def club_category(club: str) -> str:
    c = str(club)
    if c == "Driver":
        return "Driver"
    if c.endswith("Wood"):
        return "Wood"
    if "Hybrid" in c:
        return "Hybrid"
    m = re.fullmatch(r"(\d+) Iron", c)
    if m:
        n = int(m.group(1))
        if n <= 5:
            return "Long Iron"
        if n <= 7:
            return "Mid Iron"
        return "Short Iron"
    if c in ("PW", "GW", "SW", "LW") or c.endswith("Wedge"):
        return "Wedge"
    return "Other"


def _sniff_delimiter(text: str) -> str:
    head = "\n".join(text.splitlines()[:20])
    try:
        dialect = csv.Sniffer().sniff(head, delimiters=",;\t")
        return dialect.delimiter
    except Exception:
        counts = {d: head.count(d) for d in (",", ";", "\t")}
        return max(counts, key=counts.get) if max(counts.values()) > 0 else ","


def _find_header_row(lines: List[str], delimiter: str) -> Tuple[int, Dict[str, str], Dict[str, str], List[str]]:
    """Return index of the header line plus its column mapping."""
    best = (-1, {}, {}, [])
    for i, line in enumerate(lines[:50]):
        cells = next(csv.reader([line], delimiter=delimiter), [])
        if len(cells) < 3:
            continue
        mapping, units, unmapped = map_columns(cells)
        # Require at least 3 recognised measurement columns
        measured = [c for c in mapping.values() if c in NUMERIC_FIELDS]
        if len(measured) >= 3:
            return i, mapping, units, unmapped
        if len(mapping) > len(best[1]):
            best = (i, mapping, units, unmapped)
    return best


def _unit_token(cell) -> str:
    """'[mph]' / '(yds)' / ' deg ' -> 'mph' / 'yds' / 'deg'; '[]' -> ''."""
    if cell is None:
        return ""
    return re.sub(r"[\[\]\(\)\s]", "", str(cell)).lower()


def _is_units_row(cells: List[str]) -> bool:
    tokens = [_unit_token(c) for c in cells]
    non_empty = [t for t in tokens if t not in ("", "-")]
    if not non_empty:
        return False
    unit_like = sum(1 for t in non_empty if t in UNIT_ALIASES)
    numeric = sum(1 for t in non_empty if not np.isnan(parse_number(t)))
    return numeric == 0 and unit_like >= max(1, len(non_empty) // 2)


def _decode(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        return data
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_dates(date_col: Optional[pd.Series], time_col: Optional[pd.Series]) -> pd.Series:
    if date_col is None:
        return pd.Series([pd.NaT] * (len(time_col) if time_col is not None else 0))
    text = date_col.astype(str).str.strip()
    if time_col is not None:
        t = time_col.astype(str).str.strip()
        has_time = text.str.contains(r"\d{1,2}:\d{2}")
        text = text.where(has_time, text + " " + t)
    parsed = _to_datetime(text)
    if parsed.isna().mean() > 0.5:
        alt = _to_datetime(text, dayfirst=True)
        if alt.notna().sum() > parsed.notna().sum():
            parsed = alt
    return parsed


def _to_datetime(text: pd.Series, dayfirst: bool = False) -> pd.Series:
    """Parse mixed date formats without pandas' per-element inference warning."""
    try:
        return pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=dayfirst)
    except (TypeError, ValueError):  # pandas < 2.0
        return pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_trackman_csv(source: Union[str, bytes, Path], source_name: Optional[str] = None) -> ParseResult:
    """
    Parse a TrackMan CSV export into a canonical shot DataFrame.

    Args:
        source: file path, raw bytes, or CSV text
        source_name: display name for the source (defaults to file name)
    """
    if isinstance(source, Path) or (isinstance(source, str) and len(source) < 4096 and "\n" not in source and Path(source).exists()):
        path = Path(source)
        raw = path.read_bytes()
        source_name = source_name or path.name
    else:
        raw = source
        source_name = source_name or "upload.csv"

    text = _decode(raw)
    result = ParseResult(df=pd.DataFrame(), source_name=source_name)

    lines = [ln for ln in text.splitlines()]
    if not any(ln.strip() for ln in lines):
        result.warnings.append("File is empty.")
        return result

    delimiter = _sniff_delimiter(text)
    result.delimiter = delimiter

    header_idx, mapping, header_units, unmapped = _find_header_row(lines, delimiter)
    if header_idx < 0 or not mapping:
        result.warnings.append("Could not find a header row with recognisable TrackMan columns.")
        return result

    body = "\n".join(lines[header_idx:])
    try:
        raw_df = pd.read_csv(
            io.StringIO(body),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            engine="python",
            on_bad_lines="skip",
            skip_blank_lines=True,
        )
    except Exception as exc:  # pragma: no cover - defensive
        result.warnings.append(f"CSV read failed: {exc}")
        return result

    result.n_rows_raw = int(len(raw_df))
    result.column_map = mapping
    result.unmapped_columns = unmapped
    units = dict(header_units)

    # Units row directly under the header?
    if len(raw_df) > 0 and _is_units_row(list(raw_df.iloc[0].values)):
        for orig, canon in mapping.items():
            u = UNIT_ALIASES.get(_unit_token(raw_df.iloc[0][orig]))
            if u:
                units[canon] = u
        raw_df = raw_df.iloc[1:].reset_index(drop=True)

    # Drop summary rows (Average / Std Dev / Consistency ...)
    first_cols = raw_df.columns[: min(3, len(raw_df.columns))]
    is_summary = pd.Series(False, index=raw_df.index)
    for col in first_cols:
        is_summary |= raw_df[col].astype(str).str.match(SUMMARY_ROW_RE)
    raw_df = raw_df[~is_summary].reset_index(drop=True)

    # Build canonical frame
    out = pd.DataFrame(index=raw_df.index)
    date_series = None
    time_series = None
    for orig, canon in mapping.items():
        col = raw_df[orig]
        if canon == "date":
            date_series = col
        elif canon == "time":
            time_series = col
        elif canon in NUMERIC_FIELDS:
            vals = col.map(parse_number).astype(float)
            unit = units.get(canon)
            if canon in SPEED_FIELDS and unit in SPEED_TO_MPH:
                vals = vals * SPEED_TO_MPH[unit]
            elif canon in DIST_FIELDS and unit in DIST_TO_YDS:
                vals = vals * DIST_TO_YDS[unit]
            elif canon in MM_FIELDS and unit in SMALL_TO_MM:
                vals = vals * SMALL_TO_MM[unit]
            out[canon] = vals
        else:
            out[canon] = col.astype(str).str.strip()

    out["date"] = _parse_dates(date_series, time_series) if (date_series is not None or time_series is not None) else pd.NaT

    # Keep only rows that look like real shots
    present_required = [c for c in REQUIRED_ANY if c in out.columns]
    if not present_required:
        result.warnings.append("No carry / ball speed / total column found - nothing to import.")
        result.units = units
        return result
    keep = out[present_required].notna().any(axis=1)
    out = out[keep].reset_index(drop=True)

    # Shots the golfer excluded from stats in TPS ("Use In Stat" = FALSE)
    if "use_in_stat" in out.columns:
        excluded = out["use_in_stat"].astype(str).str.strip().str.upper().isin(("FALSE", "0", "NO"))
        if excluded.any():
            result.warnings.append(f"Skipped {int(excluded.sum())} shot(s) marked 'Use In Stat = FALSE' in TPS.")
            out = out[~excluded].reset_index(drop=True)
        out = out.drop(columns=["use_in_stat"])

    # Clubs
    if "club" in out.columns:
        out["raw_club"] = out["club"]
        out["club"] = out["club"].map(normalize_club)
    else:
        out["raw_club"] = ""
        out["club"] = "Unknown"
        result.warnings.append("No club column found - all shots imported as 'Unknown'. Tag clubs in TPS before exporting.")
    out["club_category"] = out["club"].map(club_category)

    # Derived values
    if "smash_factor" not in out.columns and {"ball_speed_mph", "club_speed_mph"} <= set(out.columns):
        out["smash_factor"] = out["ball_speed_mph"] / out["club_speed_mph"].replace(0, np.nan)
    if "face_to_path_deg" not in out.columns and {"face_angle_deg", "club_path_deg"} <= set(out.columns):
        out["face_to_path_deg"] = out["face_angle_deg"] - out["club_path_deg"]
    if "spin_loft_deg" not in out.columns and {"dynamic_loft_deg", "attack_angle_deg"} <= set(out.columns):
        out["spin_loft_deg"] = out["dynamic_loft_deg"] - out["attack_angle_deg"]
    if "shot_number" not in out.columns:
        out["shot_number"] = np.arange(1, len(out) + 1, dtype=float)

    # Sanity filters: obvious radar glitches
    if "smash_factor" in out.columns:
        bad = out["smash_factor"] > 1.62
        if bad.any():
            result.warnings.append(f"Dropped {int(bad.sum())} shot(s) with impossible smash factor (>1.62).")
            out = out[~bad].reset_index(drop=True)
    if "carry_yds" in out.columns:
        bad = out["carry_yds"] <= 0
        if bad.any():
            result.warnings.append(f"Dropped {int(bad.sum())} shot(s) with zero carry.")
            out = out[~bad].reset_index(drop=True)

    # Column order: canonical order first
    ordered = [c for c in SHOT_FIELDS if c in out.columns] + [c for c in out.columns if c not in SHOT_FIELDS]
    out = out[ordered]

    result.df = out
    result.units = units
    if unmapped:
        result.warnings.append("Ignored columns: " + ", ".join(unmapped[:12]) + (" ..." if len(unmapped) > 12 else ""))
    return result


def content_hash(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:12]


def shot_hash(row: Dict) -> str:
    """Stable per-shot hash so overlapping exports don't double-count."""
    parts = []
    for key in ("date", "club", "ball_speed_mph", "club_speed_mph", "carry_yds", "total_yds", "launch_angle_deg", "spin_rate_rpm", "side_yds"):
        v = row.get(key)
        if isinstance(v, float):
            parts.append(f"{v:.1f}" if not np.isnan(v) else "")
        elif isinstance(v, (pd.Timestamp, datetime)):
            parts.append(v.strftime("%Y-%m-%d %H:%M:%S") if not pd.isna(v) else "")
        else:
            parts.append("" if v is None else str(v))
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
