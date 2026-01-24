# coaching package - Golf swing coaching logic
from coaching.goals import CLUB_GOALS, DEFAULT_GOALS
from coaching.drills import DRILL_TAG_ALIASES, map_tags_to_drill_tags, tag_to_drills, load_drills
from coaching.rules import analyze_with_goals

__all__ = [
    "CLUB_GOALS",
    "DEFAULT_GOALS",
    "DRILL_TAG_ALIASES",
    "map_tags_to_drill_tags",
    "tag_to_drills",
    "load_drills",
    "analyze_with_goals",
]
