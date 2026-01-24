# coaching/rules.py
# Swing analysis rules engine - maps metrics to pointers, explanations, and tags

from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field


@dataclass
class CoachingPointer:
    """Structured coaching feedback with priority and explanation."""
    message: str  # Short actionable cue
    why: str  # Why this matters
    priority: int  # 1 = highest priority, 5 = lowest
    tags: List[str] = field(default_factory=list)  # Tags for drill matching
    confidence: str = "high"  # "high", "medium", "low"
    metric_name: str = ""  # Which metric triggered this
    measured_value: Optional[float] = None
    target_value: Optional[float] = None


# Coaching rules definitions with explanations
COACHING_RULES = {
    "tempo_fast": {
        "message": "Slow down your backswing",
        "why": "A rushed backswing reduces coil and power potential. Tour players average 3:1 tempo ratio.",
        "priority": 2,
        "tags": ["fast_tempo", "tempo"],
    },
    "tempo_slow": {
        "message": "Be more decisive at transition",
        "why": "An overly slow swing can lose rhythm and timing. Find a tempo that feels athletic.",
        "priority": 3,
        "tags": ["slow_tempo", "tempo"],
    },
    "head_sway": {
        "message": "Keep your head steadier",
        "why": "Excessive head movement makes it harder to return the club to the ball consistently.",
        "priority": 1,
        "tags": ["excess_sway", "sway"],
    },
    "hip_restricted": {
        "message": "Allow more hip rotation",
        "why": "Restricted hip turn limits power and can cause over-reliance on arms. Hips lead the downswing.",
        "priority": 2,
        "tags": ["restricted_hip", "hips", "rotation"],
    },
    "shoulder_limited": {
        "message": "Turn your shoulders more fully",
        "why": "A full shoulder turn creates the coil needed for power. Feel your back face the target.",
        "priority": 2,
        "tags": ["limited_turn", "shoulders", "rotation"],
    },
    "hip_slide": {
        "message": "Rotate hips, don't slide them",
        "why": "Lateral hip slide moves the low point and causes inconsistent contact. Focus on turning in a barrel.",
        "priority": 2,
        "tags": ["hip_slide", "hips"],
    },
    "wrist_flat": {
        "message": "Allow more wrist hinge",
        "why": "Proper wrist set creates lag and clubhead speed. The lead wrist should cup slightly at the top.",
        "priority": 3,
        "tags": ["cupped_wrist", "contact"],
    },
    "wrist_cupped": {
        "message": "Reduce excessive wrist cup",
        "why": "Too much wrist cup can open the clubface. Work on a flatter, more neutral position.",
        "priority": 3,
        "tags": ["cupped_wrist", "contact"],
    },
}


def analyze_with_goals(
    metrics: Dict[str, Any],
    goals: Dict[str, Any],
    detection_confidence: str = "high"
) -> Tuple[List[str], List[str]]:
    """
    Analyze swing metrics against club-specific goals.
    Returns simple (pointers, tags) tuple for backward compatibility.

    Args:
        metrics: Dict with keys like tempo_ratio, head_sway_cm, etc.
        goals: Dict with thresholds like tempo_lower, tempo_upper, etc.
        detection_confidence: Overall detection confidence from video analysis

    Returns:
        Tuple of (pointers list, tags list) for coaching feedback and drill matching.
    """
    structured = analyze_with_goals_detailed(metrics, goals, detection_confidence)

    # Extract simple lists for backward compatibility
    pointers = [p.message + f" ({p.measured_value} vs target {p.target_value})"
                if p.measured_value and p.target_value
                else p.message
                for p in structured]

    # If no issues found
    if not pointers:
        pointers = ["Swing fundamentals look solid. Keep practicing for consistency!"]

    tags = []
    for p in structured:
        tags.extend(p.tags)

    # De-duplicate tags while preserving order
    seen = set()
    unique_tags = [t for t in tags if not (t in seen or seen.add(t))]

    return pointers, unique_tags


