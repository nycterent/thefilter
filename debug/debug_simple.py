#!/usr/bin/env python3
"""
Simple debug script to trace LLM interactions during newsletter generation.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.clients.openrouter import OpenRouterClient
from src.core.newsletter import NewsletterGenerator
from src.models.settings import Settings


# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class DebugOpenRouterClient(OpenRouterClient):
    """Extended OpenRouter client with detailed logging."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.call_count = 0

    async def generate_text(
        self, prompt: str, model: str = "anthropic/claude-3.5-sonnet", **kwargs
    ) -> str:
        self.call_count += 1
        logger.info("=" * 100)
        logger.info(f"🤖 LLM CALL #{self.call_count} - MODEL: {model}")
        logger.info("=" * 100)
        logger.info(f"PROMPT (first 500 chars):\n{prompt[:500]}...")
        logger.info("=" * 100)

        # Call parent method
        response = await super().generate_text(prompt, model, **kwargs)

        logger.info("=" * 100)
        logger.info(f"🎯 LLM RESPONSE #{self.call_count}")
        logger.info("=" * 100)
        logger.info(f"RESPONSE (first 500 chars):\n{response[:500]}...")
        logger.info("=" * 100)

        # Full prompt and response to file
        with open(f"debug_llm_call_{self.call_count}.txt", "w") as f:
            f.write(f"=== LLM CALL #{self.call_count} ===\n")
            f.write(f"MODEL: {model}\n\n")
            f.write(f"=== FULL PROMPT ===\n")
            f.write(prompt)
            f.write(f"\n\n=== FULL RESPONSE ===\n")
            f.write(response)
            f.write("\n")

        logger.info(f"📝 Full details saved to debug_llm_call_{self.call_count}.txt")

        return response


async def main():
    """Main debug function."""

    logger.info("🚀 Starting simple newsletter debug")

    try:
        # Initialize settings
        settings = Settings()

        if not settings.rss_feeds:
            logger.error("No RSS feeds configured!")
            return

        if not settings.openrouter_api_key:
            logger.error("No OpenRouter API key configured!")
            return

        # Create debug client
        debug_client = DebugOpenRouterClient(settings.openrouter_api_key)

        # Create newsletter generator
        generator = NewsletterGenerator(settings)

        # Replace the OpenRouter client with our debug version
        generator.openrouter_client = debug_client

        logger.info("📰 Generating newsletter with debug tracing...")

        # Generate newsletter - this will trigger all LLM calls
        draft = await generator.generate_newsletter(dry_run=True)

        logger.info(f"✅ Newsletter generation complete!")
        logger.info(f"Title: {draft.title}")
        logger.info(f"Content length: {len(draft.content)} characters")
        logger.info(f"Total LLM calls made: {debug_client.call_count}")

        # Save final newsletter
        with open("debug_final_newsletter.md", "w") as f:
            f.write(f"# {draft.title}\n\n")
            f.write(draft.content)

        logger.info("📝 Final newsletter saved to debug_final_newsletter.md")
        logger.info("📁 Individual LLM calls saved as debug_llm_call_*.txt files")

    except Exception as e:
        logger.error(f"❌ Error during debug: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
