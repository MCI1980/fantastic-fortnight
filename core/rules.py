
def analyze_with_goals(m, goals):
    return ["Example pointer"], ["example_tag"]
DEFAULT_GOALS = {}
CLUB_GOALS = {
    "Driver":      {"tempo_lower": 2.9, "tempo_upper": 3.6, "head_sway_max": 4.0, "hip_rot_min": 40, "shoulder_rot_min": 85},
    "3W":          {"tempo_lower": 2.8, "tempo_upper": 3.4, "head_sway_max": 3.5, "hip_rot_min": 38, "shoulder_rot_min": 82},
    "Hybrid":      {"tempo_lower": 2.7, "tempo_upper": 3.3, "head_sway_max": 3.2, "hip_rot_min": 36, "shoulder_rot_min": 80},
    "Long Iron":   {"tempo_lower": 2.7, "tempo_upper": 3.2, "head_sway_max": 3.0, "hip_rot_min": 36, "shoulder_rot_min": 80},
    "Mid Iron":    {"tempo_lower": 2.6, "tempo_upper": 3.1, "head_sway_max": 2.8, "hip_rot_min": 35, "shoulder_rot_min": 78},
    "Short Iron":  {"tempo_lower": 2.6, "tempo_upper": 3.0, "head_sway_max": 2.6, "hip_rot_min": 34, "shoulder_rot_min": 76},
    "Wedge":       {"tempo_lower": 2.5, "tempo_upper": 3.0, "head_sway_max": 2.5, "hip_rot_min": 32, "shoulder_rot_min": 74},
}