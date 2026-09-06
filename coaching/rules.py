# coaching/rules.py
# Rules engine: turns per-club launch-monitor statistics and round stats
# into prioritized, explained coaching pointers with measurable success
# criteria. Priority 1 = costs the most strokes.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from analysis.gapping import club_summary
from analysis.scoring import benchmark_for
from analysis.tendencies import expected_smash
from coaching.goals import get_goals_for_category
from integrations.trackman import club_category


@dataclass
class CoachingPointer:
    """Structured coaching feedback with priority, explanation and a measurable target."""
    rule_id: str
    message: str                      # Short actionable headline
    why: str                          # Why it costs strokes
    priority: int                     # 1 = highest
    tags: List[str] = field(default_factory=list)
    club: str = ""                    # Club (or "" for round-level pointers)
    metric_name: str = ""
    measured_value: Optional[float] = None
    target_value: Optional[float] = None
    target_text: str = ""             # Human readable target window
    success_criterion: str = ""       # What "fixed" looks like on TrackMan / scorecard
    check: Optional[Dict] = None      # Machine-checkable target for Progress: {metric, club, op, value}
    confidence: str = "high"          # high | medium | low (by sample size)
    n: int = 0
    source: str = "shots"             # "shots" | "rounds"


def _conf(n: int) -> str:
    if n >= 20:
        return "high"
    if n >= 10:
        return "medium"
    return "low"


def _isnum(v) -> bool:
    return v is not None and not (isinstance(v, float) and np.isnan(v))


# ---------------------------------------------------------------------------
# Shot rules
# ---------------------------------------------------------------------------

