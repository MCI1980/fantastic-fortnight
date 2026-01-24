# video_analysis/metrics.py
# Swing metrics computation from pose data

import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

from .pose import (
    PoseFrame, PoseLandmark,
    NOSE, LEFT_EYE, RIGHT_EYE,
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_HIP, RIGHT_HIP,
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_ELBOW, RIGHT_ELBOW,
    compute_angle_horizontal, compute_distance
)


@dataclass
class SwingPhase:
    """Represents a detected swing phase."""
    name: str  # address, backswing, top, downswing, impact, finish
    frame_idx: int
    timestamp_ms: float
    confidence: float


@dataclass
class SwingMetrics:
    """Computed swing metrics with confidence scores."""
    # Core metrics
    tempo_ratio: Optional[float] = None  # backswing_frames / downswing_frames
    head_sway_cm: Optional[float] = None  # horizontal head movement (estimated)
    head_sway_normalized: Optional[float] = None  # as fraction of shoulder width

    hip_rotation_deg_top: Optional[float] = None  # hip line angle at top
    shoulder_rotation_deg_top: Optional[float] = None  # shoulder line angle at top

    # Additional metrics (may be None if not detected)
    lead_wrist_set_deg_top: Optional[float] = None
    pelvis_slide_cm: Optional[float] = None

    # Confidence flags
    detection_confidence: float = 0.0
    tempo_confidence: float = 0.0
    phases_detected: int = 0

    # Phase info
    address_frame: Optional[int] = None
    top_frame: Optional[int] = None
    impact_frame: Optional[int] = None
    finish_frame: Optional[int] = None

    @property
    def is_valid(self) -> bool:
        """Check if we have enough data for meaningful analysis."""
        return (
            self.detection_confidence > 0.3 and
            self.phases_detected >= 2 and
            self.tempo_ratio is not None
        )


