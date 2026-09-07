# tests/test_coaching.py
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import aggregate_rounds, club_summary, filter_valid, prepare_shots, load_games
from coaching import (
    CATEGORY_GOALS,
    build_weekly_plan,
    evaluate_check,
    evaluate_club,
    evaluate_rounds,
    evaluate_shots,
    get_goals_for_club,
    get_pointer_drills,
    load_drills,
    top_priorities,
)
from data.plans import PlanStore
from data.rounds import HoleResult, Round
from integrations.rounds_csv import parse_rounds_csv
from integrations.trackman import parse_trackman_csv

SAMPLE = Path(__file__).parent / "sample_trackman.csv"
ROUNDS = Path(__file__).parent / "sample_rounds.csv"


@pytest.fixture
def shots():
    return filter_valid(prepare_shots(parse_trackman_csv(SAMPLE).df, "right"))


@pytest.fixture
def drills():
    return load_drills()


def _row(**kw) -> pd.Series:
    base = {"shots": 12, "carry_med": 150.0, "carry_std": 6.0, "carry_cv": 0.04, "side_std": 8.0,
            "ftp_mean": 0.5, "ftp_std": 2.0, "path_mean": 1.0, "attack_mean": -3.0, "spin_mean": 6500.0,
            "launch_mean": 18.0, "smash_mean": 1.37, "smash_std": 0.03, "spin_loft_mean": 21.0}
    base.update(kw)
    return pd.Series(base)


class TestGoals:
    def test_all_categories_present(self):
        for cat in ["Driver", "Wood", "Hybrid", "Long Iron", "Mid Iron", "Short Iron", "Wedge"]:
            assert cat in CATEGORY_GOALS

    def test_goals_for_club_merge_defaults(self):
        g = get_goals_for_club("7 Iron")
        assert g["attack_max"] == CATEGORY_GOALS["Mid Iron"]["attack_max"]
        assert "path_min" in g  # from defaults


class TestClubRules:
    def test_clean_club_has_no_findings(self):
        assert evaluate_club("7 Iron", _row()) == []

    def test_open_face_is_priority_one(self):
        ps = evaluate_club("7 Iron", _row(ftp_mean=5.5))
        ids = [p.rule_id for p in ps]
        assert "face_open" in ids
        assert next(p for p in ps if p.rule_id == "face_open").priority == 1

    def test_closed_face(self):
        ids = [p.rule_id for p in evaluate_club("7 Iron", _row(ftp_mean=-4.5))]
        assert "face_closed" in ids

    def test_over_the_top(self):
        ps = evaluate_club("Driver", _row(path_mean=-5.0, attack_mean=1.0, spin_mean=2600, launch_mean=12, smash_mean=1.47, side_std=15))
        assert [p.rule_id for p in ps] == ["path_out_to_in"]

    def test_driver_negative_attack(self):
        ps = evaluate_club("Driver", _row(attack_mean=-3.0, spin_mean=3600, launch_mean=9.5, smash_mean=1.47, side_std=15))
        ids = [p.rule_id for p in ps]
        assert "driver_attack_down" in ids
        # spin/launch rules are suppressed when the attack rule already explains them
        assert "driver_spin_high" not in ids and "driver_launch_low" not in ids

    def test_driver_spin_without_attack_issue(self):
        ps = evaluate_club("Driver", _row(attack_mean=1.0, spin_mean=3600, launch_mean=12, smash_mean=1.47, side_std=15))
        assert [p.rule_id for p in ps] == ["driver_spin_high"]

    def test_iron_not_hitting_down(self):
        ids = [p.rule_id for p in evaluate_club("8 Iron", _row(attack_mean=0.5))]
        assert "iron_attack_shallow" in ids

    def test_iron_too_steep_suppresses_spin_loft_rule(self):
        ids = [p.rule_id for p in evaluate_club("8 Iron", _row(attack_mean=-9.0, spin_loft_mean=31.0))]
        assert "iron_attack_steep" in ids
        assert "iron_spin_loft_high" not in ids
        assert "iron_attack_shallow" not in ids

    def test_iron_within_window_no_attack_rule(self):
        ids = [p.rule_id for p in evaluate_club("8 Iron", _row(attack_mean=-4.0))]
        assert not any(r.startswith("iron_attack") for r in ids)

    def test_wedge_distance_control(self):
        ps = evaluate_club("SW", _row(attack_mean=-4, spin_mean=9000, launch_mean=30, smash_mean=1.2, carry_std=10, carry_cv=0.12, side_std=5))
        assert [p.rule_id for p in ps] == ["distance_inconsistent"]
        assert ps[0].priority == 2

    def test_low_smash(self):
        ids = [p.rule_id for p in evaluate_club("7 Iron", _row(smash_mean=1.26))]
        assert "strike_low" in ids

    def test_sample_file_findings(self, shots):
        ps = evaluate_shots(shots, "right", min_shots=8)
        ids = {(p.club, p.rule_id) for p in ps}
        # the sample driver slices with a downward strike; the 7-iron has an open face
        assert ("Driver", "face_open") in ids
        assert ("Driver", "driver_attack_down") in ids
        assert ("7 Iron", "face_open") in ids
        # PW only has 8 shots and is clean
        assert not any(c == "PW" for c, _ in ids)
        # sorted by priority
        assert [p.priority for p in ps] == sorted(p.priority for p in ps)
        for p in ps:
            assert p.success_criterion and p.check and p.why


