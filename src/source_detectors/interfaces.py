"""Interfaces for the pluggable source detection system."""

from abc import ABC, abstractmethod
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models.detection import SourceDetectionResult


class SourceDetector(ABC):
    """Interface for a newsletter source detection provider."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """A unique name for this provider, e.g., 'mailchimp'."""
        pass
    
    @abstractmethod
    def is_applicable(self, url: str) -> bool:
        """
        Quickly checks if this detector can handle the given URL.
        
        Args:
            url: The URL to check
            
        Returns:
            True if this detector can handle the URL, False otherwise
        """
        pass
    
    @abstractmethod
    async def run_detection(self, url: str) -> Optional[SourceDetectionResult]:
        """
        Executes the full detection, extraction, and analysis pipeline.
        
        Args:
            url: The URL to analyze
            
        Returns:
            SourceDetectionResult with detection results or None if failed
        """
        pass
    
    def get_priority(self) -> int:
        """
        Get the priority of this detector for URL matching.
        Lower numbers have higher priority.
        
        Returns:
            Priority value (default: 100)
        """
        return 100