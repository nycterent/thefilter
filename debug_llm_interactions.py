#!/usr/bin/env python3
"""Debug script to capture LLM interactions for one RSS article."""

import asyncio
import os
import json
import logging
from typing import List, Dict, Any

# Setup logging to show all interactions
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_llm_interactions.log')
    ]
)

# Create a custom logger for LLM interactions
llm_logger = logging.getLogger('LLM_DEBUG')
llm_logger.setLevel(logging.INFO)

# Add file handler for LLM interactions only
llm_handler = logging.FileHandler('llm_interactions.log')
llm_formatter = logging.Formatter('%(asctime)s - %(message)s')
llm_handler.setFormatter(llm_formatter)
llm_logger.addHandler(llm_handler)

from src.clients.openrouter import OpenRouterClient
from src.clients.rss import RSSClient
from src.models.settings import Settings


class DebuggingOpenRouterClient(OpenRouterClient):
    """OpenRouter client that logs all interactions for debugging."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.interaction_count = 0
    
    async def _make_request(self, prompt: str, max_tokens: int = 100, temperature: float = 0.3) -> Dict[str, Any]:
        """Override to log all interactions."""
        self.interaction_count += 1
        
        # Log the input
        llm_logger.info(f"\n{'='*80}")
        llm_logger.info(f"LLM INTERACTION #{self.interaction_count}")
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
                llm_logger.info(f"Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                llm_logger.info(f"Total tokens: {usage.get('total_tokens', 'N/A')}")
        else:
            llm_logger.info(f"\nLLM RESPONSE: FAILED")
            llm_logger.info(f"Raw response: {response}")
        
        llm_logger.info(f"{'='*80}\n")
        
        return response


async def debug_single_article():
    """Debug processing of a single article with full LLM interaction logging."""
    
    print("🔍 Starting LLM interaction debugging for one RSS article...")
    print("📝 Logs will be written to 'llm_interactions.log'")
    
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
    print(f"🤖 OpenRouter API key: {openrouter_key[:20]}..." if openrouter_key else "Not set")
    
    settings = Settings()
    
    # Use debugging client
    openrouter_client = DebuggingOpenRouterClient(settings.openrouter_api_key)
    
    # Fetch one RSS article
    rss_client = RSSClient(settings.rss_feeds.split(","))
    articles = await rss_client.get_recent_articles(days=7)
    
    if not articles:
        print("❌ No articles found in RSS feed")
        return
    
    article = articles[0]  # Get first article
    print(f"📰 Processing article: {article['title'][:80]}...")
    
    # Create ContentItem
    from src.models.content import ContentItem
    from datetime import datetime, timezone
    
    item = ContentItem(
        id=f"rss_{hash(article['id'])}",
        title=article["title"],
        content=article.get("summary", article.get("content", "")),
        source=article["source"],
        url=article.get("url"),
        author=article.get("author"),
        source_title=article.get("source_title"),
        tags=article.get("tags", []),
        created_at=datetime.now(timezone.utc),
        metadata={
            "source_url": article.get("source_url"),
            "full_content": article.get("content"),
        },
    )
    
    print(f"📊 Article details:")
    print(f"  Title: {item.title}")
    print(f"  Source: {item.source_title}")
    print(f"  URL: {item.url}")
    print(f"  Content length: {len(item.content)} chars")
    print(f"  Tags: {item.tags}")
    
    print(f"\n🎭 Starting editorial workflow...")
    
    # Step 1: Fetch article content
    print(f"📄 Step 1: Fetching article content...")
    article_content = ""
    if item.url:
        article_content = await openrouter_client.fetch_article_content(str(item.url))
        print(f"   Fetched {len(article_content)} characters")
    else:
        print(f"   No URL available, skipping content fetch")
    
    # Step 2: Generate initial commentary  
    print(f"✍️  Step 2: Generating initial commentary...")
    commentary = await openrouter_client.generate_commentary(
        article_content if article_content else "Article content not available",
        item.content,  # User highlights
        item.title,
    )
    print(f"   Generated commentary: {len(commentary)} characters")
    
    # Step 3: Editorial review
    print(f"👨‍💼 Step 3: Editorial review...")
    review = await openrouter_client.editorial_roast(commentary, "article")
    print(f"   Editor score: {review['score']}/10")
    print(f"   Approved: {review['approved']}")
    print(f"   Feedback: {review['feedback'][:200]}...")
    
    # Step 4: Revision if needed
    if not review['approved']:
        print(f"🔄 Step 4: Revising based on editor feedback...")
        revised_commentary = await openrouter_client.revise_content(
            commentary,
            review['feedback'],
            article_content,
            item.content
        )
        print(f"   Revised commentary: {len(revised_commentary)} characters")
        
        # Second review
        print(f"👨‍💼 Step 5: Second editorial review...")
        final_review = await openrouter_client.editorial_roast(revised_commentary, "article")
        print(f"   Final editor score: {final_review['score']}/10")
        print(f"   Final approved: {final_review['approved']}")
    else:
        revised_commentary = commentary
        print(f"✅ Article approved on first review, no revision needed")
    
    print(f"\n📋 FINAL RESULTS:")
    print(f"=" * 60)
    print(f"Original content ({len(item.content)} chars):")
    print(f"{item.content}")
    print(f"\n" + "=" * 60)
    print(f"Final commentary ({len(revised_commentary)} chars):")
    print(f"{revised_commentary}")
    print(f"=" * 60)
    
    print(f"\n✅ Debug complete!")
    print(f"📄 Total LLM interactions: {openrouter_client.interaction_count}")
    print(f"📝 Full interaction logs saved to 'llm_interactions.log'")
    print(f"🔍 Debug logs saved to 'debug_llm_interactions.log'")


if __name__ == "__main__":
    asyncio.run(debug_single_article())