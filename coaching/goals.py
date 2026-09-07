# coaching/goals.py
# Launch-monitor target windows by club category.
#
# These are amateur-realistic windows (what a consistent 80s golfer
# produces), not tour numbers. Signs follow the normalized convention from
# analysis.prep: positive path = in-to-out, positive face-to-path = fade
# side, positive attack = hitting up.

from typing import Dict

DEFAULT_GOALS: Dict[str, float] = {
    "path_min": -3.0,
    "path_max": 5.0,
    "ftp_min": -3.0,
    "ftp_max": 3.0,
    "ftp_std_max": 4.0,
    "smash_std_max": 0.06,
    "carry_cv_max": 0.07,
    "side_std_max": 18.0,
}

CATEGORY_GOALS: Dict[str, Dict[str, float]] = {
    "Driver": {
        "attack_min": -1.0, "attack_max": 5.0,
        "launch_min": 10.0, "launch_max": 15.0,
        "spin_min": 1800, "spin_max": 3200,
        "smash_min": 1.45,
        "side_std_max": 22.0, "carry_cv_max": 0.07,
    },
    "Wood": {
        "attack_min": -3.5, "attack_max": 1.5,
        "launch_min": 9.0, "launch_max": 14.0,
        "spin_min": 2400, "spin_max": 4300,
        "smash_min": 1.42,
        "side_std_max": 20.0, "carry_cv_max": 0.07,
    },
    "Hybrid": {
        "attack_min": -4.5, "attack_max": 0.5,
        "launch_min": 11.0, "launch_max": 16.0,
        "spin_min": 3300, "spin_max": 5300,
        "smash_min": 1.40,
        "side_std_max": 18.0, "carry_cv_max": 0.07,
    },
    "Long Iron": {
        "attack_min": -5.5, "attack_max": -0.5,
        "launch_min": 12.0, "launch_max": 18.0,
        "spin_min": 3800, "spin_max": 6000,
        "smash_min": 1.37, "spin_loft_max": 24.0,
        "side_std_max": 16.0, "carry_cv_max": 0.07,
    },
    "Mid Iron": {
        "attack_min": -6.0, "attack_max": -1.0,
        "launch_min": 15.0, "launch_max": 21.0,
        "spin_min": 5000, "spin_max": 7800,
        "smash_min": 1.34, "spin_loft_max": 26.0,
        "side_std_max": 14.0, "carry_cv_max": 0.06,
    },
    "Short Iron": {
        "attack_min": -7.0, "attack_max": -1.5,
        "launch_min": 19.0, "launch_max": 26.0,
        "spin_min": 6500, "spin_max": 9800,
        "smash_min": 1.29, "spin_loft_max": 29.0,
        "side_std_max": 11.0, "carry_cv_max": 0.06,
    },
    "Wedge": {
        "attack_min": -8.0, "attack_max": -2.0,
        "launch_min": 24.0, "launch_max": 36.0,
        "spin_min": 7500, "spin_max": 12000,
        "smash_min": 1.15,
        "side_std_max": 8.0, "carry_std_max": 7.0, "carry_cv_max": 0.07,
    },
}

# Backwards-compatible name used by older code/tests
CLUB_GOALS = CATEGORY_GOALS


def get_goals_for_category(category: str) -> Dict[str, float]:
    goals = dict(DEFAULT_GOALS)
    goals.update(CATEGORY_GOALS.get(category, {}))
    return goals


def get_goals_for_club(club: str) -> Dict[str, float]:
    from integrations.trackman import club_category
    return get_goals_for_category(club_category(club))
