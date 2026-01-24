# coaching/rules.py
# Swing analysis rules engine - maps metrics to pointers and tags

from typing import Dict, List, Tuple, Any


def analyze_with_goals(metrics: Dict[str, Any], goals: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Analyze swing metrics against club-specific goals.

    Args:
        metrics: Dict with keys like tempo_ratio, head_sway_cm, hip_rotation_deg_top, etc.
        goals: Dict with thresholds like tempo_lower, tempo_upper, head_sway_max, etc.

    Returns:
        Tuple of (pointers list, tags list) for coaching feedback and drill matching.
    """
    pointers = []
    tags = []

    # Tempo analysis
    tempo = metrics.get("tempo_ratio")
    if tempo is not None:
        tempo_lower = goals.get("tempo_lower", 2.5)
        tempo_upper = goals.get("tempo_upper", 3.5)

        if tempo < tempo_lower:
            pointers.append(f"Tempo is quick ({tempo:.1f}). Try a slower backswing to build power.")
            tags.append("fast_tempo")
        elif tempo > tempo_upper:
            pointers.append(f"Tempo is slow ({tempo:.1f}). A more decisive transition may help.")
            tags.append("slow_tempo")

    # Head sway analysis
    head_sway = metrics.get("head_sway_cm")
    if head_sway is not None:
        sway_max = goals.get("head_sway_max", 3.5)

        if head_sway > sway_max:
            pointers.append(f"Head sway is {head_sway:.1f} cm (target: <{sway_max}). Keep head steadier over the ball.")
            tags.append("excess_sway")

    # Hip rotation analysis
    hip_rot = metrics.get("hip_rotation_deg_top")
    if hip_rot is not None:
        hip_min = goals.get("hip_rot_min", 35)

        if hip_rot < hip_min:
            pointers.append(f"Hip turn is limited ({hip_rot}°, target: >{hip_min}°). Allow hips to rotate more freely.")
            tags.append("restricted_hip")

    # Shoulder rotation analysis
    shoulder_rot = metrics.get("shoulder_rotation_deg_top")
    if shoulder_rot is not None:
        shoulder_min = goals.get("shoulder_rot_min", 78)

        if shoulder_rot < shoulder_min:
            pointers.append(f"Shoulder turn is {shoulder_rot}° (target: >{shoulder_min}°). Try to turn more for power.")
            tags.append("limited_turn")

    # Pelvis slide analysis (if available)
    pelvis_slide = metrics.get("pelvis_slide_cm")
    if pelvis_slide is not None:
        slide_max = goals.get("pelvis_slide_max", 5.0)

        if pelvis_slide > slide_max:
            pointers.append(f"Pelvis slide is {pelvis_slide:.1f} cm. Focus on rotation over lateral movement.")
            tags.append("hip_slide")

    # Lead wrist analysis (if available)
    wrist_set = metrics.get("lead_wrist_set_deg_top")
    if wrist_set is not None:
        wrist_min = goals.get("lead_wrist_set_min", 45)
        wrist_max = goals.get("lead_wrist_set_max", 90)

        if wrist_set < wrist_min:
            pointers.append(f"Lead wrist is too flat ({wrist_set}°). Allow more wrist hinge.")
            tags.append("cupped_wrist")
        elif wrist_set > wrist_max:
            pointers.append(f"Lead wrist is over-cupped ({wrist_set}°). Moderate the wrist set.")
            tags.append("cupped_wrist")

    # Default feedback if everything looks good
    if not pointers:
        pointers.append("Swing fundamentals look solid. Keep practicing for consistency!")

    return pointers, tags
