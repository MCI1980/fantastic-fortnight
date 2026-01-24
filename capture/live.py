# capture/live.py
# Real-time video processing for WebRTC live capture

from dataclasses import dataclass
from typing import Tuple, Optional, Literal
import av
import cv2
import time


@dataclass
class FramingStatus:
    """Status of frame composition for golfer positioning."""
    ok: bool
    msg: str
    checks: dict  # Individual check results


def _check_framing(
    frame_h: int,
    frame_w: int,
    bbox: Optional[Tuple[int, int, int, int]],
    angle: str = "FO"
) -> FramingStatus:
    """
    Check if the detected subject is properly framed.

    Args:
        frame_h: Frame height in pixels
        frame_w: Frame width in pixels
        bbox: Bounding box (x1, y1, x2, y2) or None if no subject detected
        angle: "FO" (face-on) or "DTL" (down-the-line)

    Returns:
        FramingStatus with ok flag, guidance message, and individual checks
    """
    checks = {
        "subject_detected": False,
        "centered": False,
        "head_visible": False,
        "feet_visible": False,
        "full_body": False,
    }

    if bbox is None:
        return FramingStatus(
            ok=False,
            msg="Stand in frame",
            checks=checks
        )

    checks["subject_detected"] = True
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    box_height = y2 - y1
    box_width = x2 - x1

    # Center check (allow more flexibility for DTL)
    if angle == "DTL":
        checks["centered"] = frame_w * 0.30 <= cx <= frame_w * 0.70
    else:  # FO
        checks["centered"] = frame_w * 0.35 <= cx <= frame_w * 0.65

    # Head in upper portion
    checks["head_visible"] = y1 < frame_h * 0.18

    # Feet in lower portion
    checks["feet_visible"] = y2 > frame_h * 0.88

    # Full body (reasonable height coverage)
    checks["full_body"] = box_height > frame_h * 0.65

    # Determine overall status
    all_ok = all(checks.values())

    # Generate specific guidance
    if all_ok:
        msg = "Ready to record"
    elif not checks["centered"]:
        msg = "Move to center"
    elif not checks["head_visible"]:
        msg = "Step back - head cut off"
    elif not checks["feet_visible"]:
        msg = "Step back - feet cut off"
    elif not checks["full_body"]:
        msg = "Step back for full body"
    else:
        msg = "Adjust position"

    return FramingStatus(ok=all_ok, msg=msg, checks=checks)


