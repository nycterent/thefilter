"""Mailchimp source detector implementation."""

import time
import asyncio
import aiohttp
import logging
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from source_detectors.interfaces import SourceDetector
from models.detection import SourceDetectionResult, DetectionStatus, AttributionInfo
from source_detectors.strategies.attribution import (
    AttributionAnalyzer, 
    FooterCopyrightStrategy, 
    PoweredByLinkStrategy,
    EmailFooterStrategy,
    DomainExtractionStrategy
)
from source_detectors.config import get_config

logger = logging.getLogger(__name__)


class MailchimpDetector(SourceDetector):
    """Source detector for Mailchimp campaign archive URLs."""
    
    def __init__(self):
        """Initialize the Mailchimp detector with attribution strategies."""
        # Initialize attribution analyzer with Mailchimp-specific strategies
        self.attribution_analyzer = AttributionAnalyzer([
            EmailFooterStrategy(),      # Highest priority for email patterns
            PoweredByLinkStrategy(),    # Look for powered by links
            FooterCopyrightStrategy(),  # Copyright notices
            DomainExtractionStrategy(), # Fallback domain extraction
        ])
        
        # Load configuration
        self.timeout = get_config("mailchimp.timeout", 30)
        self.max_retries = get_config("mailchimp.max_retries", 3)
        self.retry_delay = get_config("mailchimp.retry_delay", 1.0)
        self.user_agent = get_config("detection.user_agent", "Mozilla/5.0 (compatible; Newsletter-Bot/1.0)")
    
    @property
    def provider_name(self) -> str:
        """Unique name for this provider."""
        return "mailchimp"
    
    def get_priority(self) -> int:
        """Mailchimp has high priority for campaign-archive URLs."""
        return 10
    
    def is_applicable(self, url: str) -> bool:
        """
        Check if URL is a Mailchimp campaign archive URL.
        
        Args:
            url: The URL to check
            
        Returns:
            True if this is a Mailchimp campaign archive URL
        """
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Check for Mailchimp campaign archive patterns
        mailchimp_patterns = [
            "campaign-archive.com",
            ".list-manage.com",
            "mailchimp.com",
        ]
        
        return any(pattern in url_lower for pattern in mailchimp_patterns)
    
    async def run_detection(self, url: str) -> Optional[SourceDetectionResult]:
        """
        Execute the full Mailchimp detection pipeline.
        
        Args:
            url: The URL to analyze
            
        Returns:
            SourceDetectionResult with detection results
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔍 Running Mailchimp detection for: {url}")
            
            # 1. Extract content with retry logic
            raw_content = await self._extract_content_with_retry(url)
            if not raw_content:
                return SourceDetectionResult(
                    provider=self.provider_name,
                    url=url,
                    status=DetectionStatus.FAILURE,
                    error_message="Failed to extract content after retries",
                    processing_time=time.time() - start_time
                )
            
            logger.debug(f"✅ Content extracted: {len(raw_content)} characters")
            
            # 2. Analyze for attribution
            attribution = self.attribution_analyzer.analyze(raw_content)
            
            # 3. Determine success status
            if attribution and attribution.confidence_score > get_config("attribution.min_confidence", 0.3):
                status = DetectionStatus.SUCCESS
                logger.info(f"✅ Attribution found: {attribution.publisher} (confidence: {attribution.confidence_score})")
            elif raw_content:
                status = DetectionStatus.PARTIAL_SUCCESS
                logger.warning("⚠️ Content extracted but no reliable attribution found")
            else:
                status = DetectionStatus.FAILURE
                logger.error("❌ Failed to extract content")
            
            # 4. Return result
            return SourceDetectionResult(
                provider=self.provider_name,
                url=url,
                status=status,
                content_extracted=bool(raw_content),
                attribution_found=attribution is not None,
                raw_content=raw_content,
                attribution=attribution,
                processing_time=time.time() - start_time,
                metadata={
                    "content_length": len(raw_content) if raw_content else 0,
                    "strategies_used": len(self.attribution_analyzer.strategies),
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Error in Mailchimp detection: {e}")
            return SourceDetectionResult(
                provider=self.provider_name,
                url=url,
                status=DetectionStatus.FAILURE,
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    async def _extract_content_with_retry(self, url: str) -> Optional[str]:
        """
        Extract content from URL with retry logic and exponential backoff.
        
        Args:
            url: The URL to fetch
            
        Returns:
            Raw HTML content or None if failed
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                headers = {
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
                
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        content = await response.text()
                        
                        # Check content size
                        max_size = get_config("detection.max_content_size", 10 * 1024 * 1024)
                        if len(content) > max_size:
                            logger.warning(f"Content size ({len(content)}) exceeds maximum ({max_size})")
                            content = content[:max_size]
                        
                        return content
                        
            except asyncio.TimeoutError as e:
                last_error = f"Timeout after {self.timeout}s on attempt {attempt + 1}"
                logger.warning(last_error)
            except aiohttp.ClientError as e:
                last_error = f"HTTP error on attempt {attempt + 1}: {e}"
                logger.warning(last_error)
            except Exception as e:
                last_error = f"Unexpected error on attempt {attempt + 1}: {e}"
                logger.warning(last_error)
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                logger.debug(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        logger.error(f"Failed to extract content after {self.max_retries} attempts. Last error: {last_error}")
        return None