# coaching/plan.py
# Weekly practice plan generator: turns the top priorities into two or
# three concrete simulator sessions plus one on-course rule, each with a
# measurable success check that the Progress tab can evaluate.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd

from analysis.games import games_for_tags, game_applies_to_club
from coaching.drills import map_tags_to_drill_tags
from coaching.rules import CoachingPointer, get_pointer_drills
from integrations.trackman import club_sort_key


@dataclass
class PlanBlock:
    name: str
    minutes: int
    reps: str
    instructions: List[str]
    success_metric: str = ""
    trackman_watch: str = ""
    kind: str = "drill"           # warmup | drill | game | gapping | home | course


@dataclass
class PlanSession:
    title: str
    focus: str
    minutes: int
    blocks: List[PlanBlock]
    where: str = "sim"


@dataclass
class WeeklyPlan:
    week_of: str
    focus: List[str]
    sessions: List[PlanSession]
    on_course_rule: str
    checks: List[Dict]
    created_at: str = ""
    pointer_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "WeeklyPlan":
        sessions = []
        for s in d.get("sessions", []):
            blocks = [PlanBlock(**b) for b in s.get("blocks", [])]
            sessions.append(PlanSession(title=s.get("title", ""), focus=s.get("focus", ""), minutes=int(s.get("minutes", 0)), blocks=blocks, where=s.get("where", "sim")))
        return cls(
            week_of=d.get("week_of", ""),
            focus=list(d.get("focus", [])),
            sessions=sessions,
            on_course_rule=d.get("on_course_rule", ""),
            checks=list(d.get("checks", [])),
            created_at=d.get("created_at", ""),
            pointer_ids=list(d.get("pointer_ids", [])),
        )


WARMUP = PlanBlock(
    name="Warm-up",
    minutes=6,
    reps="12 balls",
    instructions=[
        "6 half-swing wedges at 60% effort, then 6 smooth 8-irons.",
        "Do not look at the numbers yet. Rhythm and balance only.",
    ],
    kind="warmup",
)


def _drill_block(drill: Dict, pointer: CoachingPointer, minutes: int = 14) -> PlanBlock:
    return PlanBlock(
        name=drill.get("name", "Drill"),
        minutes=minutes,
        reps="20-25 balls",
        instructions=list(drill.get("steps", [])),
        success_metric=pointer.success_criterion,
        trackman_watch=drill.get("trackman_watch", ""),
        kind="drill",
    )


def _transfer_block(pointer: CoachingPointer) -> PlanBlock:
    club = pointer.club or "the same club"
    return PlanBlock(
        name="Transfer: normal swings",
        minutes=8,
        reps="10 balls",
        instructions=[
            f"Hit 10 normal {club} shots with your full routine, no drill props.",
            "Compare the 10-shot average with your session numbers in the Coach tab.",
            f"Pass mark: {pointer.success_criterion}" if pointer.success_criterion else "Pass mark: the metric you are working on is inside its target window.",
        ],
        success_metric=pointer.success_criterion,
        trackman_watch=pointer.metric_name.replace("_", " "),
        kind="drill",
    )


def _game_block(game: Dict, club: str) -> PlanBlock:
    return PlanBlock(
        name=f"Game: {game.get('name')} ({club})",
        minutes=10,
        reps=f"{game.get('shots', 10)} balls",
        instructions=[
            game.get("description", ""),
            "Export the session afterwards; the Coach tab scores it automatically from the last shots with that club.",
        ],
        success_metric="Beat last week's score",
        trackman_watch=str(game.get("metric", "")).replace("_", " "),
        kind="game",
    )


