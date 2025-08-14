"""RSS feed client for retrieving content from RSS sources."""

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

from src.core.utils import clean_article_title, extract_source_from_url

logger = logging.getLogger(__name__)


class RSSClient:
    """Client for fetching and parsing RSS feeds."""

    def __init__(self, feed_urls: List[str], settings=None):
        """Initialize RSS client.

        Args:
            feed_urls: List of RSS feed URLs to monitor
            settings: Settings instance for configuration values
        """
        self.feed_urls = feed_urls if feed_urls else []
        # Timeout configuration
        self.feed_timeout = settings.rss_feed_timeout if settings else 30.0
        self.content_timeout = settings.rss_content_timeout if settings else 15.0
        self.user_agent = (
            settings.default_user_agent if settings else "Newsletter-Bot/1.0"
        )

    async def get_recent_articles(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent articles from all RSS feeds.

        Args:
            days: Number of days back to fetch articles

        Returns:
            List of article dictionaries
        """
        if not self.feed_urls:
            logger.warning("No RSS feed URLs configured")
            return []

        all_articles = []
        threshold_date = datetime.utcnow() - timedelta(days=days)

        async with aiohttp.ClientSession() as session:
            tasks = []
            for feed_url in self.feed_urls:
                task = self._fetch_feed(session, feed_url.strip(), threshold_date)
                tasks.append(task)

            feed_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(feed_results):
                if isinstance(result, Exception):
                    logger.error(f"Error fetching feed {self.feed_urls[i]}: {result}")
                else:
                    all_articles.extend(result)

        # Sort by publication date (newest first)
        all_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        logger.info(
            f"Retrieved {len(all_articles)} articles from "
            f"{len(self.feed_urls)} RSS feeds"
        )
        return all_articles

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, feed_url: str, threshold_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch and parse a single RSS feed.

        Args:
            session: HTTP session
            feed_url: RSS feed URL
            threshold_date: Only include articles published after this date

        Returns:
            List of articles from this feed
        """
        try:
            headers = {"User-Agent": f"{self.user_agent} (RSS Reader)"}

            timeout = aiohttp.ClientTimeout(total=self.feed_timeout)
            async with session.get(
                feed_url, headers=headers, timeout=timeout
            ) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to fetch RSS feed {feed_url}: HTTP {response.status}"
                    )
                    return []

                content = await response.text()
                return await self._parse_rss(content, feed_url, threshold_date)

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching RSS feed: {feed_url}")
            return []
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error fetching RSS feed {feed_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching RSS feed {feed_url}: {e}")
            return []

    async def _parse_rss(
        self, xml_content: str, feed_url: str, threshold_date: datetime
    ) -> List[Dict[str, Any]]:
        """Parse RSS XML content.

        Args:
            xml_content: RSS XML string
            feed_url: Original feed URL
            threshold_date: Only include articles after this date

        Returns:
            List of parsed articles
        """
        try:
            root = ET.fromstring(xml_content)
            articles = []

            # Handle both RSS and Atom formats
            if root.tag == "rss":
                items = root.findall(".//item")
                feed_title = self._get_text(
                    root.find(".//channel/title"), "Unknown Feed"
                )
                # Channel description (not currently used)
                root.find(".//channel/description")
            elif root.tag == "{http://www.w3.org/2005/Atom}feed":
                # Atom feed
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                feed_title = self._get_text(
                    root.find(".//{http://www.w3.org/2005/Atom}title"), "Unknown Feed"
                )
                # Atom subtitle (not currently used)
                root.find(".//{http://www.w3.org/2005/Atom}subtitle")
            else:
                logger.warning(f"Unrecognized feed format for {feed_url}")
                return []

            for item in items:
                try:
                    article = await self._parse_item(
                        item, feed_url, feed_title, root.tag
                    )

                    # Filter by date if we can parse it
                    if article.get("published_at"):
                        try:
                            pub_date = datetime.fromisoformat(
                                article["published_at"].replace("Z", "+00:00")
                            )
                            if pub_date < threshold_date:
                                continue
                        except Exception:
                            pass  # If we can't parse date, include the article

                    articles.append(article)

                except Exception as e:
                    logger.debug(f"Error parsing RSS item: {e}")
                    continue

            logger.debug(f"Parsed {len(articles)} articles from {feed_title}")
            return articles

        except ET.ParseError as e:
            logger.error(f"XML parsing error for {feed_url}: {e}")
            return []
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"RSS parsing error for feed {feed_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing RSS feed {feed_url}: {e}")
            return []

    async def _parse_item(
        self, item: ET.Element, feed_url: str, feed_title: str, root_tag: str
    ) -> Dict[str, Any]:
        """Parse a single RSS/Atom item.

        Args:
            item: XML element for the item
            feed_url: Feed URL
            feed_title: Feed title
            root_tag: Root tag type (rss or atom)

        Returns:
            Parsed article dictionary
        """
        if root_tag == "rss":
            # RSS format
            title = self._get_text(item.find("title"), "Untitled")
            description = self._get_text(item.find("description"), "")
            link = self._get_text(item.find("link"), "")
            author = self._get_text(
                item.find("author"), self._get_text(item.find("dc:creator"), "")
            )
            pub_date = self._get_text(item.find("pubDate"), "")
            guid = self._get_text(item.find("guid"), "")

        else:
            # Atom format
            title = self._get_text(
                item.find(".//{http://www.w3.org/2005/Atom}title"), "Untitled"
            )
            summary_elem = item.find(".//{http://www.w3.org/2005/Atom}summary")
            content_elem = item.find(".//{http://www.w3.org/2005/Atom}content")
            description = self._get_text(content_elem or summary_elem, "")

            link_elem = item.find(
                './/{http://www.w3.org/2005/Atom}link[@rel="alternate"]'
            )
            if link_elem is None:
                link_elem = item.find(".//{http://www.w3.org/2005/Atom}link")
            link = link_elem.get("href", "") if link_elem is not None else ""

            author_elem = item.find(
                ".//{http://www.w3.org/2005/Atom}author/"
                "{http://www.w3.org/2005/Atom}name"
            )
            author = self._get_text(author_elem, "")

            pub_date = self._get_text(
                item.find(".//{http://www.w3.org/2005/Atom}published"),
                self._get_text(
                    item.find(".//{http://www.w3.org/2005/Atom}updated"), ""
                ),
            )
            guid = self._get_text(item.find(".//{http://www.w3.org/2005/Atom}id"), "")

        # Handle cases where title contains a URL (common in starred articles feeds)
        actual_article_url = None
        if title and title.strip():
            # Look for URLs in the title (like "[Firehose] https://example.com/")
            import re

            url_pattern = r"https?://[^\s\])]+"
            url_matches = re.findall(url_pattern, title)
            if url_matches:
                # Title contains a URL - use it as the article URL and generate a proper title
                actual_article_url = url_matches[0]  # Take the first URL found
                logger.debug(
                    f"Title contains URL: {actual_article_url} - will extract real title from article"
                )
                title = None  # Will be extracted from article content

        # Extract user highlights and insights from HTML description
        user_insights = ""
        description_clean = ""

        if description:
            user_insights = self._extract_user_insights(description)
            if user_insights:
                # Use user insights as the primary content
                description_clean = user_insights
            else:
                # Fallback to basic HTML cleaning
                import re

                description_clean = re.sub(r"<[^>]+>", "", description)
                description_clean = description_clean.strip()

        # Extract original article URL from the content, or use the URL from title
        original_url = (
            actual_article_url or self._extract_article_url(description) or link
        )

        # Fetch full article content from the original URL
        article_content = ""
        if original_url:
            try:
                article_content = await self._fetch_article_content(original_url)
                if article_content:
                    logger.debug(
                        f"Fetched {len(article_content)} chars of article content from {original_url}"
                    )
                else:
                    logger.warning(
                        f"Could not fetch article content from {original_url}"
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Network error fetching article content from {original_url}: {e}"
                )
            except Exception as e:
                logger.warning(
                    f"Unexpected error fetching article content from {original_url}: {e}"
                )

        # Extract real title from article content if title was a URL
        if title is None and article_content:
            # Title was a URL, extract real title from fetched content
            title = self._extract_title_from_content(article_content, original_url)
            if not title:
                title = "Article Summary"  # Fallback if extraction fails
        elif title is None:
            title = "Shared Article"  # Fallback if no content fetched

        # For RSS items, combine title + description + article content as raw input for LLM processing
        # This treats all of this as source material, not final content
        raw_title = clean_article_title(title)

        # Combine title, description, and fetched article content as comprehensive input for LLM
        # The LLM will generate proper title and content from this combined input
        input_parts = [raw_title]
        if description_clean:
            input_parts.append(f"User insights: {description_clean}")
        if article_content:
            input_parts.append(f"Article content: {article_content}")

        combined_input = "\n\n".join(input_parts)

        # Use a generic title that indicates this needs LLM processing
        # The actual title will be generated by the LLM commentary system
        display_title = (
            "Article Summary"
            if not raw_title or len(raw_title) < 10
            else raw_title[:100]
        )

        # Extract actual source from article URL instead of using generic feed title
        actual_source = extract_source_from_url(original_url) if original_url else None

        # Note: Web search fallback would go here but requires async context
        # TODO: Implement web search fallback for better source detection

        # Use actual source if available, otherwise fall back to feed title
        # Skip generic feed titles like "Starred Articles" in favor of actual source
        source_title = actual_source if actual_source else feed_title

        return {
            "id": guid or link,
            "title": display_title,  # Temporary title - LLM will generate the real one
            "content": combined_input,  # Combined title+description as LLM input
            "summary": (
                description_clean[:300] + "..."
                if len(description_clean) > 300
                else description_clean
            ),
            "source": "rss",
            "source_title": source_title,
            "source_url": feed_url,
            "url": original_url,  # Use extracted article URL instead of Feedbin redirect
            "author": author,
            "published_at": self._normalize_date(pub_date),
            "tags": [],  # RSS feeds typically don't have tags
            "needs_llm_processing": True,  # Flag to indicate this needs LLM processing
        }

    def _get_text(self, element: Optional[ET.Element], default: str = "") -> str:
        """Safely get text from XML element.

        Args:
            element: XML element or None
            default: Default value if element is None or empty

        Returns:
            Element text or default
        """
        if element is not None and element.text:
            return element.text.strip()
        return default

    def _normalize_date(self, date_str: str) -> str:
        """Normalize various date formats to ISO format.

        Args:
            date_str: Date string in various formats

        Returns:
            ISO formatted date string or original if parsing fails
        """
        if not date_str:
            return ""

        try:
            # Try common RSS date formats
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
        except Exception:
            try:
                # Try ISO format
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.isoformat()
            except Exception:
                # Return original if all parsing fails
                return date_str

    async def test_feeds(self) -> Dict[str, bool]:
        """Test connectivity to all configured RSS feeds.

        Returns:
            Dictionary mapping feed URLs to connection status
        """
        if not self.feed_urls:
            return {}

        results = {}

        async with aiohttp.ClientSession() as session:
            tasks = []
            for feed_url in self.feed_urls:
                task = self._test_feed(session, feed_url.strip())
                tasks.append(task)

            test_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(test_results):
                feed_url = self.feed_urls[i].strip()
                if isinstance(result, Exception):
                    results[feed_url] = False
                    logger.error(f"RSS feed test failed for {feed_url}: {result}")
                else:
                    results[feed_url] = result
                    if result:
                        logger.info(f"RSS feed test successful: {feed_url}")
                    else:
                        logger.warning(f"RSS feed test failed: {feed_url}")

        return results

    async def _test_feed(self, session: aiohttp.ClientSession, feed_url: str) -> bool:
        """Test a single RSS feed.

        Args:
            session: HTTP session
            feed_url: RSS feed URL

        Returns:
            True if feed is accessible, False otherwise
        """
        try:
            headers = {"User-Agent": f"{self.user_agent} (RSS Reader)"}
            timeout = aiohttp.ClientTimeout(total=self.feed_timeout)

            async with session.get(
                feed_url, headers=headers, timeout=timeout
            ) as response:
                if response.status == 200:
                    # Try to parse the XML content to verify it's valid
                    content = await response.text()
                    # Basic check for RSS/Atom content
                    if any(
                        tag in content.lower() for tag in ["<rss", "<feed", "<atom"]
                    ):
                        try:
                            # Try to parse full content as XML
                            ET.fromstring(content)
                            return True
                        except ET.ParseError:
                            # If full parse fails, it's still likely a valid feed
                            logger.debug(
                                f"XML parse failed for {feed_url}, but contains feed indicators"
                            )
                            return True
                    return False
                else:
                    return False

        except Exception:
            return False

    def _extract_user_insights(self, html_content: str) -> str:
        """Extract user's curated highlights and insights from Feedbin RSS description.

        Args:
            html_content: HTML content from RSS description containing user highlights

        Returns:
            Cleaned, structured summary based on user's insights
        """
        if not html_content:
            return ""

        from html import unescape

        try:
            # Remove HTML tags but preserve structure
            text = re.sub(r"<div[^>]*>", "\n", html_content)
            text = re.sub(r"</div>", "", text)
            text = re.sub(r"<ul[^>]*>", "\n", text)
            text = re.sub(r"</ul>", "", text)
            text = re.sub(r"<li[^>]*>", "• ", text)
            text = re.sub(r"</li>", "\n", text)
            text = re.sub(r"<p[^>]*>", "", text)
            text = re.sub(r"</p>", "\n", text)
            text = re.sub(r"<br[^>]*>", "\n", text)
            text = re.sub(r"<span[^>]*>", "", text)
            text = re.sub(r"</span>", "", text)
            text = re.sub(r"<b>", "**", text)
            text = re.sub(r"</b>", "**", text)
            text = re.sub(r"<strong>", "**", text)
            text = re.sub(r"</strong>", "**", text)

            # Remove any remaining HTML tags
            text = re.sub(r"<[^>]+>", "", text)

            # Unescape HTML entities
            text = unescape(text)

            # Clean up whitespace and empty lines
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            # Filter out signature blocks and metadata
            filtered_lines = []
            for line in lines:
                # Skip signature blocks, email metadata, and URLs at the end
                if any(
                    skip_phrase in line.lower()
                    for skip_phrase in [
                        "protonmail",
                        "signature_block",
                        "class=",
                        "style=",
                        "font-family",
                        "https://feedbin",
                        "feedbinusercontent.com",
                    ]
                ):
                    continue

                # Keep lines that start with bullet points, emojis, or are substantial insights
                if (
                    line.startswith("•")
                    or line.startswith("-")
                    or any(
                        emoji in line
                        for emoji in [
                            "📚",
                            "☕",
                            "🤖",
                            "⚔️",
                            "🌍",
                            "🏛️",
                            "✊",
                            "📊",
                            "🏢",
                            "👥",
                            "🔄",
                            "🔍",
                            "📱",
                            "📜",
                            "⚠️",
                        ]
                    )
                    or (len(line) > 50 and "**" in line)
                ):
                    filtered_lines.append(line)

            # If we found structured insights, use them
            if filtered_lines:
                insights = "\n".join(filtered_lines)
                # Limit length for newsletter summary
                if len(insights) > 500:
                    # Take first few insights and add continuation
                    truncated = "\n".join(filtered_lines[:3])
                    if len(truncated) > 400:
                        truncated = truncated[:400] + "..."
                    return truncated
                return insights

            # Fallback: return first substantial paragraph if no structured insights found
            for line in lines:
                if len(line) > 100 and not line.startswith("http"):
                    return line[:300] + "..." if len(line) > 300 else line

            return ""

        except Exception as e:
            logger.debug(f"Error extracting user insights: {e}")
            return ""

    async def _fetch_article_content(self, url: str) -> str:
        """Fetch full article content from URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # Use the same session from the parent call
            timeout = aiohttp.ClientTimeout(total=self.content_timeout)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=timeout
                ) as response:
                    if response.status == 200:
                        # Handle potential encoding issues gracefully
                        try:
                            html = await response.text()
                        except UnicodeDecodeError:
                            # Try with latin-1 encoding for problematic content
                            raw_content = await response.read()
                            html = raw_content.decode("latin-1", errors="ignore")

                        # Extract clean article content using BeautifulSoup
                        import re

                        soup = BeautifulSoup(html, "html.parser")

                        # Remove script, style, nav, footer, ads
                        for tag in soup(
                            ["script", "style", "nav", "footer", "aside", "iframe"]
                        ):
                            tag.decompose()

                        # Try to find article content
                        article_content = None
                        for selector in [
                            "article",
                            ".article-content",
                            ".post-content",
                            ".entry-content",
                            "main",
                        ]:
                            content = soup.select_one(selector)
                            if content:
                                article_content = content.get_text(strip=True)
                                break

                        if not article_content:
                            # Fallback to body content
                            article_content = soup.get_text(strip=True)

                        # Clean up the text
                        article_content = re.sub(r"\s+", " ", article_content)
                        article_content = re.sub(r"\n+", "\n", article_content)

                        # Limit length for LLM processing
                        if len(article_content) > 8000:
                            article_content = article_content[:8000] + "..."

                        return article_content
                    else:
                        logger.warning(f"Failed to fetch article: {response.status}")
                        return ""

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error fetching article content: {e}")
            return ""
        except (ValueError, TypeError) as e:
            logger.error(f"Data processing error fetching article content: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error fetching article content: {e}")
            return ""

    def _extract_article_url(self, html_content: str) -> str:
        """Extract the original article URL from RSS content.

        Args:
            html_content: HTML content from RSS description

        Returns:
            Original article URL or empty string if not found
        """
        if not html_content:
            return ""

        try:
            # Look for URLs that are not Feedbin URLs
            url_pattern = r'https?://[^\s<>"\']+'
            urls = re.findall(url_pattern, html_content)

            for url in urls:
                # Skip Feedbin internal URLs and email tracking
                if any(
                    skip_domain in url
                    for skip_domain in [
                        "feedbin.com",
                        "feedbinusercontent.com",
                        "protonmail.com",
                        "sfmc_id=",
                        "utm_source=",
                        "utm_medium=email",
                    ]
                ):
                    continue

                # Clean up URL (remove trailing punctuation, URL parameters for tracking)
                url = url.rstrip(".,;")  # Remove trailing punctuation

                # Remove common tracking parameters but keep essential ones
                if "?" in url:
                    base_url, params = url.split("?", 1)
                    # Keep only essential parameters, remove tracking
                    essential_params = []
                    for param in params.split("&"):
                        if param.startswith(
                            ("v=", "id=", "p=", "article=")
                        ) and not param.startswith(("utm_", "sfmc_", "j=")):
                            essential_params.append(param)

                    if essential_params:
                        url = base_url + "?" + "&".join(essential_params)
                    else:
                        url = base_url

                return url

            return ""

        except Exception as e:
            logger.debug(f"Error extracting article URL: {e}")
            return ""

    def _extract_title_from_content(self, content: str, url: str) -> str:
        """Extract a meaningful title from article content.

        Args:
            content: Full article content text
            url: Source URL for context

        Returns:
            Extracted title or empty string if extraction fails
        """
        try:
            # Split content into lines and look for title patterns
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            if not lines:
                return ""

            # Strategy 1: Look for lines that appear to be titles (shorter, no periods)
            for line in lines[:10]:  # Check first 10 lines
                # Skip very short lines or lines with URLs
                if (
                    len(line) < 10
                    or line.startswith("http")
                    or line.lower().startswith("[firehose]")
                ):
                    continue

                # Skip lines that look like descriptions (too long, end with periods)
                if len(line) > 120 or line.endswith(".") or line.endswith("..."):
                    continue

                # Skip lines with too many special characters
                special_chars = sum(1 for c in line if c in ".,;:!?()[]{}")
                if special_chars > len(line) * 0.3:
                    continue

                # This looks like a title
                return line[:100]  # Limit title length

            # Strategy 2: Take first substantial line that doesn't end with period
            for line in lines[:5]:
                if len(line) >= 20 and len(line) <= 100 and not line.endswith("."):
                    return line

            # Strategy 3: Take first line if it's reasonable
            first_line = lines[0] if lines else ""
            if len(first_line) >= 10 and len(first_line) <= 150:
                # Clean up the first line
                if first_line.endswith("."):
                    first_line = first_line[:-1]
                return first_line[:100]

            return ""

        except Exception as e:
            logger.debug(f"Error extracting title from content: {e}")
            return ""