def evaluate_club(club: str, row: pd.Series, handedness: str = "right") -> List[CoachingPointer]:
    """Rules for a single club given its summary row from analysis.gapping.club_summary."""
    cat = club_category(club)
    g = get_goals_for_category(cat)
    n = int(row.get("shots", 0))
    conf = _conf(n)
    fade, draw = ("right", "left") if not str(handedness).lower().startswith("l") else ("left", "right")
    ps: List[CoachingPointer] = []
    is_iron_like = cat in ("Long Iron", "Mid Iron", "Short Iron", "Wedge", "Hybrid")

    side_std = row.get("side_std")
    ftp = row.get("ftp_mean")
    ftp_std = row.get("ftp_std")
    path = row.get("path_mean")
    attack = row.get("attack_mean")
    spin = row.get("spin_mean")
    launch = row.get("launch_mean")
    smash = row.get("smash_mean")
    smash_std = row.get("smash_std")
    carry_cv = row.get("carry_cv")
    carry_std = row.get("carry_std")
    spin_loft = row.get("spin_loft_mean")
    carry_med = row.get("carry_med")

    # 1. Dispersion
    if _isnum(side_std) and side_std > g["side_std_max"]:
        ps.append(CoachingPointer(
            rule_id="dispersion_wide", club=club,
            message=f"{club}: shots are spread ±{side_std:.0f} yds side to side",
            why=("Wide dispersion is what turns a decent swing into penalties, lost balls and short-sided chips. "
                 "Tightening the pattern is worth more strokes than adding distance."),
            priority=1 if cat in ("Driver", "Wood") else 2,
            tags=["dispersion", "face_control"],
            metric_name="side_std", measured_value=float(side_std), target_value=float(g["side_std_max"]),
            target_text=f"1-sigma side dispersion under {g['side_std_max']:.0f} yds",
            success_criterion=f"10 {club} shots with a side spread (±) under {g['side_std_max']:.0f} yds",
            check={"metric": "side_std", "club": club, "op": "<=", "value": float(g["side_std_max"])},
            confidence=conf, n=n,
        ))

    # 2/3. Face to path
    if _isnum(ftp):
        if ftp > g["ftp_max"]:
            ps.append(CoachingPointer(
                rule_id="face_open", club=club,
                message=f"{club}: clubface is {ftp:.1f}° open to your path (fade/slice)",
                why=(f"An open face to path curves the ball toward the {fade} and costs distance through added spin. "
                     "Face control is the single biggest driver of where the ball finishes."),
                priority=1,
                tags=["face_control", "slice"],
                metric_name="ftp_mean", measured_value=float(ftp), target_value=float(g["ftp_max"]),
                target_text=f"face-to-path between {g['ftp_min']:+.0f}° and {g['ftp_max']:+.0f}°",
                success_criterion=f"Average face-to-path inside ±2° over 10 {club} shots, with 7 of 10 inside ±3°",
                check={"metric": "ftp_mean", "club": club, "op": "abs<=", "value": 2.5},
                confidence=conf, n=n,
            ))
        elif ftp < g["ftp_min"]:
            ps.append(CoachingPointer(
                rule_id="face_closed", club=club,
                message=f"{club}: clubface is {abs(ftp):.1f}° closed to your path (draw/hook)",
                why=(f"A closed face to path sends shots low and {draw}, and the miss gets worse under pressure. "
                     "Neutralising the face makes every club more predictable."),
                priority=1,
                tags=["face_control", "hook"],
                metric_name="ftp_mean", measured_value=float(ftp), target_value=float(g["ftp_min"]),
                target_text=f"face-to-path between {g['ftp_min']:+.0f}° and {g['ftp_max']:+.0f}°",
                success_criterion=f"Average face-to-path inside ±2° over 10 {club} shots, with 7 of 10 inside ±3°",
                check={"metric": "ftp_mean", "club": club, "op": "abs<=", "value": 2.5},
                confidence=conf, n=n,
            ))
        elif _isnum(ftp_std) and ftp_std > g["ftp_std_max"]:
            ps.append(CoachingPointer(
                rule_id="face_inconsistent", club=club,
                message=f"{club}: face-to-path varies ±{ftp_std:.1f}° shot to shot (two-way miss)",
                why="A two-way miss is harder to play for than a consistent one. You can aim for a fade; you cannot aim for both.",
                priority=2,
                tags=["face_control"],
                metric_name="ftp_std", measured_value=float(ftp_std), target_value=float(g["ftp_std_max"]),
                target_text=f"face-to-path spread under ±{g['ftp_std_max']:.0f}°",
                success_criterion=f"Face-to-path spread (±) under {g['ftp_std_max']:.0f}° over 10 {club} shots",
                check={"metric": "ftp_std", "club": club, "op": "<=", "value": float(g["ftp_std_max"])},
                confidence=conf, n=n,
            ))

    # 4/5. Path
    if _isnum(path):
        if path < g["path_min"]:
            ps.append(CoachingPointer(
                rule_id="path_out_to_in", club=club,
                message=f"{club}: path is {abs(path):.1f}° out-to-in (over the top)",
                why=("An out-to-in path with an open face is the classic slice; with a square face it is a pull. "
                     "Either way it robs distance and makes the miss bigger on the course."),
                priority=2,
                tags=["path", "over_the_top"],
                metric_name="path_mean", measured_value=float(path), target_value=float(g["path_min"]),
                target_text=f"path between {g['path_min']:+.0f}° and {g['path_max']:+.0f}°",
                success_criterion=f"Average path between -1° and +3° over 10 {club} shots",
                check={"metric": "path_mean", "club": club, "op": ">=", "value": -1.5},
                confidence=conf, n=n,
            ))
        elif path > g["path_max"]:
            ps.append(CoachingPointer(
                rule_id="path_in_to_out_excess", club=club,
                message=f"{club}: path is {path:.1f}° in-to-out (too much)",
                why="A strongly in-to-out path needs a very precise face to work; small face errors become big pushes and hooks.",
                priority=3,
                tags=["path"],
                metric_name="path_mean", measured_value=float(path), target_value=float(g["path_max"]),
                target_text=f"path between {g['path_min']:+.0f}° and {g['path_max']:+.0f}°",
                success_criterion=f"Average path between 0° and +4° over 10 {club} shots",
                check={"metric": "path_mean", "club": club, "op": "<=", "value": 4.5},
                confidence=conf, n=n,
            ))

    # 6-8. Driver launch conditions
    if cat == "Driver":
        attack_fired = False
        if _isnum(attack) and attack < g["attack_min"]:
            attack_fired = True
            ps.append(CoachingPointer(
                rule_id="driver_attack_down", club=club,
                message=f"Driver: hitting down {abs(attack):.1f}° on the ball",
                why=("Hitting down with the driver adds spin and lowers launch, which costs 10-25 yards of carry at your speed "
                     "and makes the ball curve more. Hitting level or slightly up is free distance."),
                priority=2,
                tags=["attack_angle_driver"],
                metric_name="attack_mean", measured_value=float(attack), target_value=float(g["attack_min"]),
                target_text=f"attack angle between {g['attack_min']:+.0f}° and {g['attack_max']:+.0f}°",
                success_criterion="Average driver attack angle of 0° or better over 10 shots, 7 of 10 at or above 0°",
                check={"metric": "attack_mean", "club": club, "op": ">=", "value": 0.0},
                confidence=conf, n=n,
            ))
        if not attack_fired and _isnum(spin) and spin > g["spin_max"]:
            ps.append(CoachingPointer(
                rule_id="driver_spin_high", club=club,
                message=f"Driver: spin is {spin:.0f} rpm (too high)",
                why="High driver spin balloons the ball and exaggerates curve. It usually comes from a downward strike or hitting low on the face.",
                priority=3,
                tags=["attack_angle_driver", "strike"],
                metric_name="spin_mean", measured_value=float(spin), target_value=float(g["spin_max"]),
                target_text=f"spin between {g['spin_min']:.0f} and {g['spin_max']:.0f} rpm",
                success_criterion=f"Average driver spin under {g['spin_max']:.0f} rpm over 10 shots",
                check={"metric": "spin_mean", "club": club, "op": "<=", "value": float(g["spin_max"])},
                confidence=conf, n=n,
            ))
        if not attack_fired and _isnum(launch) and launch < g["launch_min"]:
            ps.append(CoachingPointer(
                rule_id="driver_launch_low", club=club,
                message=f"Driver: launch angle is {launch:.1f}° (too low)",
                why="Low launch leaves carry on the table. Tee height, ball position and a slight upward strike all raise it.",
                priority=3,
                tags=["attack_angle_driver"],
                metric_name="launch_mean", measured_value=float(launch), target_value=float(g["launch_min"]),
                target_text=f"launch between {g['launch_min']:.0f}° and {g['launch_max']:.0f}°",
                success_criterion=f"Average driver launch of {g['launch_min']:.0f}° or more over 10 shots",
                check={"metric": "launch_mean", "club": club, "op": ">=", "value": float(g["launch_min"])},
                confidence=conf, n=n,
            ))

    # 9/10. Iron low point
    if is_iron_like and cat != "Hybrid":
        attack_rule_fired = False
        if _isnum(attack) and attack > g["attack_max"]:
            attack_rule_fired = True
            ps.append(CoachingPointer(
                rule_id="iron_attack_shallow", club=club,
                message=f"{club}: attack angle is {attack:+.1f}° (not hitting down enough)",
                why=("Irons need a descending strike so the low point is in front of the ball. A level or upward strike "
                     "produces thin and fat shots, inconsistent distance and low spin that will not hold greens."),
                priority=2,
                tags=["low_point", "attack_angle_iron"],
                metric_name="attack_mean", measured_value=float(attack), target_value=float(g["attack_max"]),
                target_text=f"attack angle between {g['attack_min']:+.0f}° and {g['attack_max']:+.0f}°",
                success_criterion=f"Average {club} attack angle of {g['attack_max']:+.0f}° or lower over 10 shots, 8 of 10 below -1°",
                check={"metric": "attack_mean", "club": club, "op": "<=", "value": float(g["attack_max"])},
                confidence=conf, n=n,
            ))
        elif _isnum(attack) and attack < g["attack_min"] - 0.5:
            attack_rule_fired = True
            ps.append(CoachingPointer(
                rule_id="iron_attack_steep", club=club,
                message=f"{club}: attack angle is {attack:.1f}° (very steep)",
                why=("A very steep strike with irons almost always pairs with an out-to-in path: the over-the-top move. "
                     "It adds spin loft, costs ball speed, digs, and makes distance unpredictable. Shallowing the "
                     "approach fixes the path and the strike together."),
                priority=3,
                tags=["over_the_top", "path", "low_point"],
                metric_name="attack_mean", measured_value=float(attack), target_value=float(g["attack_min"]),
                target_text=f"attack angle between {g['attack_min']:+.0f}° and {g['attack_max']:+.0f}°",
                success_criterion=f"Average {club} attack angle between {g['attack_min']:+.0f}° and -2° over 10 shots",
                check={"metric": "attack_mean", "club": club, "op": ">=", "value": float(g["attack_min"])},
                confidence=conf, n=n,
            ))
        if not attack_rule_fired and _isnum(spin_loft) and "spin_loft_max" in g and spin_loft > g["spin_loft_max"]:
            ps.append(CoachingPointer(
                rule_id="iron_spin_loft_high", club=club,
                message=f"{club}: spin loft is {spin_loft:.0f}° (adding loft at impact)",
                why="High spin loft means the hands are flipping and adding loft. Ball speed drops and distance control suffers.",
                priority=3,
                tags=["spin_loft", "low_point"],
                metric_name="spin_loft_mean", measured_value=float(spin_loft), target_value=float(g["spin_loft_max"]),
                target_text=f"spin loft under {g['spin_loft_max']:.0f}°",
                success_criterion=f"Average {club} spin loft under {g['spin_loft_max']:.0f}° over 10 shots",
                check={"metric": "spin_loft_mean", "club": club, "op": "<=", "value": float(g["spin_loft_max"])},
                confidence=conf, n=n,
            ))

    # 11/12. Strike quality
    exp_smash = expected_smash(club)
    if _isnum(smash) and smash < min(g["smash_min"], exp_smash - 0.04):
        ps.append(CoachingPointer(
            rule_id="strike_low", club=club,
            message=f"{club}: smash factor {smash:.2f} (solid contact is around {exp_smash:.2f})",
            why="Low smash factor means off-centre contact. Every 0.05 of smash is roughly 3-4% of distance and a lot of dispersion.",
            priority=2,
            tags=["strike"],
            metric_name="smash_mean", measured_value=float(smash), target_value=float(exp_smash),
            target_text=f"smash factor around {exp_smash:.2f}",
            success_criterion=f"7 of 10 {club} shots with smash factor at or above {exp_smash - 0.03:.2f}",
            check={"metric": "smash_mean", "club": club, "op": ">=", "value": float(exp_smash - 0.03)},
            confidence=conf, n=n,
        ))
    elif _isnum(smash_std) and smash_std > g["smash_std_max"]:
        ps.append(CoachingPointer(
            rule_id="strike_inconsistent", club=club,
            message=f"{club}: strike quality varies (smash spread ±{smash_std:.2f})",
            why="Inconsistent contact shows up as inconsistent distance, which is how approach shots end up short-sided or over the green.",
            priority=3,
            tags=["strike"],
            metric_name="smash_std", measured_value=float(smash_std), target_value=float(g["smash_std_max"]),
            target_text=f"smash spread under ±{g['smash_std_max']:.2f}",
            success_criterion=f"Smash factor spread (±) under {g['smash_std_max']:.2f} over 10 {club} shots",
            check={"metric": "smash_std", "club": club, "op": "<=", "value": float(g["smash_std_max"])},
            confidence=conf, n=n,
        ))

    # 13. Distance control
    dist_bad = False
    if cat == "Wedge" and _isnum(carry_std) and "carry_std_max" in g and carry_std > g["carry_std_max"]:
        dist_bad = True
        target_txt = f"carry spread under ±{g['carry_std_max']:.0f} yds"
        check = {"metric": "carry_std", "club": club, "op": "<=", "value": float(g["carry_std_max"])}
        measured, target = float(carry_std), float(g["carry_std_max"])
        headline = f"{club}: carry varies ±{carry_std:.0f} yds"
    elif _isnum(carry_cv) and carry_cv > g["carry_cv_max"]:
        dist_bad = True
        target_txt = f"carry spread under {g['carry_cv_max'] * 100:.0f}% of your median"
        check = {"metric": "carry_cv", "club": club, "op": "<=", "value": float(g["carry_cv_max"])}
        measured, target = float(carry_cv * 100), float(g["carry_cv_max"] * 100)
        headline = f"{club}: carry varies {carry_cv * 100:.0f}% shot to shot"
    if dist_bad:
        ps.append(CoachingPointer(
            rule_id="distance_inconsistent", club=club,
            message=headline,
            why=("Distance control decides whether approach shots finish pin-high. For an 80s golfer, "
                 "consistent carry with wedges and short irons is worth more than any swing change."),
            priority=2 if cat in ("Wedge", "Short Iron", "Mid Iron") else 3,
            tags=["distance_control", "strike"],
            metric_name=check["metric"], measured_value=measured, target_value=target,
            target_text=target_txt,
            success_criterion=f"7 of 10 {club} shots carry within 5% of your median for the set",
            check=check,
            confidence=conf, n=n,
        ))

    # 14. Low spin irons (cannot hold greens)
    if is_iron_like and cat != "Hybrid" and _isnum(spin) and spin < g["spin_min"] and _isnum(carry_med):
        ps.append(CoachingPointer(
            rule_id="iron_spin_low", club=club,
            message=f"{club}: spin is {spin:.0f} rpm (low for this club)",
            why="Low iron spin usually means a thin strike or dry/old balls; on the course it rolls through greens.",
            priority=4,
            tags=["strike", "low_point"],
            metric_name="spin_mean", measured_value=float(spin), target_value=float(g["spin_min"]),
            target_text=f"spin between {g['spin_min']:.0f} and {g['spin_max']:.0f} rpm",
            success_criterion=f"Average {club} spin above {g['spin_min']:.0f} rpm over 10 shots",
            check={"metric": "spin_mean", "club": club, "op": ">=", "value": float(g["spin_min"])},
            confidence=conf, n=n,
        ))

    return ps


