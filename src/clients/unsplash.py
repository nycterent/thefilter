"""Unsplash API client for dynamic image fetching."""

import asyncio
import logging
import random
from typing import Dict

import aiohttp

logger = logging.getLogger(__name__)


class UnsplashClient:
    """Client for Unsplash API to fetch relevant images for newsletter content."""

    def __init__(self, api_key: str, settings=None):
        """Initialize Unsplash client.

        Args:
            api_key: Unsplash Access Key
            settings: Settings instance for configuration values
        """
        self.api_key = api_key
        self.base_url = "https://api.unsplash.com"
        self.headers = {
            "Authorization": f"Client-ID {api_key}",
            "Content-Type": "application/json",
        }
        # Timeout configuration
        self.timeout = settings.unsplash_timeout if settings else 10.0

        # Curated fallback images (high quality)
        self.fallback_images = {
            "technology": [
                "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
            ],
            "society": [
                "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1566125882500-87e10f726cdc?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1582213782179-e0d53f98f2ca?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
            ],
            "art": [
                "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1536924940846-227afb31e2a5?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
            ],
            "business": [
                "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "https://images.unsplash.com/photo-1664475111862-c4ba2cc60d60?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
            ],
        }

    async def search_image(self, query: str, category: str = "technology") -> str:
        """Search for an image relevant to the query and category.

        Args:
            query: Search query for the image
            category: Category hint (technology, society, art, business)

        Returns:
            Image URL or fallback URL if API fails
        """
        if not self.api_key:
            logger.debug("No Unsplash API key - using fallback images")
            return self._get_fallback_image(category)

        try:
            # Enhanced query with category context
            search_query = self._enhance_search_query(query, category)

            url = f"{self.base_url}/search/photos"
            params = {
                "query": search_query,
                "per_page": 10,
                "orientation": "landscape",
                "content_filter": "high",  # Family-friendly content
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, params=params, timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])

                        if results:
                            # Pick a random image from the results for variety
                            chosen_image = random.choice(results)
                            image_url = self._format_image_url(chosen_image)
                            logger.debug(
                                f"Found Unsplash image for '{query}': {image_url}"
                            )
                            return image_url
                        else:
                            logger.debug(
                                f"No Unsplash results for '{query}' - using fallback"
                            )
                            return self._get_fallback_image(category)
                    else:
                        logger.warning(f"Unsplash API error: {response.status}")
                        return self._get_fallback_image(category)

        except asyncio.TimeoutError:
            logger.warning("Unsplash API timeout - using fallback")
            return self._get_fallback_image(category)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Network error with Unsplash API: {e} - using fallback")
            return self._get_fallback_image(category)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(
                f"Data parsing error with Unsplash API: {e} - using fallback"
            )
            return self._get_fallback_image(category)
        except Exception as e:
            logger.warning(f"Unexpected Unsplash API error: {e} - using fallback")
            return self._get_fallback_image(category)

    def _enhance_search_query(self, query: str, category: str) -> str:
        """Enhance search query with category-specific terms."""
        # Category-specific enhancement keywords
        enhancements = {
            "technology": ["technology", "digital", "innovation", "modern"],
            "society": ["people", "community", "social", "human"],
            "art": ["art", "creative", "artistic", "design"],
            "business": ["business", "professional", "corporate", "work"],
        }

        # Limit query length and add relevant keywords
        base_query = query[:30]  # Keep reasonable length
        category_terms = enhancements.get(category, [])

        if category_terms:
            # Add one relevant category term
            enhanced_query = f"{base_query} {category_terms[0]}"
        else:
            enhanced_query = base_query

        return enhanced_query

    def _format_image_url(self, image_data: Dict) -> str:
        """Format Unsplash image URL with appropriate parameters."""
        # Use the 'regular' size and add newsletter-optimized parameters
        base_url = image_data["urls"]["regular"]

        # Add parameters for newsletter optimization
        params = "?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80"

        return f"{base_url}{params}"

    def _get_fallback_image(self, category: str) -> str:
        """Get a fallback image for the category."""
        category_images = self.fallback_images.get(
            category, self.fallback_images["technology"]
        )
        return random.choice(category_images)

    async def get_category_image(self, category: str, topic_hint: str = "") -> str:
        """Get an image appropriate for a newsletter category.

        Args:
            category: The newsletter category (technology, society, art, business)
            topic_hint: Optional topic hint to make image more relevant

        Returns:
            Image URL
        """
        # Category-specific search terms
        search_terms = {
            "technology": ["technology", "innovation", "digital", "computer", "ai"],
            "society": ["community", "people", "social", "culture", "society"],
            "art": ["art", "creative", "painting", "design", "artistic"],
            "business": ["business", "office", "professional", "finance", "corporate"],
        }

        # Use topic hint or fallback to category terms
        if topic_hint:
            query = topic_hint[:20]  # Limit hint length
        else:
            terms = search_terms.get(category, search_terms["technology"])
            query = random.choice(terms)

        return await self.search_image(query, category)

    async def test_connection(self) -> bool:
        """Test the Unsplash API connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.api_key:
            logger.warning("No Unsplash API key provided")
            return False

        try:
            url = f"{self.base_url}/search/photos"
            params = {"query": "test", "per_page": 1}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.headers, params=params, timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        logger.info("Unsplash API connection successful")
                        return True
                    else:
                        logger.error(
                            f"Unsplash API connection failed: {response.status}"
                        )
                        return False

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error testing Unsplash connection: {e}")
            return False
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Response parsing error testing Unsplash connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing Unsplash connection: {e}")
            return False
