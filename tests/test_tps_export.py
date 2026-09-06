# tests/test_tps_export.py
# Real-world TrackMan Performance Studio "Trackman CSV" export (2026 UI),
# anonymized. Format quirks: "sep=," first line, quoted full-precision
# numbers, a units row in [brackets], carry under "Carry Flat - Length",
# height in feet, empty "(Sim)" duplicate columns, bookkeeping columns.
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis import club_summary, filter_valid, prepare_shots
from coaching import evaluate_shots
from data.shots import ShotStore
from integrations.trackman import parse_trackman_csv

SAMPLE = Path(__file__).parent / "sample_tps_export.csv"


@pytest.fixture(scope="module")
def res():
    return parse_trackman_csv(SAMPLE)


class TestRealExport:
    def test_shot_count_and_clubs(self, res):
        assert res.ok, res.warnings
        assert res.n_shots == 39
        assert res.df["club"].value_counts().to_dict() == {"8 Iron": 22, "5 Iron": 17}
        assert set(res.df["club_category"]) == {"Short Iron", "Long Iron"}

    def test_measured_columns_win_over_sim_duplicates(self, res):
        cm = res.column_map
        assert cm["Carry Flat - Length"] == "carry_yds"
        assert cm["Carry Flat - Side"] == "side_yds"
        assert cm["Est. Total Flat - Length"] == "total_yds"
        assert cm["Est. Total Flat - Side"] == "side_total_yds"
        assert cm["Carry Flat - Land. Angle"] == "landing_angle_deg"
        assert cm["Carry Flat - Time"] == "hang_time_s"
        assert cm["Max Height - Height"] == "height_yds"
        assert cm["Dyn. Loft"] == "dynamic_loft_deg"
        assert cm["Low Point"] == "low_point_in"
        assert cm["Ball"] == "ball_type"
        for sim in ("Carry (Sim)", "Total (Sim)", "Carry Side (Sim)", "Spin Axis (Sim)", "Curve (Sim)"):
            assert sim in res.unmapped_columns

    def test_bookkeeping_columns_ignored_and_pii_dropped(self, res):
        for col in ("Email", "TMD No", "TMD Filename", "Max Height - Dist.", "Carry Flat - Ball Speed", "Spin Rate Type", "Smash Index"):
            assert col in res.unmapped_columns, col
        assert "email" not in res.df.columns
        assert not any("email" in c.lower() for c in res.df.columns)

    def test_units_row_and_conversions(self, res):
        assert res.units["club_speed_mph"] == "mph"
        assert res.units["height_yds"] == "ft"
        assert res.units["curve_yds"] == "ft"
        assert res.units["impact_offset_mm"] == "mm"
        first = res.df.iloc[0]
        assert first["club_speed_mph"] == pytest.approx(90.844, abs=0.01)
        assert first["carry_yds"] == pytest.approx(163.99, abs=0.01)
        assert first["total_yds"] == pytest.approx(167.79, abs=0.01)
        assert first["side_yds"] == pytest.approx(13.74, abs=0.01)
        assert first["height_yds"] == pytest.approx(90.72 / 3, abs=0.02)   # ft -> yds
        assert first["curve_yds"] == pytest.approx(35.89 / 3, abs=0.02)
        assert first["landing_angle_deg"] == pytest.approx(47.42, abs=0.01)
        assert first["hang_time_s"] == pytest.approx(6.05, abs=0.01)
        assert first["spin_loft_deg"] == pytest.approx(30.105, abs=0.01)   # from the column, not derived
        assert first["dynamic_loft_deg"] == pytest.approx(22.114, abs=0.01)

    def test_dates_and_missing_club_data(self, res):
        assert res.df["date"].notna().all()
        assert str(res.df["date"].iloc[0]) == "2026-02-19 16:54:48"
        # shots 2 and 3 had no club data (estimated spin) - numbers stay NaN, shot is kept
        assert np.isnan(res.df["club_speed_mph"].iloc[1])
        assert np.isnan(res.df["attack_angle_deg"].iloc[1])
        assert res.df["carry_yds"].iloc[1] > 170

    def test_ingest_into_store(self, tmp_path):
        store = ShotStore(tmp_path)
        r = store.ingest_path(SAMPLE)
        assert r.ok and r.added == 39
        assert store.ingest_path(SAMPLE).status == "duplicate_file"

    def test_analysis_runs_on_real_data(self, res):
        shots = filter_valid(prepare_shots(res.df, "right"))
        summary = club_summary(shots, min_shots=5)
        assert list(summary.index) == ["5 Iron", "8 Iron"]
        assert summary.loc["8 Iron", "carry_med"] > summary.loc["5 Iron", "carry_med"] - 60
        pointers = evaluate_shots(shots, "right", min_shots=8)
        ids = {(p.club, p.rule_id) for p in pointers}
        # steep, out-to-in 5-iron with a huge spread
        assert ("5 Iron", "path_out_to_in") in ids
        assert ("5 Iron", "dispersion_wide") in ids
        for p in pointers:
            assert p.success_criterion and p.check
