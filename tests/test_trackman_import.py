# tests/test_trackman_import.py
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.trackman import (
    club_category,
    club_sort_key,
    map_columns,
    normalize_club,
    parse_number,
    parse_trackman_csv,
)

SAMPLE = Path(__file__).parent / "sample_trackman.csv"
SAMPLE_METRIC = Path(__file__).parent / "sample_trackman_metric.csv"


class TestClubNames:
    @pytest.mark.parametrize("raw,expected", [
        ("Driver", "Driver"), ("dr", "Driver"), ("1W", "Driver"),
        ("3W", "3 Wood"), ("3 wood", "3 Wood"), ("Wood 5", "5 Wood"),
        ("4H", "4 Hybrid"), ("Hybrid", "Hybrid"), ("3 rescue", "3 Hybrid"),
        ("7i", "7 Iron"), ("Iron 7", "7 Iron"), ("7-Iron", "7 Iron"), ("7 iron", "7 Iron"),
        ("PW", "PW"), ("Pitching Wedge", "PW"), ("Gap Wedge", "GW"), ("AW", "GW"),
        ("SW", "SW"), ("Sand Wedge", "SW"), ("LW", "LW"), ("lob wedge", "LW"),
        ("56", "56° Wedge"), ("52 deg", "52° Wedge"), ("60°", "60° Wedge"),
        ("", "Unknown"), (None, "Unknown"),
    ])
    def test_normalize(self, raw, expected):
        assert normalize_club(raw) == expected

    def test_sort_order(self):
        clubs = ["PW", "7 Iron", "Driver", "3 Wood", "SW", "4 Hybrid", "5 Iron", "56° Wedge", "LW"]
        ordered = sorted(clubs, key=club_sort_key)
        assert ordered == ["Driver", "3 Wood", "4 Hybrid", "5 Iron", "7 Iron", "PW", "SW", "56° Wedge", "LW"]

    def test_categories(self):
        assert club_category("Driver") == "Driver"
        assert club_category("3 Wood") == "Wood"
        assert club_category("4 Iron") == "Long Iron"
        assert club_category("7 Iron") == "Mid Iron"
        assert club_category("9 Iron") == "Short Iron"
        assert club_category("PW") == "Wedge"
        assert club_category("56° Wedge") == "Wedge"


class TestNumbers:
    @pytest.mark.parametrize("raw,expected", [
        ("5.2", 5.2), ("5,2", 5.2), ("-3.1", -3.1),
        ("5.2 R", 5.2), ("R 5.2", 5.2), ("3.1 L", -3.1), ("L3.1", -3.1),
        ("142.3 mph", 142.3), ("-", np.nan), ("", np.nan), (None, np.nan), ("abc", np.nan),
    ])
    def test_parse_number(self, raw, expected):
        got = parse_number(raw)
        if isinstance(expected, float) and np.isnan(expected):
            assert np.isnan(got)
        else:
            assert got == pytest.approx(expected)


class TestColumnMapping:
    def test_maps_common_headers(self):
        headers = ["Shot", "Date", "Club", "Club Speed", "Attack Angle", "Club Path", "Face Angle",
                   "Face To Path", "Ball Speed", "Smash Factor", "Launch Angle", "Spin Rate", "Carry", "Total", "Side", "Side Total", "Height", "Land Angle"]
        mapping, units, unmapped = map_columns(headers)
        assert mapping["Club Speed"] == "club_speed_mph"
        assert mapping["Face To Path"] == "face_to_path_deg"
        assert mapping["Side"] == "side_yds"
        assert mapping["Side Total"] == "side_total_yds"
        assert mapping["Land Angle"] == "landing_angle_deg"
        assert mapping["Height"] == "height_yds"
        assert unmapped == []

    def test_units_in_header(self):
        mapping, units, _ = map_columns(["Carry (m)", "Club Speed [km/h]", "Spin Rate (rpm)"])
        assert units["carry_yds"] == "m"
        assert units["club_speed_mph"] == "kmh"

    def test_duplicate_header_goes_unmapped(self):
        mapping, _, unmapped = map_columns(["Carry", "Carry Distance"])
        assert mapping == {"Carry": "carry_yds"}
        assert unmapped == ["Carry Distance"]


class TestParseSample:
    def test_parses_shots_and_drops_summary_rows(self):
        res = parse_trackman_csv(SAMPLE)
        assert res.ok
        assert res.n_shots == 28
        assert set(res.df["club"]) == {"Driver", "7 Iron", "PW"}
        assert res.delimiter == ","
        # units row consumed, preamble skipped, summary rows dropped
        assert res.df["carry_yds"].between(100, 240).all()

    def test_side_signs_and_units(self):
        res = parse_trackman_csv(SAMPLE)
        d = res.df[res.df["club"] == "Driver"]
        assert (d["side_yds"] > 0).sum() == 9          # nine "R" shots
        assert (d["side_yds"] < 0).sum() == 1          # one "L" shot
        assert res.df["date"].notna().all()
        assert res.df["date"].min().year == 2026

    def test_derived_and_categories(self):
        res = parse_trackman_csv(SAMPLE)
        assert "club_category" in res.df.columns
        assert set(res.df["club_category"]) == {"Driver", "Mid Iron", "Wedge"}
        assert "spin_loft_deg" in res.df.columns   # derived from dynamic loft - attack

    def test_bytes_input(self):
        res = parse_trackman_csv(SAMPLE.read_bytes(), source_name="x.csv")
        assert res.ok and res.n_shots == 28 and res.source_name == "x.csv"

    def test_metric_semicolon_export(self):
        res = parse_trackman_csv(SAMPLE_METRIC)
        assert res.ok
        assert res.n_shots == 4
        assert res.delimiter == ";"
        # km/h -> mph, m -> yds, comma decimals
        assert res.df["club_speed_mph"].iloc[0] == pytest.approx(128.7 * 0.621371, rel=1e-3)
        assert res.df["carry_yds"].iloc[0] == pytest.approx(135.3 * 1.093613, rel=1e-3)
        assert res.df["side_yds"].iloc[3] < 0
        # smash factor derived when absent
        assert res.df["smash_factor"].between(1.2, 1.5).all()
        assert res.df["date"].notna().all()

    def test_garbage_file(self):
        res = parse_trackman_csv(b"hello\nworld\n", source_name="bad.csv")
        assert not res.ok
        assert res.warnings
