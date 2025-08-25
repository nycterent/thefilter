#!/usr/bin/env python3
"""
Simplified Source Resolver for Newsletter Integration

Focused on practical source resolution for newsletter generation.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class NewsletterSourceResolver:
    """Simple, synchronous source resolver for newsletter integration."""

    # Known intermediary patterns that need resolution
    INTERMEDIARY_PATTERNS = {
        # Newsletter archive codes (Us7, US17, etc.)
        "newsletter_codes": r"\b[Uu]s\d+\b|\b[A-Z]{2,3}\d+\b",
        # Newsletter platforms
        "mailchimp": r"https?://[^.]+\.campaign-archive\.com/",
        "buttondown": r"https?://buttondown\.com/[^/]+/archive/",
        "substack": r"https?://[^.]+\.substack\.com/p/",
        # Social aggregators
        "hackernews": r"https?://news\.ycombinator\.com/item\?id=\d+",
        "reddit": r"https?://(?:www\.)?reddit\.com/r/[^/]+/comments/",
    }

    # Title extraction patterns - focused on newsletter content
    TITLE_EXTRACTION_RULES = [
        # Exact quoted titles
        r'"([^"]{15,120})"',
        # Numbered findings/lessons pattern
        r"(\d+\s+(?:Surprising\s+)?(?:Lessons?|Facts?|Insights?|Findings?)\s+[^.!?]{10,80})",
        # Capitalized headlines (likely article titles)
        r"^([A-Z][^.!?]{20,100}[.!?]?)$",
        # Study/research patterns
        r"((?:Study|Research|Survey|Report):\s*[A-Z][^.!?]{15,80})",
        # Common headline patterns
        r"([A-Z][^:]{15,80}:\s*[A-Z][^.!?]{15,60})",
    ]

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0)"}
        )

        return session

    def is_intermediary_source(self, url: str, content: str = "") -> bool:
        """Check if URL/content indicates an intermediary source."""
        # Check URL patterns
        for platform, pattern in self.INTERMEDIARY_PATTERNS.items():
            if re.search(pattern, url, re.IGNORECASE):
                return True

        # Check for newsletter codes in content
        if re.search(self.INTERMEDIARY_PATTERNS["newsletter_codes"], content):
            return True

        # Check suspicious domains
        domain = urlparse(url).netloc.lower()
        suspicious = ["campaign-archive.com", "mailchi.mp", "mailchimp.com"]

        return any(sus in domain for sus in suspicious)

    def extract_article_title(self, content: str) -> Optional[str]:
        """Extract article title from newsletter content."""
        # Clean content
        content = re.sub(r"<[^>]+>", "", content)  # Remove HTML
        content = re.sub(r"\s+", " ", content)  # Normalize whitespace

        # Try each extraction rule
        for pattern in self.TITLE_EXTRACTION_RULES:
            matches = re.findall(pattern, content, re.MULTILINE | re.IGNORECASE)
            if matches:
                for match in matches:
                    title = match.strip().strip("\"'")

                    # Quality checks
                    if (
                        15 <= len(title) <= 120
                        and len(title.split()) >= 4
                        and not title.lower().startswith(
                            ("read more", "source", "click")
                        )
                    ):
                        return title

        return None

    def search_google_for_source(self, title: str) -> Optional[str]:
        """Search Google for original source using title."""
        if not title or len(title) < 15:
            return None

        try:
            # Clean title for search
            search_title = re.sub(r"[^\w\s-]", " ", title).strip()
            search_query = f'"{search_title}"'

            # Google search URL
            search_url = "https://www.google.com/search"
            params = {"q": search_query, "num": 10, "hl": "en"}

            response = self.session.get(search_url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                html = response.text

                # Extract URLs from search results - prioritize quality sources
                quality_patterns = [
                    # Academic/Research sources
                    r'https?://[^"]*(?:\.edu|\.org|nature\.com|science\.org|nejm\.org)[^"]*',
                    # News sources
                    r'https?://(?:www\.)?(?:bbc\.com|cnn\.com|reuters\.com|nytimes\.com)[^"]*',
                    # Tech/Research sites
                    r'https?://[^"]*(?:clearerthinking\.org|lessswrong\.com|arxiv\.org)[^"]*',
                    # General quality sites (avoiding intermediaries)
                    r'https?://[^"]*\.(?:com|org|net)/[^"]*',
                ]

                for pattern in quality_patterns:
                    urls = re.findall(pattern, html, re.IGNORECASE)
                    if urls:
                        # Filter out obvious bad URLs
                        good_urls = [
                            url
                            for url in urls[:5]
                            if not any(
                                bad in url.lower()
                                for bad in [
                                    "google.",
                                    "facebook.",
                                    "twitter.",
                                    "linkedin.",
                                    "campaign-archive",
                                    "mailchimp",
                                    "youtube.",
                                ]
                            )
                        ]

                        if good_urls:
                            return good_urls[0]  # Return first quality match

        except Exception as e:
            logger.error(f"Google search error for '{title}': {e}")

        return None

    def resolve_source(self, url: str, content: str) -> Dict[str, any]:
        """
        Main resolution method.

        Returns:
            {
                'original_url': str,
                'resolved_url': str or None,
                'title': str or None,
                'is_intermediary': bool,
                'method': str,
                'success': bool
            }
        """
        result = {
            "original_url": url,
            "resolved_url": None,
            "title": None,
            "is_intermediary": False,
            "method": "unknown",
            "success": False,
        }

        # Step 1: Check if intermediary
        is_intermediary = self.is_intermediary_source(url, content)
        result["is_intermediary"] = is_intermediary

        if not is_intermediary:
            result["resolved_url"] = url
            result["method"] = "direct"
            result["success"] = True
            return result

        # Step 2: Extract title
        title = self.extract_article_title(content)
        result["title"] = title

        if not title:
            result["method"] = "failed_title_extraction"
            return result

        # Step 3: Search for original source
        original_url = self.search_google_for_source(title)

        if original_url:
            result["resolved_url"] = original_url
            result["method"] = "google_search"
            result["success"] = True
        else:
            result["method"] = "search_failed"

        return result

    def batch_resolve(self, url_content_pairs: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        Resolve multiple sources and return URL mapping.

        Args:
            url_content_pairs: List of (url, content) tuples

        Returns:
            Dict mapping original_url -> resolved_url
        """
        resolved_mapping = {}

        for url, content in url_content_pairs:
            try:
                result = self.resolve_source(url, content)
                resolved_mapping[url] = result["resolved_url"] or url

                if result["success"] and result["resolved_url"] != url:
                    logger.info(f"✅ Resolved: {url} -> {result['resolved_url']}")

            except Exception as e:
                logger.error(f"Resolution error for {url}: {e}")
                resolved_mapping[url] = url  # Fallback to original

        return resolved_mapping


