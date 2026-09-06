# data/settings.py
# Persistent app settings (JSON file in the data folder).

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


def default_data_dir() -> Path:
    """Where shots/rounds/settings live. Override with GOLF_DATA_DIR."""
    env = os.environ.get("GOLF_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent / "store"


@dataclass
class Settings:
    export_folder: str = ""            # TrackMan CSV export folder to auto-scan
    handedness: str = "right"          # "right" | "left"
    target_score: int = 85             # scoring goal used for benchmarks
    player_name: str = ""
    auto_scan: bool = True             # scan export folder on app load
    flip_side_sign: bool = False       # set if your export reports left as positive
    recent_days: int = 60              # window for "current" numbers
    min_shots_per_club: int = 5        # minimum shots before a club shows in the yardage card

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Settings":
        known = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)


class SettingsStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.path = self.data_dir / "settings.json"

    def load(self) -> Settings:
        try:
            if self.path.exists():
                return Settings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            pass
        return Settings()

    def save(self, settings: Settings) -> bool:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
            return True
        except Exception:
            return False
