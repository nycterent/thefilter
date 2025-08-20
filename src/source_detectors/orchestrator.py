"""Source detection orchestrator for managing multiple providers."""

import logging
from typing import Optional, List, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from source_detectors.interfaces import SourceDetector
from source_detectors.providers.mailchimp import MailchimpDetector
from models.detection import SourceDetectionResult, DetectionStatus

logger = logging.getLogger(__name__)


class SourceDetectionOrchestrator:
    """Orchestrates the source detection process using registered detectors."""
    
    def __init__(self):
        """Initialize orchestrator with default detectors."""
        self.detectors: List[SourceDetector] = []
        self._register_default_detectors()
    
    def _register_default_detectors(self):
        """Register the default set of source detectors."""
        try:
            # Register Mailchimp detector
            self.register_detector(MailchimpDetector())
            logger.info("✅ Registered Mailchimp detector")
            
            # Future detectors can be added here:
            # self.register_detector(SubstackDetector())
            # self.register_detector(BeehiivDetector())
            
        except Exception as e:
            logger.error(f"Error registering default detectors: {e}")
    
    def register_detector(self, detector: SourceDetector):
        """
        Register a new source detector.
        
        Args:
            detector: SourceDetector instance to register
        """
        if not isinstance(detector, SourceDetector):
            raise ValueError("Detector must implement SourceDetector interface")
        
        # Check if detector with same provider name already exists
        existing = next(
            (d for d in self.detectors if d.provider_name == detector.provider_name), 
            None
        )
        
        if existing:
            logger.warning(f"Replacing existing detector for provider: {detector.provider_name}")
            self.detectors.remove(existing)
        
        self.detectors.append(detector)
        
        # Sort detectors by priority
        self.detectors.sort(key=lambda d: d.get_priority())
        
        logger.info(f"Registered detector: {detector.provider_name} (priority: {detector.get_priority()})")
    
    def unregister_detector(self, provider_name: str) -> bool:
        """
        Unregister a detector by provider name.
        
        Args:
            provider_name: Name of the provider to unregister
            
        Returns:
            True if detector was found and removed, False otherwise
        """
        for detector in self.detectors:
            if detector.provider_name == provider_name:
                self.detectors.remove(detector)
                logger.info(f"Unregistered detector: {provider_name}")
                return True
        
        logger.warning(f"Detector not found for unregistration: {provider_name}")
        return False
    
    def list_detectors(self) -> List[Dict[str, Any]]:
        """
        List all registered detectors.
        
        Returns:
            List of detector information dictionaries
        """
        return [
            {
                "provider_name": detector.provider_name,
                "priority": detector.get_priority(),
                "class_name": detector.__class__.__name__,
            }
            for detector in self.detectors
        ]
    
    async def detect_source(self, url: str) -> Optional[SourceDetectionResult]:
        """
        Detect the source of content at the given URL using registered detectors.
        
        Args:
            url: The URL to analyze
            
        Returns:
            SourceDetectionResult from the first applicable detector, or None if no detector applies
        """
        if not url or not url.strip():
            logger.warning("Empty URL provided for source detection")
            return None
        
        url = url.strip()
        logger.info(f"🔍 Starting source detection for: {url}")
        
        applicable_detectors = []
        
        # Find all applicable detectors
        for detector in self.detectors:
            try:
                if detector.is_applicable(url):
                    applicable_detectors.append(detector)
                    logger.debug(f"✅ Detector {detector.provider_name} is applicable")
                else:
                    logger.debug(f"❌ Detector {detector.provider_name} is not applicable")
            except Exception as e:
                logger.error(f"Error checking applicability for {detector.provider_name}: {e}")
                continue
        
        if not applicable_detectors:
            logger.warning(f"No applicable detectors found for URL: {url}")
            return None
        
        logger.info(f"Found {len(applicable_detectors)} applicable detector(s): {[d.provider_name for d in applicable_detectors]}")
        
        # Try detectors in priority order
        for detector in applicable_detectors:
            try:
                logger.info(f"🚀 Running detection with {detector.provider_name}")
                result = await detector.run_detection(url)
                
                if result:
                    if result.status == DetectionStatus.SUCCESS:
                        logger.info(f"✅ Successful detection by {detector.provider_name}")
                        return result
                    elif result.status == DetectionStatus.PARTIAL_SUCCESS:
                        logger.warning(f"⚠️ Partial success with {detector.provider_name}")
                        return result
                    else:
                        logger.warning(f"❌ Detection failed with {detector.provider_name}: {result.error_message}")
                        # Continue to next detector
                        continue
                else:
                    logger.warning(f"❌ No result from {detector.provider_name}")
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Error with detector {detector.provider_name}: {e}")
                continue
        
        logger.warning(f"All applicable detectors failed for URL: {url}")
        return None
    
    async def detect_source_with_fallback(self, url: str, fallback_provider: Optional[str] = None) -> Optional[SourceDetectionResult]:
        """
        Detect source with fallback to a specific provider if primary detection fails.
        
        Args:
            url: The URL to analyze
            fallback_provider: Provider name to use as fallback
            
        Returns:
            SourceDetectionResult or None
        """
        # Try normal detection first
        result = await self.detect_source(url)
        
        if result and result.status in [DetectionStatus.SUCCESS, DetectionStatus.PARTIAL_SUCCESS]:
            return result
        
        # Try fallback provider if specified
        if fallback_provider:
            fallback_detector = next(
                (d for d in self.detectors if d.provider_name == fallback_provider),
                None
            )
            
            if fallback_detector:
                try:
                    logger.info(f"🔄 Trying fallback detector: {fallback_provider}")
                    return await fallback_detector.run_detection(url)
                except Exception as e:
                    logger.error(f"Fallback detector {fallback_provider} failed: {e}")
        
        return result
    
    def get_detector_stats(self) -> Dict[str, Any]:
        """
        Get statistics about registered detectors.
        
        Returns:
            Dictionary with detector statistics
        """
        return {
            "total_detectors": len(self.detectors),
            "detectors": self.list_detectors(),
            "providers": [d.provider_name for d in self.detectors],
        }


# Global orchestrator instance
_orchestrator = None


def get_orchestrator() -> SourceDetectionOrchestrator:
    """
    Get the global orchestrator instance.
    
    Returns:
        SourceDetectionOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SourceDetectionOrchestrator()
    return _orchestrator


async def detect_source(url: str) -> Optional[SourceDetectionResult]:
    """
    Convenience function for source detection using global orchestrator.
    
    Args:
        url: The URL to analyze
        
    Returns:
        SourceDetectionResult or None
    """
    orchestrator = get_orchestrator()
    return await orchestrator.detect_source(url)