# data/sessions.py
# Session storage and retrieval for progress tracking

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
import hashlib


@dataclass
class Session:
    """Represents a single swing analysis session."""
    id: str
    timestamp: str
    club: str
    angle: str
    metrics: Dict[str, Any]
    confidence: str
    pointers_summary: List[str]
    video_name: str

    @classmethod
    def create(
        cls,
        club: str,
        angle: str,
        metrics: Dict[str, Any],
        confidence: str,
        pointers: List[str],
        video_name: str = ""
    ) -> "Session":
        """Create a new session with auto-generated ID and timestamp."""
        timestamp = datetime.now().isoformat()
        # Generate ID from timestamp + random element
        id_str = f"{timestamp}-{club}-{angle}"
        session_id = hashlib.md5(id_str.encode()).hexdigest()[:12]

        return cls(
            id=session_id,
            timestamp=timestamp,
            club=club,
            angle=angle,
            metrics=metrics,
            confidence=confidence,
            pointers_summary=pointers[:5],  # Keep top 5 pointers
            video_name=video_name,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(**data)


class SessionStore:
    """
    Simple JSONL-based session storage.

    Note: On Streamlit Cloud, the filesystem is ephemeral and resets on redeploy.
    This storage is best-effort and sessions may be lost.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize session store.

        Args:
            storage_path: Path to JSONL file. Defaults to data/sessions.jsonl
        """
        if storage_path is None:
            storage_path = Path(__file__).parent / "sessions.jsonl"

        self.storage_path = storage_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create storage file if it doesn't exist."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self.storage_path.touch()
        except Exception:
            pass  # Graceful degradation if filesystem is read-only

    def save_session(self, session: Session) -> bool:
        """
        Save a session to storage.

        Args:
            session: Session to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(session.to_dict()) + "\n")
            return True
        except Exception as e:
            print(f"Warning: Could not save session: {e}")
            return False

    def load_sessions(self, limit: int = 100) -> List[Session]:
        """
        Load sessions from storage.

        Args:
            limit: Maximum number of sessions to return (most recent first)

        Returns:
            List of Session objects, newest first
        """
        sessions = []

        try:
            if not self.storage_path.exists():
                return []

            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            sessions.append(Session.from_dict(data))
                        except (json.JSONDecodeError, TypeError):
                            continue  # Skip malformed lines

        except Exception as e:
            print(f"Warning: Could not load sessions: {e}")
            return []

        # Sort by timestamp descending and limit
        sessions.sort(key=lambda s: s.timestamp, reverse=True)
        return sessions[:limit]

    def get_sessions_by_club(self, club: str, limit: int = 50) -> List[Session]:
        """Get sessions filtered by club."""
        all_sessions = self.load_sessions(limit=500)
        filtered = [s for s in all_sessions if s.club == club]
        return filtered[:limit]

    def get_sessions_by_angle(self, angle: str, limit: int = 50) -> List[Session]:
        """Get sessions filtered by angle."""
        all_sessions = self.load_sessions(limit=500)
        filtered = [s for s in all_sessions if s.angle == angle]
        return filtered[:limit]

    def export_sessions_json(self) -> str:
        """Export all sessions as JSON string for download."""
        sessions = self.load_sessions(limit=1000)
        return json.dumps([s.to_dict() for s in sessions], indent=2)

    def clear_sessions(self) -> bool:
        """Clear all sessions (for testing/reset)."""
        try:
            self.storage_path.write_text("")
            return True
        except Exception:
            return False

    @property
    def is_ephemeral(self) -> bool:
        """Check if storage might be ephemeral (Streamlit Cloud detection)."""
        # Check for Streamlit Cloud environment indicators
        return os.environ.get("STREAMLIT_SHARING_MODE") is not None


# Module-level store instance for convenience
_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get the module-level session store instance."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
