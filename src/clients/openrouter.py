"""OpenRouter API client for AI processing and content enhancement."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API to process content with free models."""

    def __init__(self, api_key: str):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thefilter.buttondown.email",  # Required by OpenRouter
            "X-Title": "The Filter Newsletter",  # Optional title
        }
        # Use free models only
        self.default_model = "google/gemma-2-9b-it:free"  # Free Gemma model

    async def enhance_content_summary(
        self, title: str, content: str, max_length: int = 160
    ) -> str:
        """Enhance content summary using AI.

        Args:
            title: Content title
            content: Original content
            max_length: Maximum summary length

        Returns:
            Enhanced summary or original content if API fails
        """
        if not self.api_key:
            logger.warning("No OpenRouter API key - skipping content enhancement")
            return content[:max_length]

        try:
            prompt = f"""Create an engaging, informative summary for a newsletter. Focus on WHY this matters to readers and what's interesting/surprising. Keep it under {max_length} characters and avoid starting with URLs or social links.

Title: {title}
Content: {content[:600]}

Write a compelling summary that hooks the reader:"""

            response = await self._make_request(prompt, max_tokens=50)
            if response and "choices" in response and len(response["choices"]) > 0:
                summary = response["choices"][0]["message"]["content"].strip()
                # Ensure we don't exceed max_length
                if len(summary) > max_length:
                    summary = summary[:max_length-3] + "..."
                return summary
            else:
                logger.warning("OpenRouter returned no content")
                return content[:max_length]

        except Exception as e:
            logger.error(f"Error enhancing content with OpenRouter: {e}")
            return content[:max_length]

    async def categorize_content(self, title: str, content: str, tags: List[str] = None) -> str:
        """Categorize content using AI.

        Args:
            title: Content title
            content: Content text
            tags: Optional tags

        Returns:
            Category: technology, society, art, or business
        """
        if not self.api_key:
            logger.warning("No OpenRouter API key - falling back to keyword categorization")
            return self._fallback_categorize(title, content, tags)

        try:
            tags_text = f"Tags: {', '.join(tags)}" if tags else ""
            prompt = f"""Categorize this content into exactly one category: technology, society, art, or business.

Title: {title}
Content: {content[:500]}
{tags_text}

Choose the most appropriate category. Respond with only the category name."""

            response = await self._make_request(prompt, max_tokens=10)
            if response and "choices" in response and len(response["choices"]) > 0:
                category = response["choices"][0]["message"]["content"].strip().lower()
                # Validate category
                valid_categories = ["technology", "society", "art", "business"]
                if category in valid_categories:
                    return category
                else:
                    logger.warning(f"AI returned invalid category: {category}")
                    return self._fallback_categorize(title, content, tags)
            else:
                return self._fallback_categorize(title, content, tags)

        except Exception as e:
            logger.error(f"Error categorizing content with OpenRouter: {e}")
            return self._fallback_categorize(title, content, tags)

    def _fallback_categorize(self, title: str, content: str, tags: List[str] = None) -> str:
        """Fallback keyword-based categorization."""
        text = f"{title} {content}".lower()
        if tags:
            text += " " + " ".join(tags).lower()

        # Technology keywords
        tech_keywords = [
            "ai", "artificial intelligence", "machine learning", "software", "app",
            "algorithm", "programming", "code", "tech", "digital", "crypto", "blockchain",
            "computer", "internet", "web", "data", "api", "cloud", "cybersecurity"
        ]

        # Art keywords
        art_keywords = [
            "art", "artist", "painting", "sculpture", "museum", "gallery", "design",
            "creative", "photography", "music", "film", "movie", "book", "literature",
            "culture", "aesthetic", "exhibition", "performance"
        ]

        # Business keywords
        business_keywords = [
            "business", "company", "startup", "entrepreneur", "market", "finance",
            "investment", "economy", "revenue", "profit", "venture", "funding",
            "acquisition", "merger", "stock", "trade"
        ]

        # Count keyword matches
        tech_score = sum(1 for keyword in tech_keywords if keyword in text)
        art_score = sum(1 for keyword in art_keywords if keyword in text)
        business_score = sum(1 for keyword in business_keywords if keyword in text)

        # Return category with highest score
        scores = {
            "technology": tech_score,
            "art": art_score,
            "business": business_score,
            "society": 0  # Default fallback
        }

        return max(scores, key=scores.get) or "society"

    async def _make_request(
        self, prompt: str, max_tokens: int = 100, temperature: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        """Make a request to OpenRouter API.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            API response or None if failed
        """
        payload = {
            "model": self.default_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"OpenRouter API error: {response.status} - {error_text}"
                        )
                        return None

        except asyncio.TimeoutError:
            logger.error("OpenRouter API request timed out")
            return None
        except Exception as e:
            logger.error(f"OpenRouter API request failed: {e}")
            return None

    async def test_connection(self) -> bool:
        """Test the OpenRouter API connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = await self._make_request("Hello, world!", max_tokens=5)
            if response and "choices" in response:
                logger.info("OpenRouter API connection successful")
                return True
            else:
                logger.error("OpenRouter API connection failed - no valid response")
                return False

        except Exception as e:
            logger.error(f"OpenRouter connection test failed: {e}")
            return False