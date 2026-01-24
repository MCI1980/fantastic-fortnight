# video_analysis/analyzer.py
# Main video analysis pipeline

import io
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, BinaryIO
from dataclasses import dataclass, field
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None

from .pose import PoseDetector, PoseFrame, LANDMARK_NAMES
from .pose import (
    NOSE, LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_HIP, RIGHT_HIP, LEFT_WRIST, RIGHT_WRIST,
    LEFT_ELBOW, RIGHT_ELBOW, LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE
)
from .metrics import detect_swing_phases, compute_swing_metrics, SwingMetrics


# Skeleton connections for drawing
POSE_CONNECTIONS = [
    # Torso
    (LEFT_SHOULDER, RIGHT_SHOULDER),
    (LEFT_SHOULDER, LEFT_HIP),
    (RIGHT_SHOULDER, RIGHT_HIP),
    (LEFT_HIP, RIGHT_HIP),
    # Left arm
    (LEFT_SHOULDER, LEFT_ELBOW),
    (LEFT_ELBOW, LEFT_WRIST),
    # Right arm
    (RIGHT_SHOULDER, RIGHT_ELBOW),
    (RIGHT_ELBOW, RIGHT_WRIST),
    # Left leg
    (LEFT_HIP, LEFT_KNEE),
    (LEFT_KNEE, LEFT_ANKLE),
    # Right leg
    (RIGHT_HIP, RIGHT_KNEE),
    (RIGHT_KNEE, RIGHT_ANKLE),
]


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    success: bool
    error_message: Optional[str] = None

    # Metrics
    metrics: Optional[SwingMetrics] = None

    # Keyframe images (PIL Image objects)
    keyframes: Dict[str, Any] = field(default_factory=dict)  # phase_name -> PIL Image

    # Raw data for debugging
    total_frames: int = 0
    frames_processed: int = 0
    frames_with_pose: int = 0
    fps: float = 30.0
    duration_sec: float = 0.0

    # Confidence flags
    overall_confidence: str = "low"  # "low", "medium", "high"

    def to_metrics_dict(self) -> Dict[str, Any]:
        """Convert to dict format expected by coaching module."""
        if not self.metrics:
            return {}

        return {
            "tempo_ratio": self.metrics.tempo_ratio,
            "head_sway_cm": self.metrics.head_sway_cm,
            "hip_rotation_deg_top": self.metrics.hip_rotation_deg_top,
            "shoulder_rotation_deg_top": self.metrics.shoulder_rotation_deg_top,
            "lead_wrist_set_deg_top": self.metrics.lead_wrist_set_deg_top,
            "pelvis_slide_cm": self.metrics.pelvis_slide_cm,
        }


def _compute_video_hash(video_data: bytes) -> str:
    """Compute hash of video data for caching."""
    return hashlib.md5(video_data[:1024*1024]).hexdigest()[:16]  # First 1MB


