# live_capture.py
from dataclasses import dataclass
from typing import Tuple
import av
import cv2
import time

@dataclass
class FramingStatus:
    ok: bool
    msg: str

def _check_framing(frame_h, frame_w, bbox: Tuple[int,int,int,int] | None) -> FramingStatus:
    if bbox is None:
        return FramingStatus(False, "No subject detected. Stand fully in frame.")
    x1,y1,x2,y2 = bbox
    cx = (x1 + x2) / 2
    center_ok = frame_w * 0.40 <= cx <= frame_w * 0.60
    head_ok   = y1 <  frame_h * 0.15
    feet_ok   = y2 >  frame_h * 0.90
    ok = center_ok and head_ok and feet_ok
    msg = "Framing looks good." if ok else "Adjust: center yourself, include head and feet."
    return FramingStatus(ok, msg)

def _draw_guides(img, status: FramingStatus):
    h, w = img.shape[:2]
    # 3x3 grid
    for i in (1, 2):
        x = int(w * i / 3); y = int(h * i / 3)
        cv2.line(img, (x, 0), (x, h), (0, 255, 0), 2)
        cv2.line(img, (0, y), (w, y), (0, 255, 0), 2)
    # head box & feet margin
    head = (int(w*0.35), int(h*0.05), int(w*0.65), int(h*0.22))
    feet = (int(w*0.10), int(h*0.92), int(w*0.90), int(h*0.98))
    color = (0, 200, 0) if status.ok else (0, 165, 255)
    cv2.rectangle(img, (head[0], head[1]), (head[2], head[3]), color, 3)
    cv2.rectangle(img, (feet[0], feet[1]), (feet[2], feet[3]), color, 3)
    banner = "OK" if status.ok else "ADJUST FRAMING"
    cv2.rectangle(img, (0, 0), (w, 40), color, -1)
    cv2.putText(img, banner, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    return img

class GuideProcessor:
    """Draws guides and green banner when framing is good."""
    def __init__(self):
        # Per-instance subtractor (safer than a module-global)
        self._fgbg = cv2.createBackgroundSubtractorMOG2(history=50, varThreshold=32, detectShadows=False)

    def _estimate_bbox(self, frame):
        try:
            mask = self._fgbg.apply(frame)
            mask = cv2.medianBlur(mask, 7)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                return None
            x, y, w, h = cv2.boundingRect(max(cnts, key=cv2.contourArea))
            if w * h < (frame.shape[0] * frame.shape[1]) * 0.02:
                return None
            return (x, y, x + w, y + h)
        except Exception:
            return None

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        bbox = self._estimate_bbox(img)
        status = _check_framing(img.shape[0], img.shape[1], bbox)
        out = _draw_guides(img, status)
        return av.VideoFrame.from_ndarray(out, format="bgr24")

class EchoTestProcessor:
    """Minimal processor to confirm camera frames flow (no overlays)."""
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        h, w = img.shape[:2]
        ts = time.strftime("%H:%M:%S")
        cv2.putText(img, f"EchoTest {ts}", (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        return av.VideoFrame.from_ndarray(img, format="bgr24")