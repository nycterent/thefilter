"""Readwise API client for retrieving highlights and notes."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

import aiohttp

logger = logging.getLogger(__name__)


class ReadwiseClient:
    """Client for Readwise API to fetch highlights and notes."""

    def __init__(self, api_key: str):
        """Initialize Readwise client.

        Args:
            api_key: Readwise API key
        """
        self.api_key = api_key
        self.base_url = "https://readwise.io/api/v2"
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def get_recent_highlights(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent highlights from Readwise.

        Args:
            days: Number of days back to fetch highlights

        Returns:
            List of highlight dictionaries
        """
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
                            logger.error(f"Readwise API error: {response.status}")
                            break

                        data = await response.json()
                        page_highlights = data.get("results", [])

                        if not page_highlights:
                            break

                        # Process highlights
                        for highlight in page_highlights:
                            processed_highlight = {
                                "id": highlight.get("id"),
                                "title": (
                                    highlight.get("text", "")[:200] + "..."
                                    if len(highlight.get("text", "")) > 200
                                    else highlight.get("text", "")
                                ),
                                "content": highlight.get("text", ""),
                                "note": highlight.get("note", ""),
                                "source": "readwise",
                                "source_title": highlight.get("book_title", "Unknown"),
                                "author": highlight.get("author", "Unknown"),
                                "url": highlight.get("source_url"),
                                "tags": highlight.get("tags", []),
                                "created_at": highlight.get("created_at"),
                                "updated_at": highlight.get("updated_at"),
                                "location": highlight.get("location"),
                                "location_type": highlight.get("location_type"),
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

        except Exception as e:
            logger.error(f"Error fetching Readwise highlights: {e}")
            return []

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

        except Exception as e:
            logger.error(f"Error fetching Readwise books: {e}")
            return []

    async def test_connection(self) -> bool:
        """Test the Readwise API connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            url = f"{self.base_url}/auth/"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        logger.info("Readwise API connection successful")
                        return True
                    else:
                        logger.error(
                            f"Readwise API connection failed: {response.status}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Readwise connection test failed: {e}")
            return False
