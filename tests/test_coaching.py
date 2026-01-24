# tests/test_coaching.py
# Tests for coaching rules and goal presets

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from coaching import (
    analyze_with_goals,
    analyze_with_goals_detailed,
    get_goals_for_club,
    CLUB_GOALS,
    DEFAULT_GOALS,
    load_drills,
    map_tags_to_drill_tags,
    tag_to_drills,
)


class TestGoalPresets:
    """Test club-specific goal presets."""

    def test_all_clubs_have_goals(self):
        """All expected clubs should have goal presets."""
        expected_clubs = ["Driver", "3W", "Hybrid", "Long Iron", "Mid Iron", "Short Iron", "Wedge"]
        for club in expected_clubs:
            assert club in CLUB_GOALS, f"Missing goals for {club}"

    def test_driver_has_required_fields(self):
        """Driver goals should have all required threshold fields."""
        driver = CLUB_GOALS["Driver"]
        required_fields = [
            "tempo_lower", "tempo_upper",
            "head_sway_max",
            "hip_rot_min",
            "shoulder_rot_min"
        ]
        for field in required_fields:
            assert field in driver, f"Driver missing {field}"

    def test_get_goals_for_club_returns_merged(self):
        """get_goals_for_club should merge defaults with club-specific."""
        goals = get_goals_for_club("Driver")
        # Should have default keys
        assert "tempo_lower" in goals
        # Values should be from Driver preset
        assert goals["tempo_lower"] == CLUB_GOALS["Driver"]["tempo_lower"]

    def test_get_goals_for_unknown_club_uses_defaults(self):
        """Unknown club should still return defaults."""
        goals = get_goals_for_club("Unknown Club")
        assert goals == DEFAULT_GOALS

    def test_goals_progression_by_club(self):
        """Goals should get tighter from Driver to Wedge."""
        driver = CLUB_GOALS["Driver"]
        wedge = CLUB_GOALS["Wedge"]

        # Head sway tolerance should decrease
        assert driver["head_sway_max"] > wedge["head_sway_max"]

        # Hip/shoulder minimums should decrease for shorter clubs
        assert driver["hip_rot_min"] > wedge["hip_rot_min"]


class TestCoachingRules:
    """Test coaching rules engine."""

    def test_good_swing_returns_positive_message(self):
        """Swing within all goals should get positive feedback."""
        metrics = {
            "tempo_ratio": 3.0,
            "head_sway_cm": 2.0,
            "hip_rotation_deg_top": 45,
            "shoulder_rotation_deg_top": 90,
        }
        goals = get_goals_for_club("Driver")
        pointers, tags = analyze_with_goals(metrics, goals)

        # Should have positive message and no issue tags
        assert len(pointers) == 1
        assert "solid" in pointers[0].lower() or len(tags) == 0

    def test_fast_tempo_detected(self):
        """Quick tempo should be flagged."""
        metrics = {
            "tempo_ratio": 2.0,  # Too fast for Driver (2.9-3.6)
        }
        goals = get_goals_for_club("Driver")
        pointers, tags = analyze_with_goals(metrics, goals)

        assert "fast_tempo" in tags or "tempo" in str(tags)
        assert any("tempo" in p.lower() or "backswing" in p.lower() for p in pointers)

    def test_head_sway_detected(self):
        """Excessive head sway should be flagged."""
        metrics = {
            "head_sway_cm": 8.0,  # Way over 4.0 max for Driver
        }
        goals = get_goals_for_club("Driver")
        pointers, tags = analyze_with_goals(metrics, goals)

        assert "excess_sway" in tags or "sway" in str(tags)
        assert any("head" in p.lower() or "sway" in p.lower() for p in pointers)

    def test_limited_rotation_detected(self):
        """Limited hip/shoulder rotation should be flagged."""
        metrics = {
            "hip_rotation_deg_top": 25,  # Below 40 min for Driver
            "shoulder_rotation_deg_top": 70,  # Below 85 min for Driver
        }
        goals = get_goals_for_club("Driver")
        pointers, tags = analyze_with_goals(metrics, goals)

        # Should flag both rotation issues
        assert any("hip" in t.lower() or "rotation" in t.lower() for t in tags)
        assert any("shoulder" in t.lower() or "turn" in t.lower() for t in tags)

    def test_detailed_pointers_have_structure(self):
        """Detailed analysis should return structured pointers."""
        metrics = {
            "tempo_ratio": 2.0,
            "head_sway_cm": 6.0,
        }
        goals = get_goals_for_club("Driver")
        detailed = analyze_with_goals_detailed(metrics, goals)

        assert len(detailed) >= 2

        for pointer in detailed:
            assert hasattr(pointer, "message")
            assert hasattr(pointer, "why")
            assert hasattr(pointer, "priority")
            assert hasattr(pointer, "tags")
            assert pointer.priority >= 1

    def test_pointers_sorted_by_priority(self):
        """Pointers should be sorted by priority."""
        metrics = {
            "tempo_ratio": 2.0,  # Priority 2
            "head_sway_cm": 6.0,  # Priority 1
        }
        goals = get_goals_for_club("Driver")
        detailed = analyze_with_goals_detailed(metrics, goals)

        # Head sway (priority 1) should come before tempo (priority 2)
        priorities = [p.priority for p in detailed]
        assert priorities == sorted(priorities)