def _draw_guides(img, status: FramingStatus, angle: str = "FO"):
    """
    Draw framing guides and status banner on the image.

    Args:
        img: OpenCV BGR image (numpy array)
        status: FramingStatus indicating if framing is correct
        angle: "FO" or "DTL" for angle-specific guides

    Returns:
        Modified image with overlays
    """
    h, w = img.shape[:2]

    # Colors
    GREEN = (0, 200, 0)
    ORANGE = (0, 165, 255)
    WHITE = (255, 255, 255)
    DARK = (40, 40, 40)

    main_color = GREEN if status.ok else ORANGE

    # Semi-transparent overlay for guide areas
    overlay = img.copy()

    # Draw 3x3 rule-of-thirds grid (subtle)
    grid_color = (100, 100, 100)
    for i in (1, 2):
        x = int(w * i / 3)
        y = int(h * i / 3)
        cv2.line(overlay, (x, 0), (x, h), grid_color, 1)
        cv2.line(overlay, (0, y), (w, y), grid_color, 1)

    # Head zone indicator (top center)
    head_zone = (int(w * 0.30), int(h * 0.02), int(w * 0.70), int(h * 0.18))
    head_color = GREEN if status.checks.get("head_visible") else ORANGE
    cv2.rectangle(overlay, (head_zone[0], head_zone[1]), (head_zone[2], head_zone[3]), head_color, 2)

    # Feet zone indicator (bottom)
    feet_zone = (int(w * 0.15), int(h * 0.88), int(w * 0.85), int(h * 0.98))
    feet_color = GREEN if status.checks.get("feet_visible") else ORANGE
    cv2.rectangle(overlay, (feet_zone[0], feet_zone[1]), (feet_zone[2], feet_zone[3]), feet_color, 2)

    # Center guideline
    center_color = GREEN if status.checks.get("centered") else ORANGE
    cv2.line(overlay, (w // 2, 0), (w // 2, h), center_color, 2)

    # Blend overlay
    cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

    # Status banner at top
    banner_height = 50
    cv2.rectangle(img, (0, 0), (w, banner_height), main_color, -1)

    # Status text
    status_text = "READY" if status.ok else status.msg.upper()
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.9
    thickness = 2

    # Center the text
    (text_w, text_h), _ = cv2.getTextSize(status_text, font, font_scale, thickness)
    text_x = (w - text_w) // 2
    text_y = (banner_height + text_h) // 2

    cv2.putText(img, status_text, (text_x, text_y), font, font_scale, DARK, thickness, cv2.LINE_AA)

    # Angle indicator in corner
    angle_label = f"Angle: {angle}"
    cv2.putText(img, angle_label, (10, h - 15), font, 0.5, WHITE, 1, cv2.LINE_AA)

    # Check indicators (small icons in bottom right)
    icon_size = 15
    icon_y = h - 40
    icon_x_start = w - 100

    check_icons = [
        ("subject_detected", "P"),  # Person
        ("centered", "C"),          # Center
        ("head_visible", "H"),      # Head
        ("feet_visible", "F"),      # Feet
    ]

    for i, (check_key, label) in enumerate(check_icons):
        x = icon_x_start + i * 22
        check_ok = status.checks.get(check_key, False)
        color = GREEN if check_ok else ORANGE
        cv2.circle(img, (x, icon_y), 8, color, -1)
        cv2.putText(img, label, (x - 4, icon_y + 4), font, 0.35, DARK, 1, cv2.LINE_AA)

    return img


class GuideProcessor:
    """
    WebRTC video processor that draws framing guides and status banner.
    Uses background subtraction to detect the golfer's position.
    """

    def __init__(self, angle: str = "FO"):
        """
        Initialize processor.

        Args:
            angle: "FO" (face-on) or "DTL" (down-the-line)
        """
        self.angle = angle
        # Per-instance subtractor
        self._fgbg = cv2.createBackgroundSubtractorMOG2(
            history=50,
            varThreshold=32,
            detectShadows=False
        )
        self._frame_count = 0

    def _estimate_bbox(self, frame) -> Optional[Tuple[int, int, int, int]]:
        """
        Estimate bounding box of the largest moving object (golfer).

        Args:
            frame: OpenCV BGR image

        Returns:
            (x1, y1, x2, y2) bounding box or None
        """
        try:
            mask = self._fgbg.apply(frame)
            mask = cv2.medianBlur(mask, 7)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not cnts:
                return None

            x, y, bw, bh = cv2.boundingRect(max(cnts, key=cv2.contourArea))

            # Filter out very small detections (noise)
            if bw * bh < (frame.shape[0] * frame.shape[1]) * 0.02:
                return None

            return (x, y, x + bw, y + bh)
        except Exception:
            return None

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Process incoming video frame and return with guides overlay."""
        img = frame.to_ndarray(format="bgr24")
        self._frame_count += 1

        # Only run detection every 2nd frame to save CPU
        if self._frame_count % 2 == 0:
            bbox = self._estimate_bbox(img)
            self._last_bbox = bbox
        else:
            bbox = getattr(self, '_last_bbox', None)

        status = _check_framing(img.shape[0], img.shape[1], bbox, self.angle)
        out = _draw_guides(img, status, self.angle)
        return av.VideoFrame.from_ndarray(out, format="bgr24")


class EchoTestProcessor:
    """Minimal processor to confirm camera frames flow (no overlays)."""

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """Process frame with minimal timestamp overlay."""
        img = frame.to_ndarray(format="bgr24")
        h, w = img.shape[:2]
        ts = time.strftime("%H:%M:%S")
        cv2.putText(
            img, f"EchoTest {ts}", (10, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA
        )
        return av.VideoFrame.from_ndarray(img, format="bgr24")


# Factory function for creating angle-specific processors
def create_guide_processor(angle: str = "FO"):
    """Create a GuideProcessor configured for specific angle."""
    return lambda: GuideProcessor(angle=angle)
