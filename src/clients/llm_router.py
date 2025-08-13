"""LLM Router with fallback functionality for newsletter generation."""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

from src.clients.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class LLMRouter:
    """Router for LLM requests with automatic fallback on failures."""

    def __init__(
        self,
        primary_client: OpenRouterClient,
        fallback_client: Optional[OpenRouterClient] = None,
    ):
        """Initialize LLM router.

        Args:
            primary_client: Primary OpenRouter client (Venice)
            fallback_client: Fallback client (OSS model or local)
        """
        self.primary_client = primary_client
        self.fallback_client = fallback_client
        self.fallback_used = False

    @classmethod
    def from_env(cls) -> "LLMRouter":
        """Create router from environment variables."""
        # Primary client - Venice model
        primary_model = os.getenv(
            "OPENROUTER_MODEL",
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        )
        primary_client = OpenRouterClient(os.getenv("OPENROUTER_API_KEY", ""))
        primary_client.default_model = primary_model

        # Fallback client - OSS model
        fallback_client = None
        fallback_model = os.getenv(
            "FALLBACK_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
        )
        if fallback_model != primary_model:
            fallback_client = OpenRouterClient(os.getenv("OPENROUTER_API_KEY", ""))
            fallback_client.default_model = fallback_model

        return cls(primary_client, fallback_client)

    async def complete(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> Dict[str, Any]:
        """Complete LLM request with automatic fallback.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional arguments for the LLM request

        Returns:
            Response dictionary with 'content' key
        """
        # Try primary client first
        try:
            logger.debug("Attempting request with primary LLM (Venice)")
            response = await self._make_request(self.primary_client, messages, **kwargs)
            if response and self._is_valid_response(response):
                logger.debug("Primary LLM request successful")
                return {"content": response["choices"][0]["message"]["content"]}
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Network error with primary LLM: {e}")
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Data processing error with primary LLM: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error with primary LLM: {e}")

        # Fallback to secondary client if available
        if self.fallback_client:
            try:
                logger.info("Falling back to secondary LLM")
                self.fallback_used = True
                response = await self._make_request(
                    self.fallback_client, messages, **kwargs
                )
                if response and self._is_valid_response(response):
                    logger.info("Fallback LLM request successful")
                    return {"content": response["choices"][0]["message"]["content"]}
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Network error with fallback LLM: {e}")
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Data processing error with fallback LLM: {e}")
            except Exception as e:
                logger.error(f"Unexpected error with fallback LLM: {e}")

        # If all else fails, return empty content
        logger.error("All LLM providers failed")
        return {"content": ""}

    async def _make_request(
        self, client: OpenRouterClient, messages: List[Dict[str, str]], **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Make request to specific client."""
        # Convert messages to prompt format expected by OpenRouterClient
        if len(messages) == 1:
            prompt = messages[0]["content"]
        else:
            # For multi-message conversations, combine them
            prompt = "\n\n".join(
                [f"{msg['role']}: {msg['content']}" for msg in messages]
            )

        max_tokens = kwargs.get("max_tokens", 100)
        temperature = kwargs.get("temperature", 0.3)

        return await client._make_request(prompt, max_tokens, temperature)

    def _is_valid_response(self, response: Dict[str, Any]) -> bool:
        """Check if response is valid and contains content."""
        if not response or "choices" not in response:
            return False

        choices = response["choices"]
        if not choices or len(choices) == 0:
            return False

        content = choices[0].get("message", {}).get("content", "")
        if not content or content.strip() == "":
            return False

        # Check for refusal patterns
        refusal_patterns = [
            "i cannot fulfill your request",
            "i am just an ai model",
            "i can't provide assistance",
            "i cannot create content",
            "it is not within my programming",
            "ethical guidelines",
            "i'm unable to",
            "i cannot help with",
            "i'm not able to",
            "as an ai",
            "i'm an ai",
        ]

        content_lower = content.lower()
        for pattern in refusal_patterns:
            if pattern in content_lower:
                logger.warning(f"LLM refusal detected: {pattern}")
                return False

        return True
