#!/usr/bin/env python3
"""
Detailed debug script for newsletter generation with full LLM interaction tracing.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.clients.openrouter import OpenRouterClient
from src.core.newsletter import NewsletterGenerator
from src.models.settings import Settings


# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("debug_detailed.log")],
)

logger = logging.getLogger(__name__)


class DebugOpenRouterClient(OpenRouterClient):
    """Extended OpenRouter client with detailed logging."""

    async def generate_text(
        self, prompt: str, model: str = "anthropic/claude-3.5-sonnet", **kwargs
    ) -> str:
        logger.info("=" * 80)
        logger.info(f"🤖 SENDING TO LLM ({model})")
        logger.info("=" * 80)
        logger.info(f"PROMPT:\n{prompt}")
        logger.info("=" * 80)

        # Call parent method
        response = await super().generate_text(prompt, model, **kwargs)

        logger.info("=" * 80)
        logger.info(f"🎯 RECEIVED FROM LLM ({model})")
        logger.info("=" * 80)
        logger.info(f"RESPONSE:\n{response}")
        logger.info("=" * 80)

        return response


async def debug_single_article():
    """Debug newsletter generation for a single article with full tracing."""

    # Environment should be set externally - don't hardcode secrets

    logger.info("🚀 Starting detailed newsletter generation debug")

    try:
        # Initialize settings
        settings = Settings()
        logger.info(f"Settings loaded: RSS_FEEDS={settings.rss_feeds}")

        # Create debug client
        debug_client = DebugOpenRouterClient(settings.openrouter_api_key)

        # Create newsletter generator with debug client
        generator = NewsletterGenerator(settings)
        generator.openrouter_client = debug_client  # Replace with debug client

        logger.info("📰 Fetching RSS content...")

        # Fetch content from RSS
        logger.info(f"Fetching from RSS feeds...")
        articles = await generator._get_rss_content()
        logger.info(f"Found {len(articles)} articles from RSS")

        if not articles:
            logger.error("No articles found!")
            return

        # Process just the first article for debugging
        article = articles[0]
        logger.info(f"📄 Processing article: {article.title}")
        logger.info(f"Article URL: {article.url}")
        logger.info(f"Article content preview: {article.content[:200]}...")

        # Step 1: Writer phase
        logger.info("\n" + "=" * 100)
        logger.info("🖋️  PHASE 1: WRITER")
        logger.info("=" * 100)

        # Generate initial draft
        initial_draft = await generator._generate_initial_draft([article])

        logger.info(f"\n📝 INITIAL DRAFT GENERATED:")
        logger.info(f"Title: {initial_draft.title}")
        logger.info(f"Content:\n{initial_draft.content}")

        # Step 2: Editor phases
        logger.info("\n" + "=" * 100)
        logger.info("✏️  PHASE 2: EDITORIAL REVISIONS")
        logger.info("=" * 100)

        # First editorial pass
        logger.info("\n--- EDITORIAL PASS 1 ---")
        first_revision = await generator._apply_editorial_feedback(initial_draft, 1)

        logger.info(f"\n📝 FIRST REVISION:")
        logger.info(f"Title: {first_revision.title}")
        logger.info(f"Content:\n{first_revision.content}")

        # Second editorial pass
        logger.info("\n--- EDITORIAL PASS 2 ---")
        second_revision = await generator._apply_editorial_feedback(first_revision, 2)

        logger.info(f"\n📝 SECOND REVISION:")
        logger.info(f"Title: {second_revision.title}")
        logger.info(f"Content:\n{second_revision.content}")

        # Third editorial pass
        logger.info("\n--- EDITORIAL PASS 3 ---")
        final_revision = await generator._apply_editorial_feedback(second_revision, 3)

        logger.info(f"\n📝 FINAL REVISION:")
        logger.info(f"Title: {final_revision.title}")
        logger.info(f"Content:\n{final_revision.content}")

        logger.info("\n" + "=" * 100)
        logger.info("✅ DEBUG COMPLETE - Check debug_detailed.log for full details")
        logger.info("=" * 100)

    except Exception as e:
        logger.error(f"❌ Error during debug: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(debug_single_article())
