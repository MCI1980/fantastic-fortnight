# capture_guide.py
from typing import Literal, Tuple
from PIL import Image, ImageDraw

Angle = Literal["FO", "DTL"]

FO_DEFAULTS = {
    "height_ft": (3.5, 4.5),     # phone/camera height (about hand height)
    "distance_ft": (8, 12),      # from ball-player area
    "notes": [
        "Camera perpendicular to target line (front-on).",
        "Frame full body: shoes to cap, with a little space above/below.",
        "Place phone on tripod; avoid zoom; use landscape.",
        "60 fps if available; avoid strong backlight.",
    ],
}

DTL_DEFAULTS = {
    "height_ft": (3.5, 4.5),
    "distance_ft": (10, 15),
    "notes": [
        "Camera on hand line (not the ball line), straight behind.",
        "Lens points through hands at address toward target.",
        "Frame full body + club; include some turf behind feet.",
        "Keep horizon level; use landscape; 60 fps if available.",
    ],
}

def get_recs(angle: Angle):
    return FO_DEFAULTS if angle == "FO" else DTL_DEFAULTS

def draw_overlay_grid(img: Image.Image) -> Image.Image:
    """
    Draws a simple 3x3 grid + suggested 'head box' and 'feet margin'.
    This is only for alignment sanity checks (not measurement).
    """
    w, h = img.size
    out = img.copy()
    d = ImageDraw.Draw(out)

    # 3x3 grid
    for i in (1, 2):
        x = w * i / 3
        y = h * i / 3
        d.line([(x, 0), (x, h)], fill=(0, 255, 0), width=2)
        d.line([(0, y), (w, y)], fill=(0, 255, 0), width=2)

    # head box (top middle), feet margin (bottom)
    head_box = [(w*0.35, h*0.05), (w*0.65, h*0.22)]
    feet_margin = [(w*0.10, h*0.92), (w*0.90, h*0.98)]
    d.rectangle(head_box, outline=(255, 200, 0), width=3)
    d.rectangle(feet_margin, outline=(255, 200, 0), width=3)

    # center line (spine alignment hint)
    d.line([(w/2, 0), (w/2, h)], fill=(0, 180, 255), width=2)

    return out