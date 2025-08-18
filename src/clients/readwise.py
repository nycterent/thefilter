"""Readwise API client for retrieving highlights and notes."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiohttp
from bs4 import BeautifulSoup

from src.core.utils import extract_source_from_url

logger = logging.getLogger(__name__)


class ReadwiseClient:
    """Client for Readwise API to fetch highlights and notes."""

    def __init__(self, api_key: str, settings=None):
        """Initialize Readwise client.

        Args:
            api_key: Readwise API key
            settings: Settings instance for configuration values
        """
        self.api_key = api_key
        self.base_url = "https://readwise.io/api/v2"
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }
        # Timeout configuration
        self.timeout = settings.readwise_timeout if settings else 15.0

    async def get_recent_highlights(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent highlights from Readwise.

        Args:
            days: Number of days back to fetch highlights

        Returns:
            List of highlight dictionaries
        """
        if not self.api_key:
            logger.error("No Readwise API key provided. Cannot connect to Readwise.")
            return []
        try:
            # Calculate date threshold
            threshold_date = datetime.utcnow() - timedelta(days=days)
            updated_after = threshold_date.strftime("%Y-%m-%dT%H:%M:%S")

            url = f"{self.base_url}/highlights/"
            params = {"updated__gt": updated_after, "page_size": 1000}  # Max page size

            highlights = []
            page = 1

            async with aiohttp.ClientSession() as session:
                while True:
                    params["page"] = page

                    async with session.get(
                        url, headers=self.headers, params=params
                    ) as response:
                        if response.status != 200:
                            logger.error(
                                f"Readwise API error: {response.status}. "
                                f"URL: {url} Params: {params}"
                            )
                            try:
                                error_detail = await response.text()
                                logger.error(f"Readwise error detail: {error_detail}")
                            except Exception:
                                pass
                            break

                        data = await response.json()
                        page_highlights = data.get("results", [])

                        if not page_highlights:
                            logger.info("No highlights returned from Readwise.")
                            break

                        # Process highlights
                        for highlight in page_highlights:
                            # Handle date fields properly - prefer updated_at if created_at is missing
                            created_at = highlight.get("created_at") or highlight.get(
                                "updated_at"
                            )
                            updated_at = highlight.get("updated_at") or highlight.get(
                                "created_at"
                            )

                            # Fetch full article content if source URL is available
                            source_url = highlight.get("source_url")
                            article_content = ""
                            if source_url:
                                try:
                                    article_content = await self._fetch_article_content(
                                        source_url
                                    )
                                    if article_content:
                                        logger.debug(
                                            f"Fetched {len(article_content)} chars of article content from {source_url}"
                                        )
                                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                                    logger.warning(
                                        f"Network error fetching article content from {source_url}: {e}"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Unexpected error fetching article content from {source_url}: {e}"
                                    )

                            # Combine highlight text, note, and article content for comprehensive LLM input
                            highlight_text = highlight.get("text", "")
                            note_text = highlight.get("note", "")

                            # Build comprehensive content for LLM processing
                            content_parts = []
                            if highlight_text:
                                content_parts.append(f"Highlight: {highlight_text}")
                            if note_text:
                                content_parts.append(f"Note: {note_text}")
                            if article_content:
                                content_parts.append(
                                    f"Article content: {article_content}"
                                )

                            combined_content = (
                                "\n\n".join(content_parts)
                                if content_parts
                                else highlight_text
                            )

                            # Extract actual source from URL instead of generic book title
                            actual_source = None
                            if source_url:
                                actual_source = extract_source_from_url(source_url)

                            # Use actual source or fall back to book title, but prefer URL-based source
                            source_title = (
                                actual_source
                                if actual_source
                                else highlight.get("book_title", "Unknown")
                            )

                            processed_highlight = {
                                "id": highlight.get("id"),
                                "title": (
                                    highlight_text[:200] + "..."
                                    if len(highlight_text) > 200
                                    else highlight_text
                                ),
                                "content": combined_content,  # Combined content for LLM processing
                                "note": note_text,
                                "source": "readwise",
                                "source_title": source_title,
                                "author": highlight.get("author", "Unknown"),
                                "url": source_url,
                                "tags": highlight.get("tags", []),
                                "created_at": created_at,
                                "updated_at": updated_at,
                                "location": highlight.get("location"),
                                "location_type": highlight.get("location_type"),
                                "needs_llm_processing": bool(
                                    article_content
                                ),  # Flag if we have full article content
                            }
                            highlights.append(processed_highlight)

                        # Check if there are more pages
                        if not data.get("next"):
                            break

                        page += 1

                        # Rate limiting - be respectful
                        await asyncio.sleep(0.1)

            logger.info(f"Retrieved {len(highlights)} highlights from Readwise")
            return highlights

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(
                f"Network error fetching Readwise highlights: {e}", exc_info=True
            )
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                f"Data parsing error fetching Readwise highlights: {e}", exc_info=True
            )
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error fetching Readwise highlights: {e}", exc_info=True
            )
            return []

    async def get_recent_reader_documents(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get curated documents from Readwise Reader (only 'twiar' tagged articles).

        Args:
            days: Number of days back to fetch documents (default 7 days)

        Returns:
            List of curated Reader document dictionaries
        """
        if not self.api_key:
            logger.error(
                "No Readwise API key provided. Cannot connect to Readwise Reader."
            )
            return []

        try:
            threshold_date = datetime.utcnow() - timedelta(days=days)
            updated_after = threshold_date.strftime("%Y-%m-%dT%H:%M:%SZ")

            url = "https://readwise.io/api/v3/list/"
            params = {
                "updatedAfter": updated_after,
            }

            all_documents = []
            page_cursor = None

            async with aiohttp.ClientSession() as session:
                while True:
                    if page_cursor:
                        params["pageCursor"] = page_cursor

                    async with session.get(
                        url, headers=self.headers, params=params
                    ) as response:
                        if response.status != 200:
                            logger.error(
                                f"Readwise Reader API error: {response.status}. "
                                f"URL: {url} Params: {params}"
                            )
                            try:
                                error_detail = await response.text()
                                logger.error(
                                    f"Readwise Reader error detail: {error_detail}"
                                )
                            except Exception:
                                pass
                            break

                        data = await response.json()
                        page_documents = data.get("results", [])

                        if not page_documents:
                            break

                        all_documents.extend(page_documents)

                        # Check if there are more pages
                        page_cursor = data.get("nextPageCursor")
                        if not page_cursor:
                            break

                        # Rate limiting - Reader API is 20 requests per minute
                        await asyncio.sleep(3)  # 3 seconds between requests

            # Filter for high-quality curated articles
            curated_documents = self._filter_curated_articles(all_documents)

            logger.info(
                f"Retrieved {len(curated_documents)} curated articles from {len(all_documents)} total documents"
            )
            return curated_documents

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error fetching Readwise Reader documents: {e}")
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error fetching Readwise Reader documents: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Readwise Reader documents: {e}")
            return []

    def _filter_curated_articles(
        self, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter documents to only include curated articles (only 'twiar' tagged).

        Args:
            documents: All documents from API

        Returns:
            Filtered list of curated articles
        """
        curated = []

        for doc in documents:
            reading_progress = doc.get("reading_progress", 0)
            tags = doc.get("tags", {})

            is_fully_read = reading_progress and reading_progress >= 1.0
            has_twiar_tag = self._has_twiar_tag(tags)

            # Include ONLY articles with twiar tag (not just fully read)
            if has_twiar_tag:
                curated.append(doc)

        # Sort by reading progress (fully read first) then by date
        curated.sort(
            key=lambda x: (
                -(x.get("reading_progress", 0) or 0),  # Fully read first
                x.get("created_at", "") or "",  # Then by date
            ),
            reverse=True,
        )

        return curated

    def _has_twiar_tag(self, tags) -> bool:
        """Check if document has 'twiar' tag (case-insensitive)."""
        if not tags:
            return False

        if isinstance(tags, dict):
            return any(
                "twiar" in tag_name.lower() for tag_name in tags.keys() if tag_name
            )
        elif isinstance(tags, list):
            return any("twiar" in str(tag).lower() for tag in tags if tag)

        return False

    async def get_books(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent books from Readwise.

        Args:
            days: Number of days back to fetch books

        Returns:
            List of book dictionaries
        """
        try:
            threshold_date = datetime.utcnow() - timedelta(days=days)
            updated_after = threshold_date.strftime("%Y-%m-%dT%H:%M:%S")

            url = f"{self.base_url}/books/"
            params = {"updated__gt": updated_after, "page_size": 1000}

            books = []

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        books = data.get("results", [])
                        logger.info(f"Retrieved {len(books)} books from Readwise")

            return books

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error fetching Readwise books: {e}")
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error fetching Readwise books: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Readwise books: {e}")
            return []

    async def _fetch_article_content(self, url: str) -> str:
        """Fetch full article content from URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            timeout = aiohttp.ClientTimeout(total=self.timeout)
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

    async def test_connection(self) -> bool:
        """Test the Readwise API connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.base_url}/auth/"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    # 200 = OK with content, 204 = OK no content (both valid for auth)
                    if response.status in [200, 204]:
                        logger.info("Readwise API connection successful")
                        return True
                    else:
                        logger.error(
                            f"Readwise API connection failed: {response.status}"
                        )
                        try:
                            error_detail = await response.text()
                            logger.error(f"Readwise error detail: {error_detail}")
                        except Exception:
                            pass
                        return False

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error testing Readwise connection: {e}")
            return False
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Response parsing error testing Readwise connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing Readwise connection: {e}")
            return False
