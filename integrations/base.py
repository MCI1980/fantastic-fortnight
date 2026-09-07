# integrations/base.py
# Canonical shot schema shared by importers, storage and analysis.
#
# Every importer (TrackMan CSV today, others later) produces a pandas
# DataFrame whose columns are drawn from SHOT_FIELDS. Analysis code only
# ever sees these canonical names and units, never vendor-specific ones.

from typing import Dict, Tuple

# canonical_name -> (description, unit)
SHOT_FIELDS: Dict[str, Tuple[str, str]] = {
    # Identity
    "date": ("Shot timestamp", "datetime"),
    "club": ("Normalized club name, e.g. '7 Iron'", "text"),
    "raw_club": ("Club name exactly as exported", "text"),
    "club_category": ("Driver / Wood / Hybrid / Long Iron / Mid Iron / Short Iron / Wedge", "text"),
    "shot_number": ("Shot index within the session", "count"),
    "player": ("Player name from the export", "text"),
    "ball_type": ("Ball type from the export", "text"),
    "tags": ("Free-text tags/notes from the export", "text"),

    # Club delivery
    "club_speed_mph": ("Club head speed", "mph"),
    "attack_angle_deg": ("Angle of attack (+ up, - down)", "deg"),
    "club_path_deg": ("Club path (+ in-to-out for RH)", "deg"),
    "face_angle_deg": ("Face angle at impact (+ open/right for RH)", "deg"),
    "face_to_path_deg": ("Face minus path (+ fade side for RH)", "deg"),
    "dynamic_loft_deg": ("Dynamic loft at impact", "deg"),
    "spin_loft_deg": ("Spin loft (dynamic loft minus attack angle)", "deg"),
    "swing_plane_deg": ("Swing plane", "deg"),
    "swing_direction_deg": ("Swing direction", "deg"),
    "low_point_in": ("Low point relative to ball", "in"),
    "impact_height_mm": ("Impact location, vertical", "mm"),
    "impact_offset_mm": ("Impact location, heel/toe", "mm"),

    # Ball launch
    "ball_speed_mph": ("Ball speed", "mph"),
    "smash_factor": ("Ball speed / club speed", "ratio"),
    "launch_angle_deg": ("Vertical launch angle", "deg"),
    "launch_direction_deg": ("Horizontal launch (+ right for RH)", "deg"),
    "spin_rate_rpm": ("Total spin", "rpm"),
    "spin_axis_deg": ("Spin axis tilt (+ fade side for RH)", "deg"),

    # Flight
    "height_yds": ("Max height (apex)", "yds"),
    "carry_yds": ("Carry distance", "yds"),
    "total_yds": ("Total distance", "yds"),
    "side_yds": ("Carry offline (+ right for RH)", "yds"),
    "side_total_yds": ("Total offline (+ right for RH)", "yds"),
    "landing_angle_deg": ("Descent angle", "deg"),
    "hang_time_s": ("Flight time", "s"),
    "curve_yds": ("Curve (+ fade side for RH)", "yds"),

    # Bookkeeping added by storage
    "session_id": ("Import session id (one export file = one session)", "text"),
    "source_file": ("Original file name", "text"),
    "shot_hash": ("Stable hash for de-duplication", "text"),
}

NUMERIC_FIELDS = [
    k for k, (_, unit) in SHOT_FIELDS.items()
    if unit in ("mph", "deg", "in", "mm", "rpm", "yds", "s", "ratio", "count")
]

# Fields whose sign convention flips for left-handed golfers.
# After normalization (see analysis.handedness), positive always means
# "toward the golfer's fade side" so rules can be written once.
SIGNED_FIELDS = [
    "club_path_deg",
    "face_angle_deg",
    "face_to_path_deg",
    "launch_direction_deg",
    "spin_axis_deg",
    "side_yds",
    "side_total_yds",
    "curve_yds",
    "swing_direction_deg",
]

# A row must have at least one of these to count as a real shot.
REQUIRED_ANY = ["carry_yds", "ball_speed_mph", "total_yds"]
