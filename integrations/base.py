# integrations/base.py
# Base classes and data contracts for external integrations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class IntegrationError(Exception):
    """Base exception for integration errors."""
    pass


class ConnectionError(IntegrationError):
    """Failed to connect to external service."""
    pass


class AuthenticationError(IntegrationError):
    """Authentication/authorization failed."""
    pass


class DataFormatError(IntegrationError):
    """Data format or parsing error."""
    pass


# ============================================
# Data Contracts
# ============================================

@dataclass
class LaunchMonitorData:
    """
    Standard data contract for launch monitor metrics.

    This represents a single shot captured by a launch monitor
    (e.g., TrackMan, Bushnell Launch Pro, FlightScope).
    """
    # Identifiers
    shot_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    source: str = "unknown"  # e.g., "trackman", "bushnell"

    # Club data
    club: Optional[str] = None  # e.g., "Driver", "7 Iron"
    club_speed_mph: Optional[float] = None
    attack_angle_deg: Optional[float] = None  # Angle of Attack
    club_path_deg: Optional[float] = None  # In-to-out / out-to-in

    # Face data
    face_angle_deg: Optional[float] = None  # Open/closed at impact
    face_to_path_deg: Optional[float] = None  # Face relative to path
    dynamic_loft_deg: Optional[float] = None

    # Ball data
    ball_speed_mph: Optional[float] = None
    smash_factor: Optional[float] = None  # Ball speed / club speed
    launch_angle_deg: Optional[float] = None
    launch_direction_deg: Optional[float] = None  # Left/right of target
    spin_rate_rpm: Optional[float] = None
    spin_axis_deg: Optional[float] = None  # Tilt of spin axis

    # Carry/total
    carry_yards: Optional[float] = None
    total_yards: Optional[float] = None
    offline_yards: Optional[float] = None  # Left (-) / right (+) of target

    # Quality indicators
    confidence: float = 1.0  # 0.0 to 1.0
    raw_data: Optional[Dict[str, Any]] = None  # Original data for debugging


@dataclass
class ShotData:
    """
    Data contract for a single shot in a round.

    Used for round/scoring integrations.
    """
    hole_number: int
    shot_number: int  # 1 = tee shot, 2 = approach, etc.

    # Location
    start_lie: Optional[str] = None  # "tee", "fairway", "rough", "bunker", "green"
    end_lie: Optional[str] = None
    start_distance_yards: Optional[float] = None  # To pin
    end_distance_yards: Optional[float] = None

    # Club used
    club: Optional[str] = None

    # Result
    result: Optional[str] = None  # "fairway", "green", "hazard", "ob", "holed"
    penalty_strokes: int = 0

    # Launch monitor data if available
    launch_data: Optional[LaunchMonitorData] = None


@dataclass
class RoundData:
    """
    Data contract for a complete round of golf.

    Used for scoring/stats integrations (e.g., Arccos, Garmin Golf).
    """
    # Identifiers
    round_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    source: str = "unknown"

    # Course info
    course_name: Optional[str] = None
    course_id: Optional[str] = None
    tee_name: Optional[str] = None  # e.g., "Blue", "White"
    course_rating: Optional[float] = None
    slope_rating: Optional[int] = None

    # Scores
    total_strokes: Optional[int] = None
    total_putts: Optional[int] = None
    fairways_hit: Optional[int] = None
    fairways_total: Optional[int] = None
    greens_in_regulation: Optional[int] = None
    greens_total: Optional[int] = None

    # Per-hole data
    hole_scores: List[int] = field(default_factory=list)
    hole_putts: List[int] = field(default_factory=list)

    # Detailed shot data (if available)
    shots: List[ShotData] = field(default_factory=list)

    # Raw data
    raw_data: Optional[Dict[str, Any]] = None


# ============================================
# Abstract Base Connector
# ============================================

class BaseConnector(ABC):
    """
    Abstract base class for external service connectors.

    Subclasses implement specific integrations (TrackMan, Bushnell, etc.).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize connector with optional configuration.

        Args:
            config: Dictionary with API keys, endpoints, etc.
        """
        self.config = config or {}
        self._connected = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the integration."""
        pass

    @property
    @abstractmethod
    def supported_features(self) -> List[str]:
        """List of supported features (e.g., ['launch_monitor', 'rounds'])."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the external service.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the external service."""
        pass

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected

    def get_recent_shots(self, limit: int = 10) -> List[LaunchMonitorData]:
        """
        Retrieve recent shot data from launch monitor.

        Args:
            limit: Maximum number of shots to retrieve

        Returns:
            List of LaunchMonitorData objects

        Raises:
            NotImplementedError: If not supported by this connector
        """
        raise NotImplementedError(f"{self.name} does not support launch monitor data")

    def get_recent_rounds(self, limit: int = 5) -> List[RoundData]:
        """
        Retrieve recent round data.

        Args:
            limit: Maximum number of rounds to retrieve

        Returns:
            List of RoundData objects

        Raises:
            NotImplementedError: If not supported by this connector
        """
        raise NotImplementedError(f"{self.name} does not support round data")

    def import_shot(self, shot_id: str) -> Optional[LaunchMonitorData]:
        """
        Import a specific shot by ID.

        Args:
            shot_id: Unique identifier for the shot

        Returns:
            LaunchMonitorData or None if not found
        """
        raise NotImplementedError(f"{self.name} does not support shot import")
