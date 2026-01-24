# coaching/drills.py
# Drill tagging, mapping, and loading logic

from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

# Maps analyzer output tags to standardized drill tags in drills.yaml
DRILL_TAG_ALIASES = {
    # tempo issues
    "fast_tempo": "tempo",
    "slow_tempo": "tempo",
    "rushed_transition": "tempo",

    # sway / balance issues
    "excess_sway": "sway",
    "sway": "sway",
    "head_movement": "sway",
    "loss_of_posture": "balance",
    "sway_off_ball": "balance",

    # rotation / hips / shoulders
    "early_extension": "hips",
    "hip_slide": "hips",
    "hip_spin": "hips",
    "flat_shoulder": "shoulders",
    "limited_turn": "rotation",
    "over_rotation": "rotation",
    "restricted_hip": "hips",
    "shoulder_tilt": "shoulders",

    # wrists / impact / contact
    "casting": "impact",
    "cupped_wrist": "contact",
    "open_face": "contact",
    "early_release": "impact",
    "lag_loss": "impact",
    "flip": "contact",
}


def map_tags_to_drill_tags(analyzer_tags: Optional[List[str]]) -> List[str]:
    """
    Convert analyzer-generated tags to standardized drill tags.
    De-duplicates while preserving order.
    """
    if not analyzer_tags:
        return []

    mapped = [DRILL_TAG_ALIASES.get(t, t) for t in analyzer_tags]
    # De-duplicate while keeping order
    seen = set()
    return [x for x in mapped if not (x in seen or seen.add(x))]


def tag_to_drills(tags: Optional[List[str]], drills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter drills list to those matching any of the given tags.
    """
    if not tags or not drills:
        return []

    tagset = set(tags)
    return [d for d in drills if tagset & set(d.get("tags", []))]


def load_drills(drills_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Load drills from YAML file.

    Args:
        drills_path: Path to drills.yaml. Defaults to data/drills.yaml

    Returns:
        List of drill dictionaries, or empty list on error.
    """
    if drills_path is None:
        # Default path relative to project root
        drills_path = Path(__file__).parent.parent / "data" / "drills.yaml"

    try:
        if not drills_path.exists():
            return []
        content = drills_path.read_text(encoding="utf-8")
        drills = yaml.safe_load(content)
        return drills if isinstance(drills, list) else []
    except Exception:
        return []
