# data/shots.py
# Shot storage: every imported TrackMan shot lives in one JSONL file.
# One export file = one "session". Files and shots are de-duplicated so
# re-exporting or re-scanning never double counts.

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

import numpy as np
import pandas as pd

from data.settings import default_data_dir
from integrations.trackman import ParseResult, content_hash, parse_trackman_csv, shot_hash


@dataclass
class IngestResult:
    source: str
    status: str                 # "added" | "duplicate_file" | "no_new_shots" | "empty" | "error"
    added: int = 0
    skipped_duplicates: int = 0
    session_id: str = ""
    warnings: List[str] = field(default_factory=list)
    unmapped_columns: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "added"


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else pd.Timestamp(value).isoformat()
    if isinstance(value, (np.floating, float)):
        return None if (isinstance(value, float) and math.isnan(value)) or pd.isna(value) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


class ShotStore:
    """JSONL-backed shot storage with file + shot de-duplication."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.shots_path = self.data_dir / "shots.jsonl"
        self.index_path = self.data_dir / "ingested_files.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ----- index of ingested files -----------------------------------------

    def _load_index(self) -> Dict[str, Dict]:
        try:
            if self.index_path.exists():
                return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_index(self, index: Dict[str, Dict]) -> None:
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _existing_hashes(self) -> set:
        hashes = set()
        if self.shots_path.exists():
            with open(self.shots_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        hashes.add(json.loads(line).get("shot_hash"))
                    except json.JSONDecodeError:
                        continue
        return hashes

    # ----- ingestion -------------------------------------------------------

    def ingest_bytes(self, data: bytes, name: str) -> IngestResult:
        file_hash = content_hash(data)
        index = self._load_index()
        if file_hash in index:
            return IngestResult(source=name, status="duplicate_file", session_id=index[file_hash].get("session_id", ""))
        parsed = parse_trackman_csv(data, source_name=name)
        return self._ingest_parsed(parsed, name, file_hash)

    def ingest_path(self, path: Union[str, Path]) -> IngestResult:
        path = Path(path)
        try:
            data = path.read_bytes()
        except Exception as exc:
            return IngestResult(source=path.name, status="error", warnings=[str(exc)])
        return self.ingest_bytes(data, path.name)

    def scan_folder(self, folder: Union[str, Path], patterns: Iterable[str] = ("*.csv", "*.CSV", "*.txt")) -> List[IngestResult]:
        folder = Path(folder).expanduser()
        results: List[IngestResult] = []
        if not folder.exists() or not folder.is_dir():
            return [IngestResult(source=str(folder), status="error", warnings=["Folder not found."])]
        seen = set()
        files: List[Path] = []
        for pattern in patterns:
            for p in folder.glob(pattern):
                if p.is_file() and p.resolve() not in seen:
                    seen.add(p.resolve())
                    files.append(p)
        index = self._load_index()
        for p in sorted(files, key=lambda x: x.stat().st_mtime):
            try:
                data = p.read_bytes()
            except Exception as exc:
                results.append(IngestResult(source=p.name, status="error", warnings=[str(exc)]))
                continue
            if content_hash(data) in index:
                continue  # silently skip files already ingested
            results.append(self.ingest_bytes(data, p.name))
            index = self._load_index()
        return results

    def _ingest_parsed(self, parsed: ParseResult, name: str, file_hash: str) -> IngestResult:
        res = IngestResult(source=name, warnings=list(parsed.warnings), unmapped_columns=list(parsed.unmapped_columns), status="empty")
        if not parsed.ok:
            # Remember the file so we don't re-parse it on every scan
            index = self._load_index()
            index[file_hash] = {"name": name, "ingested_at": datetime.now().isoformat(), "session_id": "", "shots": 0, "status": "empty"}
            self._save_index(index)
            return res

        session_id = file_hash
        df = parsed.df.copy()
        if "date" in df.columns and df["date"].notna().any():
            session_date = pd.to_datetime(df["date"]).min()
        else:
            session_date = pd.Timestamp(datetime.now())
            df["date"] = session_date
        df["session_id"] = session_id
        df["source_file"] = name

        existing = self._existing_hashes()
        rows = df.to_dict(orient="records")
        new_rows = []
        for row in rows:
            h = shot_hash(row)
            if h in existing:
                res.skipped_duplicates += 1
                continue
            existing.add(h)
            row["shot_hash"] = h
            new_rows.append({k: _json_safe(v) for k, v in row.items()})

        if new_rows:
            with open(self.shots_path, "a", encoding="utf-8") as f:
                for row in new_rows:
                    f.write(json.dumps(row) + "\n")
            res.status = "added"
            res.added = len(new_rows)
        else:
            res.status = "no_new_shots"
        res.session_id = session_id

        index = self._load_index()
        index[file_hash] = {
            "name": name,
            "ingested_at": datetime.now().isoformat(),
            "session_id": session_id,
            "session_date": pd.Timestamp(session_date).isoformat(),
            "shots": res.added,
            "status": res.status,
        }
        self._save_index(index)
        return res

    # ----- reading ---------------------------------------------------------

    def load_shots(self) -> pd.DataFrame:
        rows = []
        if self.shots_path.exists():
            with open(self.shots_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for col in df.columns:
            if col.endswith(("_mph", "_deg", "_yds", "_rpm", "_s", "_in", "_mm")) or col in ("smash_factor", "shot_number"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def sessions(self) -> pd.DataFrame:
        df = self.load_shots()
        if df.empty:
            return pd.DataFrame(columns=["session_id", "date", "source_file", "shots", "clubs"])
        g = df.groupby("session_id")
        out = pd.DataFrame({
            "date": g["date"].min(),
            "source_file": g["source_file"].first(),
            "shots": g.size(),
            "clubs": g["club"].agg(lambda s: ", ".join(sorted(set(s), key=str))),
        }).reset_index()
        return out.sort_values("date", ascending=False).reset_index(drop=True)

    # ----- maintenance -----------------------------------------------------

    def delete_session(self, session_id: str) -> int:
        if not self.shots_path.exists():
            return 0
        kept, removed = [], 0
        with open(self.shots_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("session_id") == session_id:
                    removed += 1
                else:
                    kept.append(line if line.endswith("\n") else line + "\n")
        with open(self.shots_path, "w", encoding="utf-8") as f:
            f.writelines(kept)
        index = self._load_index()
        for h, meta in list(index.items()):
            if meta.get("session_id") == session_id:
                del index[h]
        self._save_index(index)
        return removed

    def clear(self) -> None:
        for p in (self.shots_path, self.index_path):
            if p.exists():
                p.unlink()

    def export_csv(self) -> str:
        df = self.load_shots()
        return df.to_csv(index=False) if not df.empty else ""
