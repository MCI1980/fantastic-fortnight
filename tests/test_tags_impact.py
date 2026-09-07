# tests/test_tags_impact.py
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import (
    club_summary,
    filter_valid,
    impact_summary,
    load_games,
    match_game,
    prepare_shots,
    shot_role,
    split_tags,
    stats_shots,
    tagged_game_results,
)
from coaching import evaluate_club, evaluate_shots, get_pointer_drills, load_drills
from integrations.trackman import parse_trackman_csv

SAMPLE = Path(__file__).parent / "sample_trackman.csv"
REAL = Path(__file__).parent / "sample_tps_export.csv"


class TestTags:
    @pytest.mark.parametrize("raw,expected", [
        ("", "normal"), (None, "normal"), (np.nan, "normal"), ("nan", "normal"),
        ("drill", "drill"), ("Drill: gate", "drill"), ("warm-up", "warmup"), ("Warmup", "warmup"),
        ("game", "game"), ("game: fairway finder", "game"), ("stock, game", "game"), ("range", "normal"),
    ])
    def test_shot_role(self, raw, expected):
        assert shot_role(raw) == expected

    def test_split_tags(self):
        assert split_tags("Drill; Gate | game: smash ten") == ["drill", "gate", "game: smash ten"]

    def test_stats_shots_excludes_drill_and_warmup(self):
        df = parse_trackman_csv(SAMPLE).df
        df["tags"] = ""
        df.loc[df["club"] == "PW", "tags"] = "warmup"
        df.loc[df.index[:3], "tags"] = "drill: gate"
        shots = filter_valid(prepare_shots(df, "right"))
        assert set(shots["role"]) == {"normal", "drill", "warmup"}
        kept = stats_shots(shots)
        assert "PW" not in set(kept["club"])
        assert len(kept) == len(shots) - 8 - 3
        assert "PW" not in club_summary(kept, 1).index

    def test_missing_tags_column_means_normal(self):
        df = parse_trackman_csv(SAMPLE).df.drop(columns=["tags"], errors="ignore")
        shots = prepare_shots(df, "right")
        assert (shots["role"] == "normal").all()


class TestGameTags:
    @pytest.fixture
    def games(self):
        return load_games()

    def test_match_game(self, games):
        assert match_game("game: fairway finder", games)["id"] == "fairway_finder"
        assert match_game("game-smash_ten", games)["id"] == "smash_ten"
        assert match_game("Face Control", games)["id"] == "face_control"
        assert match_game("game: distance", games)["id"] == "distance_control"
        assert match_game("game", games) is None
        assert match_game("game: nonsense", games) is None

    def test_tagged_named_game_scores_that_game(self, games):
        df = parse_trackman_csv(SAMPLE).df
        df["tags"] = ""
        df.loc[df["club"] == "Driver", "tags"] = "game: fairway finder"
        shots = filter_valid(prepare_shots(df, "right"))
        shots["session_id"] = "s1"
        results = tagged_game_results(shots, games)
        assert len(results) == 1
        r = results[0]
        assert r["game_id"] == "fairway_finder" and r["club"] == "Driver" and r["named"]
        expected = int((shots[shots["club"] == "Driver"]["side_yds"].abs() <= 20).sum())
        assert r["points"] == expected and r["ready"]

    def test_bare_game_tag_scores_every_applicable_game(self, games):
        df = parse_trackman_csv(SAMPLE).df
        df["tags"] = ""
        df.loc[df["club"] == "7 Iron", "tags"] = "game"
        shots = filter_valid(prepare_shots(df, "right"))
        shots["session_id"] = "s1"
        results = tagged_game_results(shots, games)
        ids = {r["game_id"] for r in results}
        assert {"face_control", "smash_ten", "distance_control", "down_and_through"} <= ids
        assert "fairway_finder" not in ids
        assert all(not r["named"] for r in results)

    def test_game_shots_still_count_for_stats(self):
        df = parse_trackman_csv(SAMPLE).df
        df["tags"] = "game"
        shots = filter_valid(prepare_shots(df, "right"))
        assert len(stats_shots(shots)) == len(shots)


