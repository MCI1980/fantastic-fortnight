# coaching package - Golf swing coaching logic
from coaching.goals import CLUB_GOALS, DEFAULT_GOALS, get_goals_for_club
from coaching.drills import DRILL_TAG_ALIASES, map_tags_to_drill_tags, tag_to_drills, load_drills
from coaching.rules import (
    analyze_with_goals,
    analyze_with_goals_detailed,
    get_pointer_drills,
    CoachingPointer,
    COACHING_RULES,
)

__all__ = [
    # Goals
    "CLUB_GOALS",
    "DEFAULT_GOALS",
    "get_goals_for_club",
    # Drills
    "DRILL_TAG_ALIASES",
    "map_tags_to_drill_tags",
    "tag_to_drills",
    "load_drills",
    # Rules
    "analyze_with_goals",
    "analyze_with_goals_detailed",
    "get_pointer_drills",
    "CoachingPointer",
    "COACHING_RULES",
]
