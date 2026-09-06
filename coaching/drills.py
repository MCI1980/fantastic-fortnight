# coaching/drills.py
# Drill loading and tag matching.

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Older tag names -> current drill tags (kept for compatibility)
DRILL_TAG_ALIASES = {
    "slice": "face_control",
    "hook": "face_control",
    "over_the_top": "path",
    "open_face": "face_control",
    "closed_face": "face_control",
    "contact": "strike",
    "impact": "low_point",
    "fat": "low_point",
    "thin": "low_point",
    "tempo": "tempo",
    "gapping": "distance_control",
}


def map_tags_to_drill_tags(tags: Optional[List[str]]) -> List[str]:
    """Expand rule tags with their aliases, de-duplicated and ordered."""
    if not tags:
        return []
    out: List[str] = []
    for t in tags:
        for candidate in (t, DRILL_TAG_ALIASES.get(t)):
            if candidate and candidate not in out:
                out.append(candidate)
    return out


def tag_to_drills(tags: Optional[List[str]], drills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not tags or not drills:
        return []
    tagset = set(tags)
    return [d for d in drills if tagset & set(d.get("tags", []))]


def load_drills(drills_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    if drills_path is None:
        drills_path = Path(__file__).parent.parent / "data" / "drills.yaml"
    try:
        if not drills_path.exists():
            return []
        drills = yaml.safe_load(drills_path.read_text(encoding="utf-8"))
        return drills if isinstance(drills, list) else []
    except Exception:
        return []