def _gapping_block(summary: Optional[pd.DataFrame], min_shots: int = 8) -> Optional[PlanBlock]:
    """Ask for more shots with clubs that have thin data so the yardage card fills in."""
    if summary is None or summary.empty:
        return PlanBlock(
            name="Gapping: build your yardage card",
            minutes=12,
            reps="8 balls per club",
            instructions=[
                "Hit 8 normal shots with Driver, 5-iron, 7-iron, 9-iron, PW and SW. Tag the club in TPS before each set.",
                "Export the session. The My Numbers tab will show your Safe / Plan / Max carry per club.",
            ],
            kind="gapping",
        )
    thin = [c for c, r in summary.iterrows() if r.get("shots", 0) < min_shots]
    if not thin:
        return None
    thin = sorted(thin, key=club_sort_key)[:4]
    return PlanBlock(
        name="Gapping: top up thin clubs",
        minutes=10,
        reps="8 balls per club",
        instructions=[
            f"Hit 8 normal shots each with: {', '.join(thin)}.",
            "Tag the club in TPS before each set so the export carries the club name.",
        ],
        kind="gapping",
    )


def _home_block(pointer: CoachingPointer, drills: List[Dict]) -> Optional[PlanBlock]:
    matches = [d for d in get_pointer_drills(pointer, drills, limit=5) if d.get("where") in ("home", "course")]
    if not matches:
        return None
    d = matches[0]
    return PlanBlock(
        name=d.get("name", "Practice"),
        minutes=10,
        reps="3 x per week",
        instructions=list(d.get("steps", [])),
        success_metric=pointer.success_criterion,
        trackman_watch=d.get("trackman_watch", ""),
        kind="home" if d.get("where") == "home" else "course",
    )


def _default_course_rule(handedness: str = "right") -> str:
    return ("Play to your Safe number: pick the club whose 20th-percentile carry clears the trouble, "
            "and aim at the middle of the green.")


