# data/plans.py
# Weekly plan history (JSONL).

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from coaching.plan import WeeklyPlan
from data.settings import default_data_dir


class PlanStore:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.path = self.data_dir / "plans.jsonl"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[WeeklyPlan]:
        plans: List[WeeklyPlan] = []
        if not self.path.exists():
            return plans
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    plans.append(WeeklyPlan.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        plans.sort(key=lambda p: (p.week_of, p.created_at), reverse=True)
        return plans

    def latest(self) -> Optional[WeeklyPlan]:
        plans = self.load()
        return plans[0] if plans else None

    def save(self, plan: WeeklyPlan) -> bool:
        """Replace any plan for the same week, then append."""
        plans = [p for p in self.load() if p.week_of != plan.week_of]
        plans.append(plan)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                for p in sorted(plans, key=lambda p: (p.week_of, p.created_at)):
                    f.write(json.dumps(p.to_dict()) + "\n")
            return True
        except Exception:
            return False

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