# Integration helper functions


def resolve_newsletter_links(articles: List[Dict]) -> List[Dict]:
    """
    Resolve intermediary links in newsletter articles.

    Args:
        articles: List of article dicts with 'url' and 'content' keys

    Returns:
        Articles with resolved URLs
    """
    resolver = NewsletterSourceResolver()

    for article in articles:
        if "url" in article and "content" in article:
            result = resolver.resolve_source(article["url"], article["content"])

            if result["success"] and result["resolved_url"]:
                article["original_url"] = article["url"]
                article["url"] = result["resolved_url"]
                article["source_resolution"] = result["method"]

                logger.info(
                    f"Resolved article URL: {article['original_url']} -> {article['url']}"
                )

    return articles


# CLI tool for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python source_resolver.py <url> <content>")
        sys.exit(1)

    url = sys.argv[1]
    content = sys.argv[2]

    resolver = NewsletterSourceResolver()
    result = resolver.resolve_source(url, content)

    print("Source Resolution Result:")
    print(f"  Original URL: {result['original_url']}")
    print(f"  Resolved URL: {result['resolved_url']}")
    print(f"  Title: {result['title']}")
    print(f"  Is Intermediary: {result['is_intermediary']}")
    print(f"  Method: {result['method']}")
    print(f"  Success: {result['success']}")
