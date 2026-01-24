# integrations package - External service connectors
# Pro integrations for launch monitors, scoring, etc.

from integrations.base import (
    BaseConnector,
    LaunchMonitorData,
    RoundData,
    ShotData,
    IntegrationError,
)
from integrations.trackman import TrackManConnector
from integrations.bushnell import BushnellConnector
from integrations.config import (
    IntegrationConfig,
    FEATURE_FLAGS,
    is_feature_enabled,
    get_available_integrations,
    get_enabled_integrations,
)

__all__ = [
    # Base classes and data contracts
    "BaseConnector",
    "LaunchMonitorData",
    "RoundData",
    "ShotData",
    "IntegrationError",
    # Connectors
    "TrackManConnector",
    "BushnellConnector",
    # Config
    "IntegrationConfig",
    "FEATURE_FLAGS",
    "is_feature_enabled",
    "get_available_integrations",
    "get_enabled_integrations",
]
