# video_analysis/pose.py
# MediaPipe Pose detection wrapper

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any

# Landmark indices for key body parts (MediaPipe Pose)
# See: https://google.github.io/mediapipe/solutions/pose.html
LANDMARK_NAMES = {
    0: "nose",
    1: "left_eye_inner",
    2: "left_eye",
    3: "left_eye_outer",
    4: "right_eye_inner",
    5: "right_eye",
    6: "right_eye_outer",
    7: "left_ear",
    8: "right_ear",
    9: "mouth_left",
    10: "mouth_right",
    11: "left_shoulder",
    12: "right_shoulder",
    13: "left_elbow",
    14: "right_elbow",
    15: "left_wrist",
    16: "right_wrist",
    17: "left_pinky",
    18: "right_pinky",
    19: "left_index",
    20: "right_index",
    21: "left_thumb",
    22: "right_thumb",
    23: "left_hip",
    24: "right_hip",
    25: "left_knee",
    26: "right_knee",
    27: "left_ankle",
    28: "right_ankle",
    29: "left_heel",
    30: "right_heel",
    31: "left_foot_index",
    32: "right_foot_index",
}

# Key landmark indices we use for golf analysis
NOSE = 0
LEFT_EYE = 2
RIGHT_EYE = 5
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28


@dataclass
class PoseLandmark:
    """Single pose landmark with coordinates and visibility."""
    x: float  # normalized 0-1, left to right
    y: float  # normalized 0-1, top to bottom
    z: float  # depth, smaller is closer to camera
    visibility: float  # confidence 0-1


@dataclass
class PoseFrame:
    """Pose detection result for a single frame."""
    frame_idx: int
    timestamp_ms: float
    landmarks: Optional[List[PoseLandmark]] = None
    confidence: float = 0.0

    @property
    def detected(self) -> bool:
        return self.landmarks is not None and len(self.landmarks) > 0

    def get_landmark(self, idx: int) -> Optional[PoseLandmark]:
        if self.landmarks and 0 <= idx < len(self.landmarks):
            return self.landmarks[idx]
        return None

    def get_landmark_xy(self, idx: int) -> Optional[Tuple[float, float]]:
        """Get (x, y) normalized coordinates for a landmark."""
        lm = self.get_landmark(idx)
        if lm and lm.visibility > 0.5:
            return (lm.x, lm.y)
        return None


class PoseDetector:
    """
    Wrapper for MediaPipe Pose detection.
    Handles initialization, inference, and cleanup.
    """

    def __init__(self, static_image_mode: bool = False, min_detection_confidence: float = 0.5):
        """
        Initialize pose detector.

        Args:
            static_image_mode: True for independent images, False for video (tracking)
            min_detection_confidence: Minimum confidence for detection (0-1)
        """
        self._mp_pose = None
        self._pose = None
        self._static_mode = static_image_mode
        self._min_confidence = min_detection_confidence
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of MediaPipe."""
        if self._initialized:
            return

        try:
            import mediapipe as mp
            self._mp_pose = mp.solutions.pose
            self._pose = self._mp_pose.Pose(
                static_image_mode=self._static_mode,
                model_complexity=1,  # 0=lite, 1=full, 2=heavy
                min_detection_confidence=self._min_confidence,
                min_tracking_confidence=0.5,
            )
            self._initialized = True
        except ImportError:
            raise RuntimeError("MediaPipe not installed. Run: pip install mediapipe")

    def detect(self, frame_rgb: np.ndarray, frame_idx: int = 0, timestamp_ms: float = 0.0) -> PoseFrame:
        """
        Detect pose in a single frame.

        Args:
            frame_rgb: RGB image as numpy array (H, W, 3)
            frame_idx: Frame index in video
            timestamp_ms: Timestamp in milliseconds

        Returns:
            PoseFrame with detected landmarks or None
        """
        self._ensure_initialized()

        try:
            results = self._pose.process(frame_rgb)

            if results.pose_landmarks:
                landmarks = []
                total_visibility = 0.0

                for lm in results.pose_landmarks.landmark:
                    landmarks.append(PoseLandmark(
                        x=lm.x,
                        y=lm.y,
                        z=lm.z,
                        visibility=lm.visibility
                    ))
                    total_visibility += lm.visibility

                avg_visibility = total_visibility / len(landmarks) if landmarks else 0.0

                return PoseFrame(
                    frame_idx=frame_idx,
                    timestamp_ms=timestamp_ms,
                    landmarks=landmarks,
                    confidence=avg_visibility
                )
            else:
                return PoseFrame(
                    frame_idx=frame_idx,
                    timestamp_ms=timestamp_ms,
                    landmarks=None,
                    confidence=0.0
                )

        except Exception as e:
            return PoseFrame(
                frame_idx=frame_idx,
                timestamp_ms=timestamp_ms,
                landmarks=None,
                confidence=0.0
            )

    def close(self):
        """Release MediaPipe resources."""
        if self._pose:
            self._pose.close()
            self._pose = None
        self._initialized = False


def compute_angle_horizontal(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Compute angle of line p1-p2 relative to horizontal (degrees).
    Returns angle in range [-90, 90].
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    if abs(dx) < 1e-6:
        return 90.0 if dy > 0 else -90.0

    angle_rad = np.arctan2(dy, dx)
    angle_deg = np.degrees(angle_rad)

    # Normalize to [-90, 90]
    if angle_deg > 90:
        angle_deg = 180 - angle_deg
    elif angle_deg < -90:
        angle_deg = -180 - angle_deg

    return angle_deg


def compute_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Compute Euclidean distance between two points."""
    return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