class TestRoundRules:
    @pytest.fixture
    def agg(self):
        rounds, _ = parse_rounds_csv(ROUNDS.read_bytes())
        return aggregate_rounds(rounds)

    def test_sample_rounds_flag_penalties_and_putting(self, agg):
        ps = evaluate_rounds(agg, 85)
        ids = [p.rule_id for p in ps]
        assert "penalties_high" in ids
        assert "three_putts_high" in ids
        assert all(p.source == "rounds" for p in ps)

    def test_needs_two_rounds(self, agg):
        assert evaluate_rounds({"n_rounds": 1, "penalties": 5}, 85) == []

    def test_good_rounds_no_findings(self):
        holes = [HoleResult(i, 4, 4, putts=2, fir=True, gir=True, penalties=0) for i in range(1, 19)]
        rounds = [Round.create("2026-08-01", "X", holes), Round.create("2026-08-08", "X", holes)]
        assert evaluate_rounds(aggregate_rounds(rounds), 85) == []


class TestPrioritiesAndPlan:
    def test_top_priorities_mix_sources(self, shots):
        rounds, _ = parse_rounds_csv(ROUNDS.read_bytes())
        sp = evaluate_shots(shots, "right")
        rp = evaluate_rounds(aggregate_rounds(rounds), 85)
        top = top_priorities(sp, rp, k=3)
        assert len(top) == 3
        assert len({p.rule_id for p in top}) == 3
        assert any(p.source == "rounds" for p in top)

    def test_drills_match_pointers(self, shots, drills):
        for p in evaluate_shots(shots, "right"):
            assert get_pointer_drills(p, drills), f"no drills for {p.rule_id}"

    def test_every_drill_tag_is_used_by_a_rule_or_game(self, drills):
        used = {"face_control", "dispersion", "slice", "hook", "path", "over_the_top", "attack_angle_driver",
                "attack_angle_iron", "low_point", "spin_loft", "strike", "distance_control", "wedge_distance",
                "approach", "tempo", "putting_lag", "putting_short", "course_management", "tee_strategy",
                "bogey_strategy", "chipping"}
        for d in drills:
            assert set(d["tags"]) & used, f"drill {d['name']} has no actionable tag"
            assert d.get("where") in ("sim", "home", "course")
            assert d.get("steps")

    def test_plan_structure(self, shots, drills):
        rounds, _ = parse_rounds_csv(ROUNDS.read_bytes())
        sp = evaluate_shots(shots, "right")
        rp = evaluate_rounds(aggregate_rounds(rounds), 85)
        top = top_priorities(sp, rp, k=3)
        summary = club_summary(shots, 5)
        plan = build_weekly_plan(top, summary, drills, load_games(), "right")
        assert len(plan.sessions) == 3
        assert plan.sessions[0].title.startswith("Session 1")
        assert any(b.kind == "game" for b in plan.sessions[1].blocks)
        assert plan.on_course_rule
        assert plan.checks and all("metric" in c for c in plan.checks)
        assert all(s.minutes > 0 for s in plan.sessions)
        # the technical session includes a transfer block with a pass mark
        assert any(b.name.startswith("Transfer") and b.success_metric for b in plan.sessions[0].blocks)

    def test_plan_without_data(self, drills):
        plan = build_weekly_plan([], None, drills, load_games(), "right")
        assert plan.sessions and plan.focus

    def test_plan_roundtrip_store(self, tmp_path, shots, drills):
        plan = build_weekly_plan(evaluate_shots(shots, "right")[:2], club_summary(shots, 5), drills, load_games())
        store = PlanStore(tmp_path)
        assert store.save(plan)
        loaded = store.latest()
        assert loaded.week_of == plan.week_of and len(loaded.sessions) == len(plan.sessions)
        assert loaded.sessions[0].blocks[0].name == plan.sessions[0].blocks[0].name

    def test_evaluate_check(self, shots):
        summary = club_summary(shots, 5)
        chk = {"metric": "ftp_mean", "club": "Driver", "op": "abs<=", "value": 2.5, "label": "x"}
        r = evaluate_check(chk, summary, {})
        assert r["ok"] is False and r["value"] > 2.5
        r2 = evaluate_check({"metric": "penalties", "club": "", "op": "<=", "value": 1.2}, summary, {"penalties": 0.5})
        assert r2["ok"] is True
        r3 = evaluate_check({"metric": "penalties", "club": "", "op": "<=", "value": 1.2}, summary, {})
        assert r3["ok"] is None
