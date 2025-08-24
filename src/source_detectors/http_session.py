"""Shared HTTP session management with connection pooling."""

import asyncio
import logging
from typing import Any, Optional

import aiohttp

from .config import get_config

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """Manages shared aiohttp session with proper connection pooling."""

    _instance: Optional["HTTPSessionManager"] = None
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "HTTPSessionManager":
        """Singleton pattern to ensure single session instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_session(self) -> aiohttp.ClientSession:
        """
        Get or create the shared HTTP session with proper connection pooling.

        Returns:
            Configured aiohttp.ClientSession instance
        """
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    await self._create_session()

        assert self._session is not None
        return self._session

    async def _create_session(self) -> None:
        """Create a new HTTP session with optimized connection pooling."""
        # Connection pool configuration
        connector = aiohttp.TCPConnector(
            limit=get_config("http.connection_pool.total_limit", 100),
            limit_per_host=get_config("http.connection_pool.per_host_limit", 30),
            ttl_dns_cache=get_config("http.connection_pool.dns_cache_ttl", 300),
            use_dns_cache=True,
            enable_cleanup_closed=True,
            force_close=False,
            keepalive_timeout=get_config("http.connection_pool.keepalive_timeout", 30),
        )

        # Session timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=get_config("http.timeout.total", 30),
            connect=get_config("http.timeout.connect", 10),
            sock_read=get_config("http.timeout.read", 30),
        )

        # Default headers for all requests
        headers = {
            "User-Agent": get_config(
                "http.user_agent",
                "newsletter-bot/1.0.0 (source-detection)",
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "DNT": "1",
        }

        # Create session with configuration
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
            raise_for_status=False,  # Handle status codes manually
            auto_decompress=True,
            trust_env=True,  # Respect environment proxy settings
        )

        logger.info(
            f"HTTP session created with connection pool limits: "
            f"total={connector.limit}, per_host={connector.limit_per_host}"
        )

    async def close(self) -> None:
        """Close the HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Wait for connections to close
            await asyncio.sleep(0.1)
            self._session = None
            logger.info("HTTP session closed")

    async def __aenter__(self) -> aiohttp.ClientSession:
        """Async context manager entry."""
        return await self.get_session()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - do not close session automatically."""
        # Session stays alive for reuse
        pass


# Global session manager instance
_session_manager: Optional[HTTPSessionManager] = None


async def get_http_session() -> aiohttp.ClientSession:
    """
    Get the global HTTP session instance.

    Returns:
        Shared aiohttp.ClientSession with connection pooling
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = HTTPSessionManager()
    return await _session_manager.get_session()


async def close_http_session() -> None:
    """Close the global HTTP session."""
    global _session_manager
    if _session_manager:
        await _session_manager.close()
        _session_manager = None


# Graceful shutdown handler
async def cleanup_http_resources() -> None:
    """Clean up HTTP resources on application shutdown."""
    await close_http_session()
    logger.info("HTTP resources cleaned up")