def build_weekly_plan(
    priorities: List[CoachingPointer],
    summary: Optional[pd.DataFrame],
    drills: List[Dict],
    games: List[Dict],
    handedness: str = "right",
    week_of: Optional[date] = None,
) -> WeeklyPlan:
    week_of = week_of or date.today()
    shot_ps = [p for p in priorities if p.source == "shots"]
    round_ps = [p for p in priorities if p.source == "rounds"]
    sessions: List[PlanSession] = []
    checks: List[Dict] = []
    focus: List[str] = []

    # ---- Session 1: technical work on the top shot pointer -----------------
    if shot_ps:
        p1 = shot_ps[0]
        focus.append(p1.message)
        p1_drills = get_pointer_drills(p1, drills, limit=3)
        sim_drills = [d for d in p1_drills if d.get("where", "sim") == "sim"] or p1_drills
        blocks = [WARMUP]
        for d in sim_drills[:2]:
            blocks.append(_drill_block(d, p1))
        blocks.append(_transfer_block(p1))
        sessions.append(PlanSession(
            title="Session 1 - Technical",
            focus=p1.message,
            minutes=sum(b.minutes for b in blocks),
            blocks=blocks,
        ))
        if p1.check:
            checks.append({**p1.check, "label": p1.message, "rule_id": p1.rule_id})

    # ---- Session 2: skills game + second pointer + gapping -----------------
    blocks = [WARMUP]
    game_added = False
    for p in shot_ps[:2]:
        candidates = games_for_tags(map_tags_to_drill_tags(p.tags) + p.tags, games)
        candidates = [g for g in candidates if not p.club or game_applies_to_club(g, p.club)]
        if candidates:
            blocks.append(_game_block(candidates[0], p.club or "your 7-iron"))
            game_added = True
            break
    if not game_added and games:
        blocks.append(_game_block(games[0], "Driver"))
    if len(shot_ps) > 1:
        p2 = shot_ps[1]
        focus.append(p2.message)
        p2_drills = [d for d in get_pointer_drills(p2, drills, limit=3) if d.get("where", "sim") == "sim"]
        if p2_drills:
            blocks.append(_drill_block(p2_drills[0], p2, minutes=12))
        if p2.check:
            checks.append({**p2.check, "label": p2.message, "rule_id": p2.rule_id})
    gap = _gapping_block(summary)
    if gap:
        blocks.append(gap)
    sessions.append(PlanSession(
        title="Session 2 - Skills and Gapping",
        focus=(shot_ps[1].message if len(shot_ps) > 1 else "Scored games and yardage card"),
        minutes=sum(b.minutes for b in blocks),
        blocks=blocks,
    ))

    # ---- Session 3: scoring (from round data) or wedge distance -------------
    on_course_rule = _default_course_rule(handedness)
    if round_ps:
        r1 = round_ps[0]
        focus.append(r1.message)
        blocks = []
        home = _home_block(r1, drills)
        if home:
            blocks.append(home)
        course_drills = [d for d in get_pointer_drills(r1, drills, limit=5) if d.get("where") == "course"]
        if course_drills:
            steps = course_drills[0].get("steps", [])
            on_course_rule = f"{course_drills[0].get('name')}: {steps[0]}" if steps else course_drills[0].get("name", on_course_rule)
        if not blocks:
            blocks.append(PlanBlock(
                name="Scoring focus",
                minutes=10,
                reps="each round",
                instructions=[r1.why, f"Target: {r1.success_criterion}"],
                success_metric=r1.success_criterion,
                kind="course",
            ))
        sessions.append(PlanSession(
            title="Session 3 - Scoring (no simulator needed)",
            focus=r1.message,
            minutes=sum(b.minutes for b in blocks),
            blocks=blocks,
            where="home",
        ))
        if r1.check:
            checks.append({**r1.check, "label": r1.message, "rule_id": r1.rule_id})
    else:
        wedge = next((d for d in drills if "wedge_distance" in d.get("tags", []) and d.get("where") == "sim"), None)
        blocks = [WARMUP]
        if wedge:
            blocks.append(PlanBlock(
                name=wedge.get("name", "Wedge distances"),
                minutes=15,
                reps="15-20 balls",
                instructions=list(wedge.get("steps", [])),
                success_metric="Three repeatable wedge carries written on your yardage card",
                trackman_watch=wedge.get("trackman_watch", "Carry"),
            ))
        blocks.append(PlanBlock(
            name="Log a round",
            minutes=3,
            reps="after your next round",
            instructions=["Enter score, putts, fairways, greens and penalties per hole in the Rounds tab.",
                          "With two rounds logged the Coach tab will show where strokes are actually going."],
            kind="course",
        ))
        sessions.append(PlanSession(
            title="Session 3 - Scoring clubs",
            focus="Wedge distance control and round tracking",
            minutes=sum(b.minutes for b in blocks),
            blocks=blocks,
        ))

    if not focus:
        focus = ["Build your yardage card and log two rounds"]

    return WeeklyPlan(
        week_of=week_of.isoformat(),
        focus=focus[:3],
        sessions=sessions,
        on_course_rule=on_course_rule,
        checks=checks,
        created_at=datetime.now().isoformat(),
        pointer_ids=[p.rule_id + (":" + p.club if p.club else "") for p in priorities],
    )


# ---------------------------------------------------------------------------
# Check evaluation (used by the Progress tab)
# ---------------------------------------------------------------------------

def evaluate_check(check: Dict, summary: Optional[pd.DataFrame], rounds_agg: Optional[Dict]) -> Dict:
    """Evaluate one plan check against current data. Returns {ok, value, target, label}."""
    metric = check.get("metric")
    club = check.get("club") or ""
    op = check.get("op", "<=")
    target = float(check.get("value", 0))
    value = None
    if club:
        if summary is not None and not summary.empty and club in summary.index and metric in summary.columns:
            v = summary.loc[club, metric]
            value = None if pd.isna(v) else float(v)
    else:
        if rounds_agg:
            v = rounds_agg.get(metric)
            value = None if v is None else float(v)
    ok = None
    if value is not None:
        if op == "<=":
            ok = value <= target
        elif op == ">=":
            ok = value >= target
        elif op == "abs<=":
            ok = abs(value) <= target
    return {"label": check.get("label", metric), "metric": metric, "club": club, "value": value, "target": target, "op": op, "ok": ok}
