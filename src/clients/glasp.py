"""Glasp API client for retrieving highlights and articles."""

import asyncio
import logging
from typing import Any, Dict, List

import aiohttp

logger = logging.getLogger(__name__)


class GlaspClient:
    """Client for Glasp API to fetch highlights and articles."""

    def __init__(self, api_key: str, settings=None):
        self.api_key = api_key
        self.base_url = "https://api.glasp.co/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # Timeout configuration - use same timeout as Readwise for similar API behavior
        self.timeout = settings.readwise_timeout if settings else 15.0

    async def get_highlights(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent highlights from Glasp."""
        if not self.api_key:
            logger.error("No Glasp API key provided.")
            return []
        try:
            url = f"{self.base_url}/highlights"
            params = {"days": days}
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    url, headers=self.headers, params=params
                ) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        # Check if this is a Cloudflare blocking page
                        if (
                            "cloudflare" in error_detail.lower()
                            and response.status == 403
                        ):
                            logger.warning(
                                f"Glasp API blocked by Cloudflare (status {response.status}). "
                                "This may be due to automated access restrictions."
                            )
                        else:
                            # For other errors, show limited detail
                            short_detail = (
                                error_detail[:200] + "..."
                                if len(error_detail) > 200
                                else error_detail
                            )
                            logger.error(
                                f"Glasp API error: {response.status} - {short_detail}"
                            )
                        return []
                    data = await response.json()
                    return data.get("results", [])
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error fetching Glasp highlights: {e}")
            return []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error fetching Glasp highlights: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Glasp highlights: {e}")
            return []
