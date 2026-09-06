# coaching package - rules, goals, drills and weekly plans
from coaching.goals import CATEGORY_GOALS, CLUB_GOALS, DEFAULT_GOALS, get_goals_for_category, get_goals_for_club
from coaching.drills import DRILL_TAG_ALIASES, map_tags_to_drill_tags, tag_to_drills, load_drills
from coaching.rules import (
    CoachingPointer,
    evaluate_club,
    evaluate_shots,
    evaluate_rounds,
    sort_pointers,
    top_priorities,
    get_pointer_drills,
)
from coaching.plan import WeeklyPlan, PlanSession, PlanBlock, build_weekly_plan, evaluate_check

__all__ = [
    "CATEGORY_GOALS", "CLUB_GOALS", "DEFAULT_GOALS", "get_goals_for_category", "get_goals_for_club",
    "DRILL_TAG_ALIASES", "map_tags_to_drill_tags", "tag_to_drills", "load_drills",
    "CoachingPointer", "evaluate_club", "evaluate_shots", "evaluate_rounds", "sort_pointers", "top_priorities", "get_pointer_drills",
    "WeeklyPlan", "PlanSession", "PlanBlock", "build_weekly_plan", "evaluate_check",
]