def evaluate_shots(df: pd.DataFrame, handedness: str = "right", min_shots: int = 8) -> List[CoachingPointer]:
    """
    Run all shot rules over a prepared shot frame (see analysis.prep).
    Only clubs with at least `min_shots` recent shots are evaluated.
    """
    if df is None or df.empty:
        return []
    summary = club_summary(df, min_shots=min_shots)
    pointers: List[CoachingPointer] = []
    for club, row in summary.iterrows():
        pointers.extend(evaluate_club(str(club), row, handedness))
    return sort_pointers(pointers)


# ---------------------------------------------------------------------------
# Round rules
# ---------------------------------------------------------------------------

def evaluate_rounds(agg: Dict, target_score: int = 85, min_rounds: int = 2) -> List[CoachingPointer]:
    if not agg or agg.get("n_rounds", 0) < min_rounds:
        return []
    bench = benchmark_for(target_score)
    n = int(agg.get("n_rounds", 0))
    conf = "high" if n >= 8 else ("medium" if n >= 4 else "low")
    ps: List[CoachingPointer] = []

    pen = agg.get("penalties")
    if _isnum(pen) and pen > bench["penalties"] + 0.4:
        ps.append(CoachingPointer(
            rule_id="penalties_high", source="rounds",
            message=f"{pen:.1f} penalty strokes per round (an {target_score}-shooter averages {bench['penalties']:.1f})",
            why=("Penalties are the fastest strokes to remove. They almost always come from the big miss off the tee or "
                 "taking on a carry your Safe number says you cannot make."),
            priority=1, tags=["course_management", "tee_strategy", "dispersion"],
            metric_name="penalties", measured_value=float(pen), target_value=float(bench["penalties"]),
            target_text=f"under {bench['penalties']:.1f} per round",
            success_criterion=f"Two rounds in a row with {max(0, round(bench['penalties'])) or 1} or fewer penalty strokes",
            check={"metric": "penalties", "club": "", "op": "<=", "value": float(bench["penalties"]) + 0.2},
            confidence=conf, n=n,
        ))

    tp = agg.get("three_putts")
    if _isnum(tp) and tp > bench["three_putts"] + 0.5:
        ps.append(CoachingPointer(
            rule_id="three_putts_high", source="rounds",
            message=f"{tp:.1f} three-putts per round (target {bench['three_putts']:.1f})",
            why="Each three-putt is a full stroke. Lag putting from 25-45 feet is the cheapest skill to improve and needs no simulator time.",
            priority=1, tags=["putting_lag"],
            metric_name="three_putts", measured_value=float(tp), target_value=float(bench["three_putts"]),
            target_text=f"under {bench['three_putts']:.1f} per round",
            success_criterion="Three rounds averaging under 1.5 three-putts",
            check={"metric": "three_putts", "club": "", "op": "<=", "value": float(bench["three_putts"]) + 0.3},
            confidence=conf, n=n,
        ))

    putts = agg.get("putts")
    if _isnum(putts) and putts > bench["putts"] + 1.5 and not any(p.rule_id == "three_putts_high" for p in ps):
        ps.append(CoachingPointer(
            rule_id="putts_high", source="rounds",
            message=f"{putts:.1f} putts per round (target {bench['putts']:.1f})",
            why="Putts are a third of your score. Holing more from 3-6 feet and lagging closer removes strokes without touching the swing.",
            priority=2, tags=["putting_short", "putting_lag"],
            metric_name="putts", measured_value=float(putts), target_value=float(bench["putts"]),
            target_text=f"under {bench['putts']:.0f} per round",
            success_criterion=f"Three rounds averaging {bench['putts']:.0f} putts or fewer",
            check={"metric": "putts", "club": "", "op": "<=", "value": float(bench["putts"]) + 0.5},
            confidence=conf, n=n,
        ))

    dbl = agg.get("doubles_plus")
    if _isnum(dbl) and dbl > bench["doubles_plus"] + 1.0:
        ps.append(CoachingPointer(
            rule_id="blowup_holes", source="rounds",
            message=f"{dbl:.1f} doubles or worse per round (target {bench['doubles_plus']:.1f})",
            why=("Low-80s rounds are built from bogeys, not birdies. Blow-up holes come from compounding one bad shot "
                 "with a hero recovery. Taking the bogey saves two strokes a round on its own."),
            priority=2, tags=["course_management", "bogey_strategy"],
            metric_name="doubles_plus", measured_value=float(dbl), target_value=float(bench["doubles_plus"]),
            target_text=f"under {bench['doubles_plus']:.1f} per round",
            success_criterion="Three rounds with two or fewer doubles each",
            check={"metric": "doubles_plus", "club": "", "op": "<=", "value": float(bench["doubles_plus"]) + 0.5},
            confidence=conf, n=n,
        ))

    gir = agg.get("gir_pct")
    if _isnum(gir) and gir < bench["gir_pct"] - 8:
        ps.append(CoachingPointer(
            rule_id="gir_low", source="rounds",
            message=f"{gir:.0f}% greens in regulation (target {bench['gir_pct']:.0f}%)",
            why="More greens means more two-putt pars and fewer chips. It comes from knowing your carry numbers and aiming at the middle of the green.",
            priority=3, tags=["approach", "distance_control", "course_management"],
            metric_name="gir_pct", measured_value=float(gir), target_value=float(bench["gir_pct"]),
            target_text=f"{bench['gir_pct']:.0f}% or better",
            success_criterion=f"Three rounds averaging {bench['gir_pct']:.0f}% GIR or better",
            check={"metric": "gir_pct", "club": "", "op": ">=", "value": float(bench["gir_pct"]) - 3},
            confidence=conf, n=n,
        ))

    fir = agg.get("fir_pct")
    if _isnum(fir) and fir < bench["fir_pct"] - 10:
        ps.append(CoachingPointer(
            rule_id="fir_low", source="rounds",
            message=f"{fir:.0f}% fairways hit (target {bench['fir_pct']:.0f}%)",
            why="Missed fairways cost about a quarter stroke each on average, and much more when they find trouble. Club selection off the tee matters as much as the swing.",
            priority=3, tags=["dispersion", "tee_strategy"],
            metric_name="fir_pct", measured_value=float(fir), target_value=float(bench["fir_pct"]),
            target_text=f"{bench['fir_pct']:.0f}% or better",
            success_criterion=f"Three rounds averaging {bench['fir_pct']:.0f}% fairways or better",
            check={"metric": "fir_pct", "club": "", "op": ">=", "value": float(bench["fir_pct"]) - 3},
            confidence=conf, n=n,
        ))

    scr = agg.get("scrambling_pct")
    if _isnum(scr) and agg.get("scramble_attempts", 0) >= 10 and scr < bench["scrambling_pct"] - 8:
        ps.append(CoachingPointer(
            rule_id="scrambling_low", source="rounds",
            message=f"{scr:.0f}% up-and-downs (target {bench['scrambling_pct']:.0f}%)",
            why="At your level you will miss 12+ greens a round. Getting a few more of those up and down is worth several strokes.",
            priority=3, tags=["chipping", "wedge_distance"],
            metric_name="scrambling_pct", measured_value=float(scr), target_value=float(bench["scrambling_pct"]),
            target_text=f"{bench['scrambling_pct']:.0f}% or better",
            success_criterion=f"Three rounds averaging {bench['scrambling_pct']:.0f}% scrambling or better",
            check={"metric": "scrambling_pct", "club": "", "op": ">=", "value": float(bench["scrambling_pct"]) - 3},
            confidence=conf, n=n,
        ))

    return sort_pointers(ps)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CATEGORY_WEIGHT = {"Driver": 0, "Wood": 2, "Hybrid": 3, "Long Iron": 3, "Mid Iron": 1, "Short Iron": 2, "Wedge": 1, "Other": 5}