def detect_swing_phases(
    pose_frames: List[PoseFrame],
    handedness: str = "right"
) -> Tuple[List[SwingPhase], Dict[str, int]]:
    """
    Detect swing phases using heuristics based on pose movement.

    Uses:
    - Lead wrist vertical position (highest = top of backswing)
    - Wrist velocity changes (deceleration = impact area)
    - Overall body position stability (address, finish)

    Args:
        pose_frames: List of PoseFrame objects from video
        handedness: "right" or "left" handed golfer

    Returns:
        (list of SwingPhase, dict of phase_name -> frame_idx)
    """
    if not pose_frames:
        return [], {}

    phases = []
    phase_indices = {}

    # Filter to frames with detected poses
    valid_frames = [f for f in pose_frames if f.detected and f.confidence > 0.3]
    if len(valid_frames) < 5:
        return [], {}

    # Lead wrist index (left for right-handed, right for left-handed)
    lead_wrist = LEFT_WRIST if handedness == "right" else RIGHT_WRIST

    # Compute wrist positions over time
    wrist_y = []  # vertical position (lower y = higher in frame)
    wrist_x = []  # horizontal position
    frame_indices = []

    for pf in valid_frames:
        pos = pf.get_landmark_xy(lead_wrist)
        if pos:
            wrist_x.append(pos[0])
            wrist_y.append(pos[1])
            frame_indices.append(pf.frame_idx)

    if len(wrist_y) < 5:
        return [], {}

    wrist_y = np.array(wrist_y)
    wrist_x = np.array(wrist_x)
    frame_indices = np.array(frame_indices)

    # Find top of backswing (lowest y = highest position in frame)
    top_idx_local = np.argmin(wrist_y)
    top_frame_idx = int(frame_indices[top_idx_local])

    # Address: frames before backswing starts (relatively stable wrist)
    # Look at first 20% of frames, find most stable position
    early_end = max(3, len(wrist_y) // 5)
    early_std = [np.std(wrist_y[max(0, i-2):i+3]) for i in range(early_end)]
    address_idx_local = np.argmin(early_std) if early_std else 0
    address_frame_idx = int(frame_indices[address_idx_local])

    # Impact: after top, look for wrist returning to near address height
    # Use velocity change heuristic
    if top_idx_local < len(wrist_y) - 3:
        post_top_y = wrist_y[top_idx_local:]
        post_top_frames = frame_indices[top_idx_local:]

        # Velocity (derivative)
        if len(post_top_y) > 2:
            velocity = np.diff(post_top_y)
            # Impact area: velocity starts to slow down after max speed
            max_vel_idx = np.argmax(np.abs(velocity))
            impact_idx_local = min(top_idx_local + max_vel_idx + 1, len(frame_indices) - 1)
            impact_frame_idx = int(frame_indices[impact_idx_local])
        else:
            impact_frame_idx = int(frame_indices[-2]) if len(frame_indices) > 1 else top_frame_idx
    else:
        impact_frame_idx = int(frame_indices[-1])

    # Finish: last stable position (last 20% of frames)
    late_start = max(0, len(wrist_y) - len(wrist_y) // 5)
    finish_frame_idx = int(frame_indices[-1])

    # Build phase list
    phases = [
        SwingPhase("address", address_frame_idx, valid_frames[address_idx_local].timestamp_ms, 0.7),
        SwingPhase("top", top_frame_idx, valid_frames[top_idx_local].timestamp_ms, 0.8),
        SwingPhase("impact", impact_frame_idx, 0.0, 0.6),
        SwingPhase("finish", finish_frame_idx, valid_frames[-1].timestamp_ms, 0.7),
    ]

    phase_indices = {
        "address": address_frame_idx,
        "top": top_frame_idx,
        "impact": impact_frame_idx,
        "finish": finish_frame_idx,
    }

    return phases, phase_indices


def compute_swing_metrics(
    pose_frames: List[PoseFrame],
    phases: Dict[str, int],
    fps: float = 30.0,
    frame_height_px: int = 1080,
    estimated_shoulder_width_cm: float = 45.0,
    handedness: str = "right"
) -> SwingMetrics:
    """
    Compute swing metrics from pose frames and detected phases.

    Args:
        pose_frames: List of PoseFrame objects
        phases: Dict of phase_name -> frame_idx
        fps: Frames per second of the video
        frame_height_px: Frame height for scaling
        estimated_shoulder_width_cm: Assumed shoulder width for cm estimates
        handedness: "right" or "left" handed golfer

    Returns:
        SwingMetrics with computed values
    """
    metrics = SwingMetrics()

    # Build frame lookup
    frame_lookup = {pf.frame_idx: pf for pf in pose_frames if pf.detected}

    if not phases or not frame_lookup:
        return metrics

    # Get key frames
    address_idx = phases.get("address")
    top_idx = phases.get("top")
    impact_idx = phases.get("impact")
    finish_idx = phases.get("finish")

    metrics.address_frame = address_idx
    metrics.top_frame = top_idx
    metrics.impact_frame = impact_idx
    metrics.finish_frame = finish_idx

    # Count detected phases
    phases_found = sum(1 for k in ["address", "top", "impact", "finish"] if phases.get(k) is not None)
    metrics.phases_detected = phases_found

    # Get pose frames for key phases
    address_pose = frame_lookup.get(address_idx)
    top_pose = frame_lookup.get(top_idx)
    impact_pose = frame_lookup.get(impact_idx)

    # Average detection confidence
    confidences = [pf.confidence for pf in frame_lookup.values()]
    metrics.detection_confidence = np.mean(confidences) if confidences else 0.0

    # === TEMPO RATIO ===
    if address_idx is not None and top_idx is not None and impact_idx is not None:
        backswing_frames = top_idx - address_idx
        downswing_frames = impact_idx - top_idx

        if downswing_frames > 0 and backswing_frames > 0:
            metrics.tempo_ratio = round(backswing_frames / downswing_frames, 2)
            metrics.tempo_confidence = 0.7 if backswing_frames > 3 and downswing_frames > 1 else 0.4

    # === HEAD SWAY ===
    if address_pose and top_pose:
        address_nose = address_pose.get_landmark_xy(NOSE)
        top_nose = top_pose.get_landmark_xy(NOSE)

        if address_nose and top_nose:
            # Horizontal sway in normalized coords
            sway_normalized = abs(top_nose[0] - address_nose[0])
            metrics.head_sway_normalized = round(sway_normalized, 3)

            # Estimate cm using shoulder width as reference
            address_shoulders = (
                address_pose.get_landmark_xy(LEFT_SHOULDER),
                address_pose.get_landmark_xy(RIGHT_SHOULDER)
            )
            if address_shoulders[0] and address_shoulders[1]:
                shoulder_width_norm = abs(address_shoulders[1][0] - address_shoulders[0][0])
                if shoulder_width_norm > 0.01:
                    pixels_per_cm = shoulder_width_norm / estimated_shoulder_width_cm
                    sway_cm = sway_normalized / pixels_per_cm
                    metrics.head_sway_cm = round(sway_cm, 1)

    # === HIP ROTATION AT TOP ===
    if top_pose:
        left_hip = top_pose.get_landmark_xy(LEFT_HIP)
        right_hip = top_pose.get_landmark_xy(RIGHT_HIP)

        if left_hip and right_hip:
            hip_angle = compute_angle_horizontal(left_hip, right_hip)
            # Convert to rotation amount (0 = square, 45 = fully rotated)
            # Positive angle means rotated toward target
            metrics.hip_rotation_deg_top = round(abs(hip_angle), 1)

    # === SHOULDER ROTATION AT TOP ===
    if top_pose:
        left_shoulder = top_pose.get_landmark_xy(LEFT_SHOULDER)
        right_shoulder = top_pose.get_landmark_xy(RIGHT_SHOULDER)

        if left_shoulder and right_shoulder:
            shoulder_angle = compute_angle_horizontal(left_shoulder, right_shoulder)
            metrics.shoulder_rotation_deg_top = round(abs(shoulder_angle), 1)

    # === LEAD WRIST SET (estimated from elbow-wrist angle) ===
    if top_pose:
        lead_elbow = LEFT_ELBOW if handedness == "right" else RIGHT_ELBOW
        lead_wrist = LEFT_WRIST if handedness == "right" else RIGHT_WRIST
        lead_shoulder = LEFT_SHOULDER if handedness == "right" else RIGHT_SHOULDER

        elbow_pos = top_pose.get_landmark_xy(lead_elbow)
        wrist_pos = top_pose.get_landmark_xy(lead_wrist)
        shoulder_pos = top_pose.get_landmark_xy(lead_shoulder)

        if elbow_pos and wrist_pos and shoulder_pos:
            # Compute angle at elbow
            v1 = (shoulder_pos[0] - elbow_pos[0], shoulder_pos[1] - elbow_pos[1])
            v2 = (wrist_pos[0] - elbow_pos[0], wrist_pos[1] - elbow_pos[1])

            dot = v1[0]*v2[0] + v1[1]*v2[1]
            mag1 = np.sqrt(v1[0]**2 + v1[1]**2)
            mag2 = np.sqrt(v2[0]**2 + v2[1]**2)

            if mag1 > 0 and mag2 > 0:
                cos_angle = np.clip(dot / (mag1 * mag2), -1, 1)
                angle_deg = np.degrees(np.arccos(cos_angle))
                # Wrist set is roughly 180 - elbow angle
                wrist_set = 180 - angle_deg
                metrics.lead_wrist_set_deg_top = round(max(0, min(120, wrist_set)), 1)

    # === PELVIS SLIDE (horizontal hip center movement) ===
    if address_pose and top_pose:
        address_hip_l = address_pose.get_landmark_xy(LEFT_HIP)
        address_hip_r = address_pose.get_landmark_xy(RIGHT_HIP)
        top_hip_l = top_pose.get_landmark_xy(LEFT_HIP)
        top_hip_r = top_pose.get_landmark_xy(RIGHT_HIP)

        if address_hip_l and address_hip_r and top_hip_l and top_hip_r:
            address_hip_center_x = (address_hip_l[0] + address_hip_r[0]) / 2
            top_hip_center_x = (top_hip_l[0] + top_hip_r[0]) / 2

            slide_normalized = abs(top_hip_center_x - address_hip_center_x)

            # Convert to cm estimate
            address_shoulders = (
                address_pose.get_landmark_xy(LEFT_SHOULDER),
                address_pose.get_landmark_xy(RIGHT_SHOULDER)
            )
            if address_shoulders[0] and address_shoulders[1]:
                shoulder_width_norm = abs(address_shoulders[1][0] - address_shoulders[0][0])
                if shoulder_width_norm > 0.01:
                    pixels_per_cm = shoulder_width_norm / estimated_shoulder_width_cm
                    slide_cm = slide_normalized / pixels_per_cm
                    metrics.pelvis_slide_cm = round(slide_cm, 1)

    return metrics