def analyze_with_goals_detailed(
    metrics: Dict[str, Any],
    goals: Dict[str, Any],
    detection_confidence: str = "high"
) -> List[CoachingPointer]:
    """
    Analyze swing metrics with detailed structured output.

    Args:
        metrics: Dict with keys like tempo_ratio, head_sway_cm, etc.
        goals: Dict with thresholds from goals.py
        detection_confidence: "high", "medium", or "low"

    Returns:
        List of CoachingPointer objects sorted by priority
    """
    pointers: List[CoachingPointer] = []

    # Adjust confidence based on detection quality
    base_confidence = detection_confidence

    # === TEMPO ANALYSIS ===
    tempo = metrics.get("tempo_ratio")
    if tempo is not None:
        tempo_lower = goals.get("tempo_lower", 2.5)
        tempo_upper = goals.get("tempo_upper", 3.5)

        if tempo < tempo_lower:
            rule = COACHING_RULES["tempo_fast"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (tempo: {tempo:.1f}, target: {tempo_lower}-{tempo_upper})",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="tempo_ratio",
                measured_value=tempo,
                target_value=tempo_lower,
            ))
        elif tempo > tempo_upper:
            rule = COACHING_RULES["tempo_slow"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (tempo: {tempo:.1f}, target: {tempo_lower}-{tempo_upper})",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="tempo_ratio",
                measured_value=tempo,
                target_value=tempo_upper,
            ))

    # === HEAD SWAY ANALYSIS ===
    head_sway = metrics.get("head_sway_cm")
    if head_sway is not None:
        sway_max = goals.get("head_sway_max", 3.5)

        if head_sway > sway_max:
            rule = COACHING_RULES["head_sway"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (sway: {head_sway:.1f}cm, target: <{sway_max}cm)",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="head_sway_cm",
                measured_value=head_sway,
                target_value=sway_max,
            ))

    # === HIP ROTATION ANALYSIS ===
    hip_rot = metrics.get("hip_rotation_deg_top")
    if hip_rot is not None:
        hip_min = goals.get("hip_rot_min", 35)

        if hip_rot < hip_min:
            rule = COACHING_RULES["hip_restricted"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (hip turn: {hip_rot}°, target: >{hip_min}°)",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="hip_rotation_deg_top",
                measured_value=hip_rot,
                target_value=hip_min,
            ))

    # === SHOULDER ROTATION ANALYSIS ===
    shoulder_rot = metrics.get("shoulder_rotation_deg_top")
    if shoulder_rot is not None:
        shoulder_min = goals.get("shoulder_rot_min", 78)

        if shoulder_rot < shoulder_min:
            rule = COACHING_RULES["shoulder_limited"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (shoulder turn: {shoulder_rot}°, target: >{shoulder_min}°)",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="shoulder_rotation_deg_top",
                measured_value=shoulder_rot,
                target_value=shoulder_min,
            ))

    # === PELVIS SLIDE ANALYSIS ===
    pelvis_slide = metrics.get("pelvis_slide_cm")
    if pelvis_slide is not None:
        slide_max = goals.get("pelvis_slide_max", 5.0)

        if pelvis_slide > slide_max:
            rule = COACHING_RULES["hip_slide"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (slide: {pelvis_slide:.1f}cm, target: <{slide_max}cm)",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="pelvis_slide_cm",
                measured_value=pelvis_slide,
                target_value=slide_max,
            ))

    # === LEAD WRIST ANALYSIS ===
    wrist_set = metrics.get("lead_wrist_set_deg_top")
    if wrist_set is not None:
        wrist_min = goals.get("lead_wrist_set_min", 45)
        wrist_max = goals.get("lead_wrist_set_max", 90)

        if wrist_set < wrist_min:
            rule = COACHING_RULES["wrist_flat"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (wrist: {wrist_set}°, target: {wrist_min}-{wrist_max}°)",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="lead_wrist_set_deg_top",
                measured_value=wrist_set,
                target_value=wrist_min,
            ))
        elif wrist_set > wrist_max:
            rule = COACHING_RULES["wrist_cupped"]
            pointers.append(CoachingPointer(
                message=f"{rule['message']} (wrist: {wrist_set}°, target: {wrist_min}-{wrist_max}°)",
                why=rule["why"],
                priority=rule["priority"],
                tags=rule["tags"].copy(),
                confidence=base_confidence,
                metric_name="lead_wrist_set_deg_top",
                measured_value=wrist_set,
                target_value=wrist_max,
            ))

    # Sort by priority (lower number = higher priority)
    pointers.sort(key=lambda p: p.priority)

    return pointers


def get_pointer_drills(pointer: CoachingPointer, all_drills: List[Dict]) -> List[Dict]:
    """
    Get drills that match a specific pointer's tags.

    Args:
        pointer: CoachingPointer object
        all_drills: List of drill dictionaries from drills.yaml

    Returns:
        List of matching drill dictionaries
    """
    if not pointer.tags or not all_drills:
        return []

    tagset = set(pointer.tags)
    return [d for d in all_drills if tagset & set(d.get("tags", []))]
