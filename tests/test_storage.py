# tests/test_storage.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.rounds import HoleResult, Round, RoundStore
from data.settings import Settings, SettingsStore
from data.shots import ShotStore

SAMPLE = Path(__file__).parent / "sample_trackman.csv"


class TestShotStore:
    def test_ingest_and_dedup(self, tmp_path):
        store = ShotStore(tmp_path)
        r1 = store.ingest_path(SAMPLE)
        assert r1.ok and r1.added == 28
        # same file again -> duplicate file
        r2 = store.ingest_path(SAMPLE)
        assert r2.status == "duplicate_file"
        # same content with a different name -> same file hash -> duplicate
        r3 = store.ingest_bytes(SAMPLE.read_bytes(), "copy.csv")
        assert r3.status == "duplicate_file"
        # slightly different file with overlapping shots -> shot-level dedup
        text = SAMPLE.read_text(encoding="utf-8") + "\n"
        r4 = store.ingest_bytes(text.encode("utf-8"), "overlap.csv")
        assert r4.status == "no_new_shots" and r4.skipped_duplicates == 28
        df = store.load_shots()
        assert len(df) == 28
        assert df["session_id"].nunique() == 1

    def test_scan_folder(self, tmp_path):
        folder = tmp_path / "exports"
        folder.mkdir()
        (folder / "a.csv").write_bytes(SAMPLE.read_bytes())
        (folder / "notes.txt").write_text("not a trackman file", encoding="utf-8")
        store = ShotStore(tmp_path / "db")
        results = store.scan_folder(folder)
        statuses = {r.source: r.status for r in results}
        assert statuses["a.csv"] == "added"
        assert statuses["notes.txt"] == "empty"
        # second scan: nothing new, nothing re-parsed
        assert store.scan_folder(folder) == []
        assert store.scan_folder(tmp_path / "missing")[0].status == "error"

    def test_sessions_and_delete(self, tmp_path):
        store = ShotStore(tmp_path)
        res = store.ingest_path(SAMPLE)
        sessions = store.sessions()
        assert len(sessions) == 1 and sessions.iloc[0]["shots"] == 28
        assert store.delete_session(res.session_id) == 28
        assert store.load_shots().empty
        # deleting the session forgets the file, so it can be re-imported
        assert store.ingest_path(SAMPLE).ok


class TestRoundStore:
    def _round(self, date="2026-08-24", score_offset=0):
        holes = [HoleResult(hole=i, par=4, score=5 + score_offset, putts=2, fir=True, gir=False, penalties=0) for i in range(1, 19)]
        return Round.create(date=date, course="Test", holes=holes)

    def test_save_load_delete(self, tmp_path):
        store = RoundStore(tmp_path)
        r = self._round()
        assert store.save(r)
        assert store.save(r)  # idempotent
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].total == 90 and loaded[0].to_par == 18
        assert store.delete(r.id)
        assert store.load() == []

    def test_save_many_counts_new(self, tmp_path):
        store = RoundStore(tmp_path)
        a, b = self._round("2026-08-24"), self._round("2026-08-31", 1)
        assert store.save_many([a, b]) == 2
        assert store.save_many([a, b]) == 0

    def test_derived_stats(self):
        holes = [
            HoleResult(1, 4, 6, putts=3, fir=False, gir=False, penalties=1),
            HoleResult(2, 3, 3, putts=2, fir=None, gir=True),
            HoleResult(3, 5, 4, putts=1, fir=True, gir=True, up_and_down=None),
            HoleResult(4, 4, 5, putts=2, fir=True, gir=False, up_and_down=False),
        ]
        r = Round.create("2026-09-01", "X", holes)
        assert r.total == 18 and r.par == 16 and r.to_par == 2
        assert r.putts == 8 and r.three_putts == 1 and r.penalties == 1
        assert r.fir_hit == 2 and r.fir_opps == 3
        assert r.gir_hit == 2 and r.gir_opps == 4
        assert r.doubles_plus == 1 and r.birdies_or_better == 1 and r.pars == 1 and r.bogeys == 1
        assert r.scramble_attempts == 1 and r.scramble_saves == 0


class TestSettings:
    def test_roundtrip(self, tmp_path):
        store = SettingsStore(tmp_path)
        assert store.load() == Settings()
        s = Settings(export_folder="C:/x", handedness="left", target_score=82)
        assert store.save(s)
        assert store.load() == s

    def test_ignores_unknown_keys(self):
        s = Settings.from_dict({"handedness": "left", "bogus": 1})
        assert s.handedness == "left"
