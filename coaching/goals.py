# coaching/goals.py
# Club-specific goal presets and thresholds for swing analysis

DEFAULT_GOALS = {
    "tempo_lower": 2.5,
    "tempo_upper": 3.5,
    "head_sway_max": 3.5,
    "hip_rot_min": 35,
    "shoulder_rot_min": 78,
    "pelvis_slide_max": 5.0,
    "lead_wrist_set_min": 45,
    "lead_wrist_set_max": 90,
}

# Club-specific goals: longer clubs allow more rotation and sway,
# shorter clubs demand tighter control and compact swings.
CLUB_GOALS = {
    "Driver": {
        "tempo_lower": 2.9,
        "tempo_upper": 3.6,
        "head_sway_max": 4.0,
        "hip_rot_min": 40,
        "shoulder_rot_min": 85,
        "pelvis_slide_max": 5.5,
        "lead_wrist_set_min": 50,
        "lead_wrist_set_max": 95,
    },
    "3W": {
        "tempo_lower": 2.8,
        "tempo_upper": 3.4,
        "head_sway_max": 3.5,
        "hip_rot_min": 38,
        "shoulder_rot_min": 82,
        "pelvis_slide_max": 5.0,
        "lead_wrist_set_min": 48,
        "lead_wrist_set_max": 90,
    },
    "Hybrid": {
        "tempo_lower": 2.7,
        "tempo_upper": 3.3,
        "head_sway_max": 3.2,
        "hip_rot_min": 36,
        "shoulder_rot_min": 80,
        "pelvis_slide_max": 4.5,
        "lead_wrist_set_min": 45,
        "lead_wrist_set_max": 88,
    },
    "Long Iron": {
        "tempo_lower": 2.7,
        "tempo_upper": 3.2,
        "head_sway_max": 3.0,
        "hip_rot_min": 36,
        "shoulder_rot_min": 80,
        "pelvis_slide_max": 4.5,
        "lead_wrist_set_min": 45,
        "lead_wrist_set_max": 85,
    },
    "Mid Iron": {
        "tempo_lower": 2.6,
        "tempo_upper": 3.1,
        "head_sway_max": 2.8,
        "hip_rot_min": 35,
        "shoulder_rot_min": 78,
        "pelvis_slide_max": 4.0,
        "lead_wrist_set_min": 45,
        "lead_wrist_set_max": 82,
    },
    "Short Iron": {
        "tempo_lower": 2.6,
        "tempo_upper": 3.0,
        "head_sway_max": 2.6,
        "hip_rot_min": 34,
        "shoulder_rot_min": 76,
        "pelvis_slide_max": 3.5,
        "lead_wrist_set_min": 45,
        "lead_wrist_set_max": 80,
    },
    "Wedge": {
        "tempo_lower": 2.5,
        "tempo_upper": 3.0,
        "head_sway_max": 2.5,
        "hip_rot_min": 32,
        "shoulder_rot_min": 74,
        "pelvis_slide_max": 3.0,
        "lead_wrist_set_min": 40,
        "lead_wrist_set_max": 78,
    },
}


def get_goals_for_club(club: str) -> dict:
    """Return merged goals for a specific club, falling back to defaults."""
    goals = DEFAULT_GOALS.copy()
    goals.update(CLUB_GOALS.get(club, {}))
    return goals
