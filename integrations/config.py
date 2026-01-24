# integrations/config.py
# Configuration and feature flags for integrations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import os


# ============================================
# Feature Flags
# ============================================

FEATURE_FLAGS = {
    # Launch monitor integrations
    "trackman_enabled": False,
    "bushnell_enabled": False,
    "flightscope_enabled": False,
    "mevo_enabled": False,

    # Scoring/round integrations
    "arccos_enabled": False,
    "garmin_golf_enabled": False,
    "grint_enabled": False,

    # UI features
    "show_pro_features": True,  # Show "Coming Soon" placeholders
    "show_mock_data": False,  # Show mock data for demo purposes

    # Experimental
    "ai_coaching_v2": False,
    "video_comparison": False,
}


def is_feature_enabled(feature_name: str) -> bool:
    """
    Check if a feature flag is enabled.

    Also checks environment variables for overrides:
    - GOLF_FEATURE_<NAME>=1 enables a feature
    - GOLF_FEATURE_<NAME>=0 disables a feature

    Args:
        feature_name: Name of the feature flag

    Returns:
        True if enabled, False otherwise
    """
    # Check environment variable override first
    env_key = f"GOLF_FEATURE_{feature_name.upper()}"
    env_value = os.environ.get(env_key)

    if env_value is not None:
        return env_value.lower() in ("1", "true", "yes", "on")

    return FEATURE_FLAGS.get(feature_name, False)


# ============================================
# Integration Configuration
# ============================================

@dataclass
class IntegrationConfig:
    """
    Configuration for external service integrations.

    Store API keys and settings securely (use environment variables
    in production, not hardcoded values).
    """
    # TrackMan
    trackman_client_id: Optional[str] = None
    trackman_client_secret: Optional[str] = None
    trackman_refresh_token: Optional[str] = None

    # Bushnell
    bushnell_api_key: Optional[str] = None
    bushnell_device_id: Optional[str] = None

    # FlightScope (future)
    flightscope_api_key: Optional[str] = None

    # Scoring apps (future)
    arccos_token: Optional[str] = None
    garmin_connect_token: Optional[str] = None

    @classmethod
    def from_environment(cls) -> "IntegrationConfig":
        """
        Load configuration from environment variables.

        Expected environment variables:
        - TRACKMAN_CLIENT_ID
        - TRACKMAN_CLIENT_SECRET
        - TRACKMAN_REFRESH_TOKEN
        - BUSHNELL_API_KEY
        - etc.
        """
        return cls(
            trackman_client_id=os.environ.get("TRACKMAN_CLIENT_ID"),
            trackman_client_secret=os.environ.get("TRACKMAN_CLIENT_SECRET"),
            trackman_refresh_token=os.environ.get("TRACKMAN_REFRESH_TOKEN"),
            bushnell_api_key=os.environ.get("BUSHNELL_API_KEY"),
            bushnell_device_id=os.environ.get("BUSHNELL_DEVICE_ID"),
            flightscope_api_key=os.environ.get("FLIGHTSCOPE_API_KEY"),
            arccos_token=os.environ.get("ARCCOS_TOKEN"),
            garmin_connect_token=os.environ.get("GARMIN_CONNECT_TOKEN"),
        )

    def get_trackman_config(self) -> Dict[str, Any]:
        """Get TrackMan-specific configuration."""
        return {
            "client_id": self.trackman_client_id,
            "client_secret": self.trackman_client_secret,
            "refresh_token": self.trackman_refresh_token,
        }

    def get_bushnell_config(self) -> Dict[str, Any]:
        """Get Bushnell-specific configuration."""
        return {
            "api_key": self.bushnell_api_key,
            "device_id": self.bushnell_device_id,
        }


# ============================================
# Integration Registry
# ============================================

AVAILABLE_INTEGRATIONS = {
    "trackman": {
        "name": "TrackMan",
        "description": "Industry-leading launch monitor for detailed ball and club data",
        "features": ["launch_monitor"],
        "status": "coming_soon",
        "icon": "📡",
    },
    "bushnell": {
        "name": "Bushnell Launch Pro",
        "description": "Portable launch monitor with GC3 radar technology",
        "features": ["launch_monitor"],
        "status": "coming_soon",
        "icon": "📶",
    },
    "flightscope": {
        "name": "FlightScope",
        "description": "Doppler radar launch monitors (Mevo, X3)",
        "features": ["launch_monitor"],
        "status": "planned",
        "icon": "🎯",
    },
    "arccos": {
        "name": "Arccos Caddie",
        "description": "AI-powered on-course tracking and analytics",
        "features": ["rounds", "stats"],
        "status": "planned",
        "icon": "⛳",
    },
    "garmin": {
        "name": "Garmin Golf",
        "description": "GPS and round tracking from Garmin watches",
        "features": ["rounds", "gps"],
        "status": "planned",
        "icon": "⌚",
    },
}


def get_available_integrations() -> Dict[str, Dict[str, Any]]:
    """
    Get list of available integrations with their status.

    Returns:
        Dictionary of integration_id -> integration info
    """
    return AVAILABLE_INTEGRATIONS.copy()


def get_enabled_integrations() -> List[str]:
    """
    Get list of currently enabled integrations.

    Returns:
        List of integration IDs that are enabled
    """
    enabled = []
    if is_feature_enabled("trackman_enabled"):
        enabled.append("trackman")
    if is_feature_enabled("bushnell_enabled"):
        enabled.append("bushnell")
    # Add others as they become available
    return enabled
