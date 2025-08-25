#!/usr/bin/env python3
"""
Universal Source Extractor for Newsletter Content

Identifies intermediary sources (newsletter archives, aggregators) and extracts
original primary sources using pattern matching and web search.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class SourceExtraction:
    """Result of source extraction attempt."""

    original_url: str
    final_url: Optional[str]
    title: Optional[str]
    extraction_method: str
    confidence: float
    is_intermediary: bool


class NewsletterSourceExtractor:
    """Extracts primary sources from newsletter intermediary links."""

    # Known newsletter archive patterns
    INTERMEDIARY_PATTERNS = {
        # Newsletter platforms
        "mailchimp": r"https?://[^.]+\.campaign-archive\.com/",
        "buttondown": r"https?://buttondown\.com/[^/]+/archive/",
        "substack": r"https?://[^.]+\.substack\.com/p/",
        "convertkit": r"https?://[^.]+\.ck\.page/",
        "beehiiv": r"https?://[^.]+\.beehiiv\.com/",
        # Aggregator codes (like US7, Us17, etc.)
        "newsletter_codes": r"\b[Uu]s\d+\b|\b[A-Z]{2,3}\d+\b",
        # Social aggregators
        "hackernews": r"https?://news\.ycombinator\.com/item\?id=\d+",
        "reddit": r"https?://(?:www\.)?reddit\.com/r/[^/]+/comments/",
        # Content aggregators
        "morning_brew": r"https?://[^.]*morningbrew[^.]*\.com/",
        "the_hustle": r"https?://[^.]*thehustle[^.]*\.com/",
    }

    # Patterns to extract titles from content
    TITLE_PATTERNS = [
        # Common title formats in newsletters
        r'"([^"]+)".*?(?:Read more:|Source:|→)',
        r"([A-Z][^.!?]*[.!?])\s*(?:Read more:|Source:|→)",
        r"### ([^\n]+)",
        r"## ([^\n]+)",
        r"# ([^\n]+)",
        # Specific patterns
        r"(\d+\s+[A-Z][^.!?]*\s+(?:Lessons?|Facts?|Insights?)[^.!?]*)",
        r"([A-Z][^:]*:\s*[A-Z][^.!?]*)",
    ]

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "Mozilla/5.0 (compatible; SourceExtractor/1.0)"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def identify_intermediary(self, url: str, content: str = "") -> Tuple[bool, str]:
        """
        Identify if a URL is an intermediary source.

        Returns:
            (is_intermediary, platform_type)
        """
        for platform, pattern in self.INTERMEDIARY_PATTERNS.items():
            if re.search(pattern, url, re.IGNORECASE):
                return True, platform

        # Check for newsletter codes in content
        if re.search(self.INTERMEDIARY_PATTERNS["newsletter_codes"], content):
            return True, "newsletter_codes"

        # Domain-based detection
        domain = urlparse(url).netloc.lower()
        suspicious_domains = [
            "campaign-archive.com",
            "mailchimp.com",
            "constantcontact.com",
            "us1.campaign-archive.com",
            "us7.campaign-archive.com",
            "mailchi.mp",
            "hs-sites.com",
        ]

        if any(sus_domain in domain for sus_domain in suspicious_domains):
            return True, "email_platform"

        return False, "direct"

    def extract_title_from_content(self, content: str, url: str = "") -> Optional[str]:
        """Extract article title from newsletter content."""
        # Clean content for better matching
        content = re.sub(r"<[^>]+>", "", content)  # Remove HTML
        content = re.sub(r"\s+", " ", content)  # Normalize whitespace

        for pattern in self.TITLE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            if matches:
                # Take the longest meaningful match
                title = max(matches, key=len).strip()
                # Clean up the title
                title = re.sub(r'^["\']|["\']$', "", title)  # Remove quotes
                title = re.sub(r"\s+", " ", title)  # Normalize spaces

                # Validate title quality
                if (
                    len(title) > 10
                    and not title.lower().startswith(("read more", "source", "link"))
                    and len(title.split()) >= 3
                ):
                    return title

        return None

    async def search_for_original_source(
        self, title: str, context: str = ""
    ) -> Optional[str]:
        """Search for original source using article title."""
        if not title:
            return None

        # Clean title for search
        search_title = re.sub(r"[^\w\s-]", "", title).strip()
        if len(search_title) < 10:
            return None

        try:
            # Use Google search to find original source
            search_query = f'"{search_title}"'
            search_url = f"https://www.google.com/search?q={search_query}"

            async with self.session.get(search_url) as response:
                if response.status == 200:
                    html = await response.text()

                    # Extract URLs from Google search results
                    # Look for news sites, academic journals, official sources
                    url_patterns = [
                        r'https?://[^"]*(?:\.edu|\.org|\.gov)[^"]*',
                        r'https?://(?:www\.)?(?:nature|science|cell|nejm|bmj)\.com[^"]*',
                        r'https?://(?:www\.)?(?:bbc|cnn|reuters|ap|nytimes)\.com[^"]*',
                        r'https?://[^"]*\.(?:com|net|io)/[^"]*(?:study|research|paper|article)[^"]*',
                    ]

                    for pattern in url_patterns:
                        urls = re.findall(pattern, html, re.IGNORECASE)
                        if urls:
                            # Return first high-quality match
                            for url in urls[:3]:  # Check top 3 matches
                                if await self._validate_source_quality(url, title):
                                    return url

        except Exception as e:
            logger.error(f"Search error for '{title}': {e}")

        return None

    async def _validate_source_quality(self, url: str, expected_title: str) -> bool:
        """Validate that a URL contains the expected content."""
        try:
            # Quick check - avoid obvious intermediaries
            domain = urlparse(url).netloc.lower()
            if any(
                bad in domain for bad in ["campaign-archive", "mailchimp", "google.com"]
            ):
                return False

            # Fetch and check title similarity
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()

                    # Extract page title
                    title_match = re.search(
                        r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE
                    )
                    if title_match:
                        page_title = title_match.group(1).strip()

                        # Check title similarity (simple word overlap)
                        expected_words = set(expected_title.lower().split())
                        page_words = set(page_title.lower().split())

                        overlap = len(expected_words.intersection(page_words))
                        similarity = overlap / max(len(expected_words), len(page_words))

                        return similarity > 0.3  # 30% word overlap threshold

        except Exception as e:
            logger.debug(f"Validation error for {url}: {e}")

        return False

    async def extract_source(self, url: str, content: str = "") -> SourceExtraction:
        """
        Main extraction method - identifies and resolves intermediary sources.

        Args:
            url: The potentially intermediary URL
            content: Newsletter content containing the article

        Returns:
            SourceExtraction with resolution results
        """
        # Step 1: Check if URL is intermediary
        is_intermediary, platform = self.identify_intermediary(url, content)

        if not is_intermediary:
            return SourceExtraction(
                original_url=url,
                final_url=url,
                title=None,
                extraction_method="direct",
                confidence=1.0,
                is_intermediary=False,
            )

        # Step 2: Extract title from content
        title = self.extract_title_from_content(content, url)

        if not title:
            return SourceExtraction(
                original_url=url,
                final_url=None,
                title=None,
                extraction_method="failed_title_extraction",
                confidence=0.0,
                is_intermediary=True,
            )

        # Step 3: Search for original source
        original_url = await self.search_for_original_source(title, content)

        if original_url:
            return SourceExtraction(
                original_url=url,
                final_url=original_url,
                title=title,
                extraction_method="search_resolution",
                confidence=0.8,
                is_intermediary=True,
            )

        # Step 4: Fallback - return with extracted title but no resolution
        return SourceExtraction(
            original_url=url,
            final_url=None,
            title=title,
            extraction_method="title_only",
            confidence=0.3,
            is_intermediary=True,
        )

    async def batch_extract(
        self, url_content_pairs: List[Tuple[str, str]]
    ) -> List[SourceExtraction]:
        """Extract sources for multiple URLs concurrently."""
        tasks = [
            self.extract_source(url, content) for url, content in url_content_pairs
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)


# Utility functions for integration


async def resolve_newsletter_sources(
    url_content_pairs: List[Tuple[str, str]],
) -> Dict[str, str]:
    """
    Resolve newsletter intermediary sources to primary sources.

    Returns:
        Dict mapping original_url -> resolved_url (or original if no resolution)
    """
    async with NewsletterSourceExtractor() as extractor:
        results = await extractor.batch_extract(url_content_pairs)

        resolved_urls = {}
        for result, (original_url, _) in zip(results, url_content_pairs):
            if isinstance(result, SourceExtraction):
                resolved_urls[original_url] = result.final_url or original_url
            else:
                # Handle exceptions
                logger.error(f"Extraction failed for {original_url}: {result}")
                resolved_urls[original_url] = original_url

        return resolved_urls


# Example usage and testing
if __name__ == "__main__":
    import asyncio

    async def test_extractor():
        """Test the source extractor with known examples."""
        test_cases = [
            (
                "https://us7.campaign-archive.com/some-link",
                "4 Surprising Lessons from Running a Giant Study on IQ\n\nRead more: Us7 - this url should be clearthinking",
            ),
            (
                "https://news.ycombinator.com/item?id=41139854",
                "Discussion about marshmallow test research and delayed gratification studies",
            ),
        ]

        async with NewsletterSourceExtractor() as extractor:
            for url, content in test_cases:
                result = await extractor.extract_source(url, content)
                print(f"URL: {url}")
                print(f"Title: {result.title}")
                print(f"Resolved: {result.final_url}")
                print(f"Method: {result.extraction_method}")
                print(f"Confidence: {result.confidence}")
                print("---")

    # Run test
    # asyncio.run(test_extractor())