class SwingAnalyzer:
    """
    Main video analysis class.
    Handles video loading, pose detection, and metrics computation.
    """

    # Class-level cache for analysis results
    _cache: Dict[str, AnalysisResult] = {}
    _max_cache_size = 10

    def __init__(
        self,
        target_fps: float = 15.0,
        max_duration_sec: float = 20.0,
        handedness: str = "right"
    ):
        """
        Initialize analyzer.

        Args:
            target_fps: Target FPS for frame extraction (lower = faster)
            max_duration_sec: Maximum video duration to process
            handedness: "right" or "left" handed golfer
        """
        self.target_fps = target_fps
        self.max_duration_sec = max_duration_sec
        self.handedness = handedness
        self._detector: Optional[PoseDetector] = None

    def _get_detector(self) -> PoseDetector:
        """Lazy initialization of pose detector."""
        if self._detector is None:
            self._detector = PoseDetector(static_image_mode=False)
        return self._detector

    def analyze(
        self,
        video_file: BinaryIO,
        angle: str = "FO",
        use_cache: bool = True
    ) -> AnalysisResult:
        """
        Analyze a golf swing video.

        Args:
            video_file: Video file object (from Streamlit uploader)
            angle: "FO" (face-on) or "DTL" (down-the-line)
            use_cache: Whether to use cached results

        Returns:
            AnalysisResult with metrics and keyframes
        """
        if cv2 is None:
            return AnalysisResult(
                success=False,
                error_message="OpenCV not available. Install opencv-python-headless."
            )

        # Read video data
        try:
            video_data = video_file.read()
            video_file.seek(0)  # Reset for potential re-read
        except Exception as e:
            return AnalysisResult(
                success=False,
                error_message=f"Could not read video file: {e}"
            )

        # Check cache
        cache_key = f"{_compute_video_hash(video_data)}_{angle}_{self.handedness}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        # Write to temp file for OpenCV
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_data)
                tmp_path = tmp.name
        except Exception as e:
            return AnalysisResult(
                success=False,
                error_message=f"Could not create temp file: {e}"
            )

        try:
            result = self._analyze_video_file(tmp_path, angle)

            # Cache result
            if use_cache and result.success:
                if len(self._cache) >= self._max_cache_size:
                    # Remove oldest entry
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                self._cache[cache_key] = result

            return result

        finally:
            # Cleanup temp file
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _analyze_video_file(self, video_path: str, angle: str) -> AnalysisResult:
        """Internal: analyze video from file path."""
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return AnalysisResult(
                success=False,
                error_message="Could not open video file. Ensure it's a valid MP4/MOV/AVI."
            )

        try:
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_sec = total_frames / fps if fps > 0 else 0

            # Check duration
            if duration_sec > self.max_duration_sec:
                return AnalysisResult(
                    success=False,
                    error_message=f"Video too long ({duration_sec:.1f}s). Maximum is {self.max_duration_sec}s. Please trim your video."
                )

            if duration_sec < 0.5:
                return AnalysisResult(
                    success=False,
                    error_message="Video too short. Please upload a video at least 0.5 seconds long."
                )

            # Calculate frame sampling
            frame_skip = max(1, int(fps / self.target_fps))

            # Process frames
            detector = self._get_detector()
            pose_frames: List[PoseFrame] = []
            raw_frames: Dict[int, np.ndarray] = {}  # Store frames for keyframe extraction

            frame_idx = 0
            frames_processed = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % frame_skip == 0:
                    # Convert BGR to RGB for MediaPipe
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    timestamp_ms = (frame_idx / fps) * 1000

                    pose_frame = detector.detect(rgb_frame, frame_idx, timestamp_ms)
                    pose_frames.append(pose_frame)

                    # Store raw frame for keyframe extraction
                    raw_frames[frame_idx] = rgb_frame

                    frames_processed += 1

                frame_idx += 1

            # Check if we got any poses
            frames_with_pose = sum(1 for pf in pose_frames if pf.detected)

            if frames_with_pose < 5:
                return AnalysisResult(
                    success=False,
                    error_message="Couldn't detect body pose in video. Tips: ensure full body is visible, use good lighting, avoid baggy clothing.",
                    total_frames=total_frames,
                    frames_processed=frames_processed,
                    frames_with_pose=frames_with_pose,
                    fps=fps,
                    duration_sec=duration_sec
                )

            # Detect swing phases
            phases, phase_indices = detect_swing_phases(pose_frames, self.handedness)

            if not phase_indices.get("top"):
                return AnalysisResult(
                    success=False,
                    error_message="Couldn't detect swing phases. Ensure the video shows a complete swing from address to finish.",
                    total_frames=total_frames,
                    frames_processed=frames_processed,
                    frames_with_pose=frames_with_pose,
                    fps=fps,
                    duration_sec=duration_sec
                )

            # Compute metrics
            frame_height = raw_frames[next(iter(raw_frames))].shape[0] if raw_frames else 1080
            metrics = compute_swing_metrics(
                pose_frames,
                phase_indices,
                fps=fps,
                frame_height_px=frame_height,
                handedness=self.handedness
            )

            # Generate keyframe images
            keyframes = self._generate_keyframes(
                raw_frames, pose_frames, phase_indices, angle
            )

            # Determine confidence level
            if metrics.detection_confidence > 0.6 and metrics.phases_detected >= 3:
                confidence = "high"
            elif metrics.detection_confidence > 0.4 and metrics.phases_detected >= 2:
                confidence = "medium"
            else:
                confidence = "low"

            return AnalysisResult(
                success=True,
                metrics=metrics,
                keyframes=keyframes,
                total_frames=total_frames,
                frames_processed=frames_processed,
                frames_with_pose=frames_with_pose,
                fps=fps,
                duration_sec=duration_sec,
                overall_confidence=confidence
            )

        finally:
            cap.release()

    def _generate_keyframes(
        self,
        raw_frames: Dict[int, np.ndarray],
        pose_frames: List[PoseFrame],
        phase_indices: Dict[str, int],
        angle: str
    ) -> Dict[str, Any]:
        """Generate annotated keyframe images for key phases."""
        if Image is None:
            return {}

        keyframes = {}
        pose_lookup = {pf.frame_idx: pf for pf in pose_frames}

        for phase_name in ["address", "top", "impact"]:
            frame_idx = phase_indices.get(phase_name)
            if frame_idx is None:
                continue

            # Find closest available frame
            closest_idx = min(raw_frames.keys(), key=lambda x: abs(x - frame_idx))
            rgb_frame = raw_frames.get(closest_idx)

            if rgb_frame is None:
                continue

            pose = pose_lookup.get(closest_idx)

            # Create PIL image
            img = Image.fromarray(rgb_frame)
            keyframes[phase_name] = self._draw_pose_overlay(img, pose, phase_name, angle)

        return keyframes

    def _draw_pose_overlay(
        self,
        img: "Image.Image",
        pose: Optional[PoseFrame],
        phase_name: str,
        angle: str
    ) -> "Image.Image":
        """Draw pose skeleton and guide lines on image."""
        if ImageDraw is None:
            return img

        draw = ImageDraw.Draw(img)
        w, h = img.size

        # Draw phase label
        draw.rectangle([(0, 0), (w, 30)], fill=(40, 40, 40))
        draw.text((10, 5), f"{phase_name.upper()} ({angle})", fill=(255, 255, 255))

        if not pose or not pose.detected:
            draw.text((10, h - 30), "No pose detected", fill=(255, 100, 100))
            return img

        landmarks = pose.landmarks

        # Draw skeleton connections
        for start_idx, end_idx in POSE_CONNECTIONS:
            start = pose.get_landmark_xy(start_idx)
            end = pose.get_landmark_xy(end_idx)

            if start and end:
                x1, y1 = int(start[0] * w), int(start[1] * h)
                x2, y2 = int(end[0] * w), int(end[1] * h)
                draw.line([(x1, y1), (x2, y2)], fill=(0, 255, 0), width=3)

        # Draw landmark points
        for idx, lm in enumerate(landmarks):
            if lm.visibility > 0.5:
                x, y = int(lm.x * w), int(lm.y * h)
                r = 5
                draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(255, 200, 0))

        # Draw guide lines based on angle and phase
        if phase_name == "address":
            # Draw head position box
            nose = pose.get_landmark_xy(NOSE)
            if nose:
                nx, ny = int(nose[0] * w), int(nose[1] * h)
                box_size = 40
                draw.rectangle(
                    [(nx - box_size, ny - box_size), (nx + box_size, ny + box_size)],
                    outline=(255, 255, 0),
                    width=2
                )
                draw.text((nx - box_size, ny + box_size + 5), "Head", fill=(255, 255, 0))

        elif phase_name == "top":
            # Draw shoulder and hip lines
            ls = pose.get_landmark_xy(LEFT_SHOULDER)
            rs = pose.get_landmark_xy(RIGHT_SHOULDER)
            lh = pose.get_landmark_xy(LEFT_HIP)
            rh = pose.get_landmark_xy(RIGHT_HIP)

            if ls and rs:
                draw.line(
                    [(int(ls[0]*w), int(ls[1]*h)), (int(rs[0]*w), int(rs[1]*h))],
                    fill=(0, 200, 255),
                    width=4
                )
                draw.text((int(ls[0]*w), int(ls[1]*h) - 15), "Shoulder line", fill=(0, 200, 255))

            if lh and rh:
                draw.line(
                    [(int(lh[0]*w), int(lh[1]*h)), (int(rh[0]*w), int(rh[1]*h))],
                    fill=(255, 100, 255),
                    width=4
                )
                draw.text((int(lh[0]*w), int(lh[1]*h) + 10), "Hip line", fill=(255, 100, 255))

        return img

    def close(self):
        """Release resources."""
        if self._detector:
            self._detector.close()
            self._detector = None


# Convenience function for Streamlit caching
def analyze_swing_video(
    video_file: BinaryIO,
    angle: str = "FO",
    handedness: str = "right",
    target_fps: float = 15.0
) -> AnalysisResult:
    """
    Analyze a golf swing video (convenience function).

    Args:
        video_file: Video file from Streamlit uploader
        angle: "FO" or "DTL"
        handedness: "right" or "left"
        target_fps: Target FPS for processing

    Returns:
        AnalysisResult
    """
    analyzer = SwingAnalyzer(
        target_fps=target_fps,
        handedness=handedness
    )

    try:
        return analyzer.analyze(video_file, angle)
    finally:
        analyzer.close()
