"""Source detection system for newsletter content attribution."""

from .config import get_config, set_config
from .interfaces import SourceDetector
from .orchestrator import SourceDetectionOrchestrator, detect_source, get_orchestrator

__version__ = "1.0.0"

__all__ = [
    "SourceDetectionOrchestrator",
    "SourceDetector",
    "get_orchestrator",
    "detect_source",
    "get_config",
    "set_config",
    "cleanup_resources",
]


async def cleanup_resources():
    """Clean up source detection resources including HTTP sessions."""
    from .http_session import cleanup_http_resources

    await cleanup_http_resources()
