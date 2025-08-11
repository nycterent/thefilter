#!/usr/bin/env python3
"""Debug script using Llama 3.2 3B with combined writer+editor prompt."""

import asyncio
import os
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("debug_llama_combined.log")],
)

llm_logger = logging.getLogger("LLM_DEBUG")
llm_logger.setLevel(logging.INFO)

llm_handler = logging.FileHandler("llama_combined_interactions.log")
llm_formatter = logging.Formatter("%(asctime)s - %(message)s")
llm_handler.setFormatter(llm_formatter)
llm_logger.addHandler(llm_handler)

from src.clients.openrouter import OpenRouterClient
from src.clients.rss import RSSClient
from src.models.settings import Settings


class LlamaCombinedClient(OpenRouterClient):
    """OpenRouter client using Llama 3.2 3B with combined prompt."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        # Use the working free model
        self.default_model = "meta-llama/llama-3.2-3b-instruct:free"
        self.interaction_count = 0

    async def _make_request(
        self, prompt: str, max_tokens: int = 100, temperature: float = 0.3
    ) -> Dict[str, Any]:
        """Override to log all interactions."""
        self.interaction_count += 1

        # Log the input
        llm_logger.info(f"\n{'='*80}")
        llm_logger.info(f"LLAMA 3.2 INTERACTION #{self.interaction_count}")
        llm_logger.info(f"{'='*80}")
        llm_logger.info(f"MODEL: {self.default_model}")
        llm_logger.info(f"MAX_TOKENS: {max_tokens}")
        llm_logger.info(f"TEMPERATURE: {temperature}")
        llm_logger.info(f"\nINPUT PROMPT:\n{'-'*40}")
        llm_logger.info(prompt)
        llm_logger.info(f"{'-'*40}")

        # Make the actual request
        response = await super()._make_request(prompt, max_tokens, temperature)

        # Log the response
        if response and "choices" in response:
            content = response["choices"][0]["message"]["content"]
            llm_logger.info(f"\nLLM RESPONSE:\n{'-'*40}")
            llm_logger.info(content)
            llm_logger.info(f"{'-'*40}")

            if "usage" in response:
                usage = response["usage"]
                llm_logger.info(f"\nTOKEN USAGE:")
                llm_logger.info(f"Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                llm_logger.info(
                    f"Completion tokens: {usage.get('completion_tokens', 'N/A')}"
                )
                llm_logger.info(f"Total tokens: {usage.get('total_tokens', 'N/A')}")
        else:
            llm_logger.info(f"\nLLM RESPONSE: FAILED")
            llm_logger.info(f"Raw response: {response}")

        llm_logger.info(f"{'='*80}\n")

        return response

    async def combined_writer_editor_workflow(
        self, article_content: str, user_highlights: str, article_title: str = ""
    ) -> str:
        """Use your combined writer+editor prompt with Llama 3.2."""
        if not self.api_key:
            return user_highlights

        try:
            # First, generate an initial draft
            initial_prompt = f"""You are a skilled newsletter writer. Write a 2-3 paragraph commentary about this article.

ARTICLE: {article_title}
CONTENT: {article_content[:2000]}
USER HIGHLIGHTS: {user_highlights}

Focus on inequality and societal collapse themes from the article. Keep under 300 words and conversational."""

            initial_response = await self._make_request(
                initial_prompt, max_tokens=200, temperature=0.7
            )
            if not initial_response or "choices" not in initial_response:
                return user_highlights

            initial_draft = initial_response["choices"][0]["message"]["content"].strip()

            # Use your combined editor+writer prompt
            combined_prompt = f"""You are doing a two-step editorial workflow:

STEP 1 - EDITOR ROLE:
Review this draft and provide brutal, specific feedback. Rate 1-10 (7+ = good).

STEP 2 - WRITER ROLE: 
Rewrite the draft using the editor feedback.

ARTICLE CONTEXT: {article_content[:1500]}

USER HIGHLIGHTS: {user_highlights}

ORIGINAL DRAFT: {initial_draft}

Do both steps - first critique, then rewrite. Format:

EDITOR CRITIQUE:
SCORE: X/10
FEEDBACK: [specific issues and fixes needed]
APPROVED: YES/NO

REVISED DRAFT:
[final improved commentary under 300 words]"""

            response = await self._make_request(
                combined_prompt, max_tokens=400, temperature=0.6
            )
            if response and "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"].strip()
            else:
                return initial_draft

        except Exception as e:
            llm_logger.error(f"Error in combined workflow: {e}")
            return user_highlights


async def debug_llama_combined():
    """Debug the combined prompt with Llama 3.2 3B."""

    print("🦙 Testing Llama 3.2 3B with combined writer+editor prompt...")
    print("📝 Logs will be written to 'llama_combined_interactions.log'")

    # Check required environment variables
    rss_feeds = os.getenv("RSS_FEEDS")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not rss_feeds:
        print("❌ RSS_FEEDS environment variable not set")
        return

    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY environment variable not set")
        return

    print(f"🔗 Using RSS feed: {rss_feeds}")

    settings = Settings()

    # Use Llama client
    openrouter_client = LlamaCombinedClient(settings.openrouter_api_key)

    # Fetch one RSS article
    rss_client = RSSClient(settings.rss_feeds.split(","))
    articles = await rss_client.get_recent_articles(days=7)

    if not articles:
        print("❌ No articles found in RSS feed")
        return

    article = articles[0]  # Get first article
    print(f"📰 Processing article: {article['title'][:80]}...")

    # Get full article content
    article_content = ""
    if article.get("url"):
        print(f"📄 Fetching full article content...")
        article_content = await openrouter_client.fetch_article_content(article["url"])
        print(f"   Fetched {len(article_content)} characters")
    else:
        article_content = article.get("summary", article.get("content", ""))

    user_highlights = article.get("summary", article.get("content", ""))

    print(f"\n🎭 Running Llama 3.2 combined workflow...")

    # Run the combined workflow
    final_commentary = await openrouter_client.combined_writer_editor_workflow(
        article_content, user_highlights, article["title"]
    )

    print(f"\n📋 RESULTS:")
    print(f"=" * 60)
    print(f"Original RSS content ({len(user_highlights)} chars):")
    print(f"{user_highlights}")
    print(f"\n" + "=" * 60)
    print(f"Llama 3.2 combined output ({len(final_commentary)} chars):")
    print(f"{final_commentary}")
    print(f"=" * 60)

    print(f"\n✅ Debug complete!")
    print(f"📄 Total LLM interactions: {openrouter_client.interaction_count}")
    print(f"📝 Full interaction logs saved to 'llama_combined_interactions.log'")
    print(f"🔍 Debug logs saved to 'debug_llama_combined.log'")


if __name__ == "__main__":
    asyncio.run(debug_llama_combined())
