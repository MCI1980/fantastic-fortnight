# tests/test_analysis.py
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import (
    aggregate_rounds,
    bag_gaps,
    benchmark_for,
    classify_shot,
    club_summary,
    club_tendencies,
    consistency_score,
    filter_valid,
    load_games,
    miss_pattern,
    prepare_shots,
    recent_shots,
    score_game,
    strike_quality,
    strokes_lost,
    yardage_card,
)
from integrations.rounds_csv import parse_rounds_csv
from integrations.trackman import parse_trackman_csv

SAMPLE = Path(__file__).parent / "sample_trackman.csv"
ROUNDS = Path(__file__).parent / "sample_rounds.csv"


@pytest.fixture
def shots():
    df = parse_trackman_csv(SAMPLE).df
    return filter_valid(prepare_shots(df, "right"))


class TestPrep:
    def test_left_handed_flips_signs(self):
        df = parse_trackman_csv(SAMPLE).df
        right = prepare_shots(df, "right")
        left = prepare_shots(df, "left")
        assert np.allclose(left["club_path_deg"], -right["club_path_deg"])
        assert np.allclose(left["side_yds"], -right["side_yds"])
        assert np.allclose(left["carry_yds"], right["carry_yds"])

    def test_flip_side_only(self):
        df = parse_trackman_csv(SAMPLE).df
        flipped = prepare_shots(df, "right", flip_side_sign=True)
        assert np.allclose(flipped["side_yds"], -df["side_yds"])
        assert np.allclose(flipped["club_path_deg"], df["club_path_deg"])

    def test_recent_window(self, shots):
        assert len(recent_shots(shots, 60)) == len(shots)
        old = shots.copy()
        old.loc[0, "date"] = pd.Timestamp("2020-01-01")
        assert len(recent_shots(old, 60)) == len(shots) - 1


class TestGapping:
    def test_summary_rows_and_order(self, shots):
        s = club_summary(shots, min_shots=3)
        assert list(s.index) == ["Driver", "7 Iron", "PW"]
        assert s.loc["Driver", "shots"] == 10
        assert 200 < s.loc["Driver", "carry_med"] < 240
        assert s.loc["Driver", "carry_p20"] <= s.loc["Driver", "carry_med"] <= s.loc["Driver", "carry_p80"]
        assert s.loc["Driver", "side_std"] > s.loc["PW", "side_std"]

    def test_min_shots_filter(self, shots):
        assert list(club_summary(shots, min_shots=9).index) == ["Driver", "7 Iron"]

    def test_bag_gaps(self, shots):
        gaps = bag_gaps(club_summary(shots, 3))
        assert len(gaps) == 2
        assert gaps.iloc[0]["from_club"] == "Driver" and gaps.iloc[0]["status"] == "gap"
        assert gaps.iloc[1]["status"] == "gap"  # 7i -> PW is ~35 yds with two clubs missing

    def test_yardage_card(self, shots):
        card = yardage_card(club_summary(shots, 3), "right")
        assert list(card["Club"]) == ["Driver", "7 Iron", "PW"]
        assert card.iloc[0]["Miss"].endswith("R")
        assert card.iloc[0]["Safe"] <= card.iloc[0]["Plan"] <= card.iloc[0]["Max"]

    def test_consistency_score_scale(self):
        assert consistency_score(4, 170, 6) > consistency_score(8, 150, 12) > consistency_score(15, 230, 25)
        assert 0 <= consistency_score(40, 100, 60) <= 100
        assert np.isnan(consistency_score(5, np.nan, 5))


class TestTendencies:
    @pytest.mark.parametrize("face,ftp,label", [
        (0, 0, "straight"), (3, 0, "push"), (-3, 0, "pull"),
        (0, 3, "fade"), (0, 6, "slice"), (0, -3, "draw"), (0, -6, "hook"),
        (-3, 6, "pull-slice"), (3, -6, "push-hook"), (np.nan, 1, "unknown"),
    ])
    def test_classify(self, face, ftp, label):
        assert classify_shot(face, ftp)[2] == label

    def test_driver_pattern_is_slice(self, shots):
        t = club_tendencies(shots, "Driver")
        assert t["n"] == 10
        assert "slice" in t["top_miss"] or "fade" in t["top_miss"]
        assert t["ftp_mean"] > 3

    def test_strike_quality(self, shots):
        sq = strike_quality(shots, "7 Iron")
        assert sq["n"] == 10 and 1.25 < sq["smash_mean"] < 1.4
        assert 0 <= sq["pct_solid"] <= 100

    def test_miss_pattern_sums_to_100(self, shots):
        p = miss_pattern(shots[shots["club"] == "PW"])
        assert abs(p["pct"].sum() - 100) <= 2


class TestScoring:
    @pytest.fixture
    def rounds(self):
        rounds, warns = parse_rounds_csv(ROUNDS.read_bytes(), "sample_rounds.csv")
        assert len(rounds) == 2, warns
        return rounds

    def test_parse_rounds(self, rounds):
        r = sorted(rounds, key=lambda r: r.date)[0]
        assert r.date == "2026-08-24" and r.course == "Pine Ridge" and r.tees == "White"
        assert r.holes_played == 18 and r.total == 89 and r.par == 72
        assert r.putts == 39 and r.three_putts == 4 and r.penalties == 4
        assert r.fir_opps == 14 and r.gir_opps == 18

    def test_aggregate_and_strokes_lost(self, rounds):
        agg = aggregate_rounds(rounds)
        assert agg["n_rounds"] == 2
        assert 85 < agg["score"] < 92
        sl = strokes_lost(agg, 85)
        assert not sl.empty
        cats = list(sl["category"])
        assert cats[0] in ("Penalty strokes / round", "Three-putts / round")
        assert (sl["est_strokes"] >= 0).all()

    def test_benchmark_interpolation(self):
        b85, b87, b90 = benchmark_for(85), benchmark_for(87), benchmark_for(90)
        assert b85["putts"] < b87["putts"] < b90["putts"]
        assert benchmark_for(60) == benchmark_for(75)
        assert benchmark_for(120) == benchmark_for(100)

    def test_rounds_csv_needs_hole_and_score(self):
        rounds, warns = parse_rounds_csv(b"a,b\n1,2\n", "x.csv")
        assert rounds == [] and warns


class TestGames:
    def test_games_load(self):
        games = load_games()
        assert len(games) >= 5
        assert all({"id", "name", "metric", "rule", "shots"} <= set(g) for g in games)

    def test_score_fairway_finder(self, shots):
        games = load_games()
        ff = next(g for g in games if g["id"] == "fairway_finder")
        res = score_game(ff, shots, "Driver")
        assert res["ready"] and res["max_points"] == 10
        assert res["points"] == int((shots[shots["club"] == "Driver"]["side_yds"].abs() <= 20).sum())

    def test_score_smash_ten(self, shots):
        games = load_games()
        g = next(x for x in games if x["id"] == "smash_ten")
        res = score_game(g, shots, "7 Iron")
        assert 0 <= res["points"] <= 10 and res["ready"]

    def test_not_ready_with_few_shots(self, shots):
        games = load_games()
        g = next(x for x in games if x["id"] == "distance_control")
        res = score_game(g, shots, "PW")
        assert res["shots_used"] == 8 and not res["ready"]
