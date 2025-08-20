"""Source detection system for newsletter content attribution."""

from .orchestrator import SourceDetectionOrchestrator, get_orchestrator, detect_source
from .interfaces import SourceDetector
from .config import get_config, set_config

__version__ = "1.0.0"

__all__ = [
    "SourceDetectionOrchestrator",
    "SourceDetector",
    "get_orchestrator",
    "detect_source",
    "get_config",
    "set_config",
]
