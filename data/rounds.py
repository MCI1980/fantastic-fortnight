# data/rounds.py
# Round storage: hole-by-hole results for on-course rounds (JSONL).

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.settings import default_data_dir


@dataclass
class HoleResult:
    hole: int
    par: int
    score: int
    putts: Optional[int] = None
    fir: Optional[bool] = None          # None = not applicable (par 3) / unknown
    gir: Optional[bool] = None
    penalties: int = 0
    sand: Optional[bool] = None
    up_and_down: Optional[bool] = None  # None = no scramble attempt / unknown

    @property
    def to_par(self) -> int:
        return self.score - self.par


@dataclass
class Round:
    id: str
    date: str                   # YYYY-MM-DD
    course: str
    tees: str
    holes: List[HoleResult]
    source: str = "manual"
    notes: str = ""
    created_at: str = ""

    @classmethod
    def create(cls, date: str, course: str, holes: List[HoleResult], tees: str = "", source: str = "manual", notes: str = "") -> "Round":
        key = f"{date}|{course}|{tees}|{len(holes)}|{sum(h.score for h in holes)}"
        rid = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return cls(id=rid, date=date, course=course, tees=tees, holes=holes, source=source, notes=notes, created_at=datetime.now().isoformat())

    # ----- derived stats ---------------------------------------------------

    @property
    def holes_played(self) -> int:
        return len(self.holes)

    @property
    def total(self) -> int:
        return sum(h.score for h in self.holes)

    @property
    def par(self) -> int:
        return sum(h.par for h in self.holes)

    @property
    def to_par(self) -> int:
        return self.total - self.par

    @property
    def putts(self) -> Optional[int]:
        vals = [h.putts for h in self.holes if h.putts is not None]
        return sum(vals) if vals else None

    @property
    def three_putts(self) -> int:
        return sum(1 for h in self.holes if h.putts is not None and h.putts >= 3)

    @property
    def penalties(self) -> int:
        return sum(h.penalties for h in self.holes)

    @property
    def fir_hit(self) -> int:
        return sum(1 for h in self.holes if h.fir is True)

    @property
    def fir_opps(self) -> int:
        return sum(1 for h in self.holes if h.fir is not None)

    @property
    def gir_hit(self) -> int:
        return sum(1 for h in self.holes if h.gir is True)

    @property
    def gir_opps(self) -> int:
        return sum(1 for h in self.holes if h.gir is not None)

    @property
    def doubles_plus(self) -> int:
        return sum(1 for h in self.holes if h.to_par >= 2)

    @property
    def birdies_or_better(self) -> int:
        return sum(1 for h in self.holes if h.to_par <= -1)

    @property
    def pars(self) -> int:
        return sum(1 for h in self.holes if h.to_par == 0)

    @property
    def bogeys(self) -> int:
        return sum(1 for h in self.holes if h.to_par == 1)

    @property
    def scramble_attempts(self) -> int:
        return sum(1 for h in self.holes if h.up_and_down is not None)

    @property
    def scramble_saves(self) -> int:
        return sum(1 for h in self.holes if h.up_and_down is True)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Round":
        holes = [HoleResult(**{k: v for k, v in h.items() if k in HoleResult.__dataclass_fields__}) for h in d.get("holes", [])]
        return cls(
            id=d.get("id", ""),
            date=d.get("date", ""),
            course=d.get("course", ""),
            tees=d.get("tees", ""),
            holes=holes,
            source=d.get("source", "manual"),
            notes=d.get("notes", ""),
            created_at=d.get("created_at", ""),
        )


class RoundStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.path = self.data_dir / "rounds.jsonl"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Round]:
        rounds: List[Round] = []
        if not self.path.exists():
            return rounds
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rounds.append(Round.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        rounds.sort(key=lambda r: (r.date, r.created_at), reverse=True)
        return rounds

    def save(self, rnd: Round) -> bool:
        """Insert or replace by id."""
        existing = [r for r in self.load() if r.id != rnd.id]
        existing.append(rnd)
        return self._write_all(existing)

    def save_many(self, rounds: List[Round]) -> int:
        current = {r.id: r for r in self.load()}
        added = 0
        for r in rounds:
            if r.id not in current:
                added += 1
            current[r.id] = r
        self._write_all(list(current.values()))
        return added

    def delete(self, round_id: str) -> bool:
        rounds = self.load()
        kept = [r for r in rounds if r.id != round_id]
        if len(kept) == len(rounds):
            return False
        return self._write_all(kept)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def _write_all(self, rounds: List[Round]) -> bool:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                for r in sorted(rounds, key=lambda r: (r.date, r.created_at)):
                    f.write(json.dumps(r.to_dict()) + "\n")
            return True
        except Exception:
            return False

    def export_json(self) -> str:
        return json.dumps([r.to_dict() for r in self.load()], indent=2)