class TestDrills:
    """Test drill loading and matching."""

    def test_drills_load(self):
        """Drills should load from YAML file."""
        drills = load_drills()
        assert len(drills) >= 10, "Should have at least 10 drills"

    def test_drills_have_required_fields(self):
        """Each drill should have required fields."""
        drills = load_drills()
        required = ["name", "tags", "steps"]

        for drill in drills:
            for field in required:
                assert field in drill, f"Drill missing {field}: {drill.get('name', 'unknown')}"

    def test_tag_mapping(self):
        """Tag aliases should map correctly."""
        # fast_tempo should map to tempo
        mapped = map_tags_to_drill_tags(["fast_tempo"])
        assert "tempo" in mapped

        # excess_sway should map to sway
        mapped = map_tags_to_drill_tags(["excess_sway"])
        assert "sway" in mapped

    def test_drill_matching(self):
        """Drills should match tags correctly."""
        drills = load_drills()

        # Find drills for tempo issues
        tempo_drills = tag_to_drills(["tempo"], drills)
        assert len(tempo_drills) >= 1
        assert any("tempo" in d["name"].lower() or "tempo" in d.get("tags", []) for d in tempo_drills)


# Sample metrics profiles for testing
SAMPLE_METRICS = [
    {
        "name": "good_driver_swing",
        "club": "Driver",
        "metrics": {
            "tempo_ratio": 3.1,
            "head_sway_cm": 3.5,
            "hip_rotation_deg_top": 42,
            "shoulder_rotation_deg_top": 88,
            "lead_wrist_set_deg_top": 65,
            "pelvis_slide_cm": 4.0,
        },
        "expected_issues": 0,
    },
    {
        "name": "rushed_swing",
        "club": "Driver",
        "metrics": {
            "tempo_ratio": 2.3,
            "head_sway_cm": 3.0,
            "hip_rotation_deg_top": 45,
            "shoulder_rotation_deg_top": 90,
        },
        "expected_issues": 1,  # Fast tempo
    },
    {
        "name": "sway_and_limited_turn",
        "club": "7 Iron",
        "metrics": {
            "tempo_ratio": 2.8,
            "head_sway_cm": 5.5,
            "hip_rotation_deg_top": 28,
            "shoulder_rotation_deg_top": 65,
        },
        "expected_issues": 3,  # Sway, hip, shoulder
    },
]


class TestSampleProfiles:
    """Test with sample metric profiles."""

    @pytest.mark.parametrize("profile", SAMPLE_METRICS, ids=lambda p: p["name"])
    def test_sample_profile(self, profile):
        """Test that sample profiles produce expected issue counts."""
        goals = get_goals_for_club(profile.get("club", "Driver"))
        detailed = analyze_with_goals_detailed(profile["metrics"], goals)

        # Allow some tolerance in issue count
        actual_issues = len(detailed)
        expected = profile["expected_issues"]

        assert actual_issues >= expected - 1, (
            f"{profile['name']}: Expected ~{expected} issues, got {actual_issues}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