def _row(**kw) -> pd.Series:
    base = {"shots": 12, "carry_med": 150.0, "carry_std": 6.0, "carry_cv": 0.04, "side_std": 8.0,
            "ftp_mean": 0.5, "ftp_std": 2.0, "path_mean": 1.0, "attack_mean": -3.0, "spin_mean": 6500.0,
            "launch_mean": 18.0, "smash_mean": 1.37, "smash_std": 0.03, "spin_loft_mean": 21.0,
            "impact_n": 10, "impact_offset_mean": 0.0, "impact_offset_std": 6.0, "impact_height_mean": -2.0}
    base.update(kw)
    return pd.Series(base)


class TestImpactRules:
    def test_centre_strike_no_rule(self):
        assert [p.rule_id for p in evaluate_club("7 Iron", _row())] == []

    def test_heel_and_low(self):
        ids = [p.rule_id for p in evaluate_club("8 Iron", _row(impact_offset_mean=-11, impact_height_mean=-12))]
        assert "strike_heel" in ids and "strike_low_face" in ids

    def test_toe(self):
        ps = evaluate_club("8 Iron", _row(impact_offset_mean=+11))
        assert [p.rule_id for p in ps] == ["strike_toe"]
        assert "toe" in ps[0].message

    def test_scatter_only_without_bias(self):
        ids = [p.rule_id for p in evaluate_club("8 Iron", _row(impact_offset_std=15))]
        assert ids == ["strike_scatter"]

    def test_driver_low_threshold_is_tighter(self):
        assert "strike_low_face" in [p.rule_id for p in evaluate_club("Driver", _row(impact_height_mean=-7, attack_mean=1, spin_mean=2600, launch_mean=12, smash_mean=1.47, side_std=15))]
        assert "strike_low_face" not in [p.rule_id for p in evaluate_club("8 Iron", _row(impact_height_mean=-7))]

    def test_needs_six_shots_with_impact_data(self):
        assert evaluate_club("8 Iron", _row(impact_n=4, impact_offset_mean=-15)) == []

    def test_drills_exist_for_impact_rules(self):
        drills = load_drills()
        for p in evaluate_club("8 Iron", _row(impact_offset_mean=-11, impact_height_mean=-12)):
            names = [d["name"] for d in get_pointer_drills(p, drills)]
            assert names, p.rule_id
        toe = evaluate_club("8 Iron", _row(impact_offset_mean=+11))[0]
        assert any("Toe" in d["name"] for d in get_pointer_drills(toe, drills))


@pytest.fixture(scope="module")
def real_shots():
    return filter_valid(prepare_shots(parse_trackman_csv(REAL).df, "right"))


class TestImpactOnRealExport:
    @pytest.fixture
    def shots(self, real_shots):
        return real_shots

    def test_summary_and_map(self, shots):
        # Real 8-iron set: 14 shots with impact data, ~centre heel-toe, ~6 mm high
        imp = impact_summary(shots, "8 Iron")
        assert imp["n"] == 14
        assert abs(imp["offset_mean"]) < 4
        assert imp["vertical"] == "high" and 4 < imp["height_mean"] < 9
        assert imp["label"] == "6 mm high"
        assert list(imp["points"].columns) == ["Heel (-)  →  Toe (+)  mm", "Low (-)  →  High (+)  mm"]
        assert len(imp["points"]) == imp["n"]

    def test_no_false_bias_rules_on_real_data(self, shots):
        ids = {p.rule_id for p in evaluate_shots(shots, "right", min_shots=8)}
        assert not ids & {"strike_heel", "strike_toe", "strike_low_face", "strike_scatter"}
        summary = club_summary(shots, 5)
        assert (summary["impact_n"] >= 10).all()

    def test_no_impact_data_no_rules(self):
        shots = filter_valid(prepare_shots(parse_trackman_csv(SAMPLE).df, "right"))
        assert impact_summary(shots, "Driver")["n"] == 0
        assert not any(p.rule_id.startswith("strike_") and p.rule_id not in ("strike_low", "strike_inconsistent")
                       for p in evaluate_shots(shots, "right"))
