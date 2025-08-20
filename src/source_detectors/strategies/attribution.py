"""Attribution extraction strategies using the Strategy Pattern."""

import logging
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from models.detection import AttributionInfo

logger = logging.getLogger(__name__)


class AttributionStrategy(ABC):
    """Abstract base class for attribution extraction strategies."""

    @abstractmethod
    def extract(self, content: str) -> Optional[AttributionInfo]:
        """
        Extract attribution information from content.

        Args:
            content: The HTML or text content to analyze

        Returns:
            AttributionInfo if attribution found, None otherwise
        """
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Name of this strategy for logging and debugging."""
        pass


class FooterCopyrightStrategy(AttributionStrategy):
    """Strategy to extract attribution from copyright notices in footers."""

    @property
    def strategy_name(self) -> str:
        return "footer_copyright"

    def extract(self, content: str) -> Optional[AttributionInfo]:
        """Extract attribution from copyright notices."""
        patterns = [
            r"©.*?(\w+\.\w+)",  # Copyright with domain
            r"copyright.*?(\w+\.\w+)",  # Copyright text with domain
            r"&copy;.*?(\w+\.\w+)",  # HTML copyright entity with domain
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                domain = match.group(1)
                return AttributionInfo(
                    publisher=domain,
                    original_url=f"https://{domain}",
                    confidence_score=0.7,
                    extraction_method=self.strategy_name,
                )

        return None


class PoweredByLinkStrategy(AttributionStrategy):
    """Strategy to extract attribution from 'powered by' links."""

    @property
    def strategy_name(self) -> str:
        return "powered_by_link"

    def extract(self, content: str) -> Optional[AttributionInfo]:
        """Extract attribution from 'powered by' links."""
        patterns = [
            r'powered by.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
            r"powered by.*?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    url, text = match.groups()
                    return AttributionInfo(
                        publisher=text.strip(),
                        original_url=url,
                        confidence_score=0.8,
                        extraction_method=self.strategy_name,
                    )
                else:
                    domain = match.group(1)
                    return AttributionInfo(
                        publisher=domain,
                        original_url=f"https://{domain}",
                        confidence_score=0.6,
                        extraction_method=self.strategy_name,
                    )

        return None


class EmailFooterStrategy(AttributionStrategy):
    """Strategy to extract attribution from email footer patterns."""

    @property
    def strategy_name(self) -> str:
        return "email_footer"

    def extract(self, content: str) -> Optional[AttributionInfo]:
        """Extract attribution from email footer patterns."""
        patterns = [
            r"You are receiving this email because you signed up to receive updates from ([^.\n]+)\.(?:org|com|net|edu|gov)",
            r"unsubscribe from ([^.\n]+)\.(?:org|com|net|edu|gov)",
            r"This email was sent by ([^.\n]+)\.(?:org|com|net|edu|gov)",
            r"From the team at ([^.\n]+)\.(?:org|com|net|edu|gov)",
            r"Contact us at.*?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                publisher = match.group(1)
                # Check if it includes domain extension
                if "." in publisher:
                    domain = publisher
                else:
                    domain = f"{publisher}.org"  # Assume .org if no extension

                return AttributionInfo(
                    publisher=domain,
                    original_url=f"https://{domain}",
                    confidence_score=0.9,
                    extraction_method=self.strategy_name,
                )

        return None


class DomainExtractionStrategy(AttributionStrategy):
    """Strategy to extract domains from content as fallback attribution."""

    @property
    def strategy_name(self) -> str:
        return "domain_extraction"

    def extract(self, content: str) -> Optional[AttributionInfo]:
        """Extract domains from content as fallback."""
        # Look for domain names in the content
        domain_pattern = (
            r"(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})(?:/[^\s]*)?"
        )
        domains = re.findall(domain_pattern, content)

        # Filter out common tracking/social domains
        excluded_domains = {
            "mailchimp.com",
            "campaign-archive.com",
            "list-manage.com",
            "facebook.com",
            "twitter.com",
            "linkedin.com",
            "instagram.com",
            "youtube.com",
            "google.com",
            "tracking.com",
            "utm.com",
            "feedburner.com",
            "bit.ly",
            "tinyurl.com",
        }

        for domain in domains:
            domain_clean = domain.lower().strip()
            if domain_clean not in excluded_domains and "." in domain_clean:
                return AttributionInfo(
                    publisher=domain_clean,
                    original_url=f"https://{domain_clean}",
                    confidence_score=0.4,
                    extraction_method=self.strategy_name,
                )

        return None


class AttributionAnalyzer:
    """Analyzes content using multiple attribution strategies."""

    def __init__(self, strategies: List[AttributionStrategy]):
        """
        Initialize with a list of attribution strategies.

        Args:
            strategies: List of AttributionStrategy instances
        """
        self.strategies = strategies

    def analyze(self, content: str) -> Optional[AttributionInfo]:
        """
        Analyze content using all strategies and return the best match.

        Args:
            content: The content to analyze

        Returns:
            AttributionInfo with highest confidence score, or None if no attribution found
        """
        best_result = None
        best_score = 0.0

        for strategy in self.strategies:
            try:
                result = strategy.extract(content)
                if result and result.confidence_score > best_score:
                    best_result = result
                    best_score = result.confidence_score
                    logger.debug(
                        f"Better attribution found using {strategy.strategy_name}: {result.publisher} (score: {result.confidence_score})"
                    )
            except Exception as e:
                logger.warning(f"Error in strategy {strategy.strategy_name}: {e}")
                continue

        if best_result:
            logger.info(
                f"Best attribution: {best_result.publisher} using {best_result.extraction_method} (confidence: {best_result.confidence_score})"
            )

        return best_result