def sort_pointers(pointers: List[CoachingPointer]) -> List[CoachingPointer]:
    """Priority first, then rounds before shots, then clubs that matter most for scoring."""
    def key(p: CoachingPointer):
        cat_w = _CATEGORY_WEIGHT.get(club_category(p.club), 5) if p.club else -1
        conf_w = {"high": 0, "medium": 1, "low": 2}.get(p.confidence, 2)
        return (p.priority, conf_w, cat_w, p.rule_id)
    return sorted(pointers, key=key)


def top_priorities(shot_pointers: List[CoachingPointer], round_pointers: List[CoachingPointer], k: int = 3) -> List[CoachingPointer]:
    """Pick the k pointers to work on this week: at most one per rule family, rounds and shots mixed."""
    merged = sort_pointers(list(round_pointers) + list(shot_pointers))
    chosen: List[CoachingPointer] = []
    seen_rules = set()
    seen_clubs = set()
    for p in merged:
        fam = p.rule_id.split("_")[0]
        if p.rule_id in seen_rules:
            continue
        if p.club and p.club in seen_clubs and len(chosen) < k - 1:
            # prefer covering a different club unless we are short of candidates
            continue
        chosen.append(p)
        seen_rules.add(p.rule_id)
        if p.club:
            seen_clubs.add(p.club)
        if len(chosen) >= k:
            break
    if len(chosen) < k:
        for p in merged:
            if p not in chosen:
                chosen.append(p)
                if len(chosen) >= k:
                    break
    return chosen


def get_pointer_drills(pointer: CoachingPointer, all_drills: List[Dict], limit: int = 3) -> List[Dict]:
    if not pointer.tags or not all_drills:
        return []
    tagset = set(pointer.tags)
    scored = []
    for d in all_drills:
        overlap = len(tagset & set(d.get("tags", [])))
        if overlap:
            scored.append((-overlap, d.get("name", ""), d))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [d for _, _, d in scored[:limit]]
