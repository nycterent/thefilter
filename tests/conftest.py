import pytest
from unittest.mock import AsyncMock
import asyncio


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from src.models.settings import Settings

    return Settings(
        readwise_api_key="test_key",
        glasp_api_key="test_key",
        feedbin_username="test_user",
        feedbin_password="test_pass",
        buttondown_api_key="test_key",
        openrouter_api_key="test_key",
        unsplash_api_key="test_key",
    )
