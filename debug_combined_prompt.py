#!/usr/bin/env python3
"""Debug script using combined writer + editor prompt for one RSS article."""

import asyncio
import os
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_combined_prompt.log')
    ]
)

llm_logger = logging.getLogger('LLM_DEBUG')
llm_logger.setLevel(logging.INFO)

llm_handler = logging.FileHandler('combined_prompt_interactions.log')
llm_formatter = logging.Formatter('%(asctime)s - %(message)s')
llm_handler.setFormatter(llm_formatter)
llm_logger.addHandler(llm_handler)

from src.clients.openrouter import OpenRouterClient
from src.clients.rss import RSSClient
from src.models.settings import Settings


class CombinedPromptClient(OpenRouterClient):
    """OpenRouter client that uses combined writer+editor prompt."""
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.interaction_count = 0
    
    async def _make_request(self, prompt: str, max_tokens: int = 100, temperature: float = 0.3) -> Dict[str, Any]:
        """Override to log all interactions."""
        self.interaction_count += 1
        
        # Log the input
        llm_logger.info(f"\n{'='*80}")
        llm_logger.info(f"COMBINED PROMPT INTERACTION #{self.interaction_count}")
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
    
    async def combined_writer_editor_workflow(self, article_content: str, user_highlights: str, article_title: str = "") -> str:
        """Use combined writer+editor prompt to process article."""
        if not self.api_key:
            return user_highlights  # Fallback to highlights
        
        try:
            # First, generate an initial draft
            initial_prompt = f"""You are a skilled newsletter writer creating engaging, thought-provoking content for informed readers.

ARTICLE TITLE: {article_title}

ARTICLE CONTENT:
{article_content[:3000]}

USER'S PERSPECTIVE/HIGHLIGHTS:
{user_highlights}

TASK: Write a 2-3 paragraph commentary incorporating the user's insights. Focus on the article content about societal collapse and inequality. Keep under 300 words.

Write engaging commentary:"""
            
            initial_response = await self._make_request(initial_prompt, max_tokens=200, temperature=0.7)
            if not initial_response or "choices" not in initial_response:
                return user_highlights
            
            initial_draft = initial_response["choices"][0]["message"]["content"].strip()
            
            # Now use your combined writer+editor prompt
            combined_prompt = f"""You are simulating a **two-step editorial workflow** in a single pass.

---

### STEP 1 — EDITOR ROLE
You are a **seasoned, uncompromising newsletter editor** using newsroom journalism standards.

**TASK:**
- Critique the given draft against the article context and user highlights.
- Be brutally honest, specific, and actionable.
- Identify:
  - Off-topic content
  - Missing journalism techniques
  - Unclear or weak arguments
  - Missed opportunities to use the user's perspective
- Provide example rewrites for weak sections.
- Rate quality **1–10** (7+ = publishable).
- Clearly state **APPROVED: YES/NO**.

**OUTPUT FORMAT:**
```
SCORE: X/10
FEEDBACK:
- [Bullet point 1: actionable fix]
- [Bullet point 2: actionable fix]
- [Bullet point 3: example rewrite]
APPROVED: YES/NO
```

---

### STEP 2 — WRITER ROLE
Now switch hats — you are a **skilled newsletter writer** revising the draft based on the FEEDBACK from STEP 1.

**TASK:**
- Implement **all** actionable fixes from the editor's feedback.
- Keep final text **under 300 words**.
- Structure:
  1. **Opening**: Hook or provocative question tied to article + user highlights
  2. **Body**: Expand the user's perspective with storytelling, historical context, and unique analysis
  3. **Closing**: Reflective or provocative question
- Maintain a **conversational but informed** tone.
- Stay on-topic — reference only the article content and user highlights.

**OUTPUT FORMAT:**
```
[FINAL REVISED COMMENTARY]
```

---

## INPUTS
ARTICLE CONTEXT:  
{article_content[:2000]}

USER HIGHLIGHTS:  
{user_highlights}

ORIGINAL DRAFT:  
{initial_draft}

---

## NOTES
- If the draft ignores the article or user highlights, call it out directly in feedback.
- The editor role should **not** rewrite the article itself — only give critique.
- The writer role should **only** output the final polished commentary."""
            
            response = await self._make_request(combined_prompt, max_tokens=400, temperature=0.6)
            if response and "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"].strip()
            else:
                return initial_draft  # Fallback to initial draft
                
        except Exception as e:
            llm_logger.error(f"Error in combined workflow: {e}")
            return user_highlights  # Fallback


async def debug_combined_prompt():
    """Debug the combined writer+editor prompt approach."""
    
    print("🔍 Starting combined writer+editor prompt debugging...")
    print("📝 Logs will be written to 'combined_prompt_interactions.log'")
    
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
    
    # Use combined prompt client
    openrouter_client = CombinedPromptClient(settings.openrouter_api_key)
    
    # Fetch one RSS article
    rss_client = RSSClient(settings.rss_feeds.split(","))
    articles = await rss_client.get_recent_articles(days=7)
    
    if not articles:
        print("❌ No articles found in RSS feed")
        return
    
    article = articles[0]  # Get first article
    print(f"📰 Processing article: {article['title'][:80]}...")
    
    print(f"📊 Article details:")
    print(f"  Title: {article['title']}")
    print(f"  Source: {article.get('source_title', 'Unknown')}")
    print(f"  URL: {article.get('url', 'No URL')}")
    print(f"  Content length: {len(article.get('summary', article.get('content', '')))} chars")
    
    # Get full article content
    article_content = ""
    if article.get('url'):
        print(f"📄 Fetching full article content...")
        article_content = await openrouter_client.fetch_article_content(article['url'])
        print(f"   Fetched {len(article_content)} characters")
    else:
        article_content = article.get('summary', article.get('content', ''))
        print(f"   Using RSS content: {len(article_content)} characters")
    
    user_highlights = article.get('summary', article.get('content', ''))
    
    print(f"\n🎭 Running combined writer+editor workflow...")
    
    # Run the combined workflow
    final_commentary = await openrouter_client.combined_writer_editor_workflow(
        article_content,
        user_highlights,
        article['title']
    )
    
    print(f"\n📋 RESULTS:")
    print(f"=" * 60)
    print(f"Original RSS content ({len(user_highlights)} chars):")
    print(f"{user_highlights}")
    print(f"\n" + "=" * 60)
    print(f"Combined workflow output ({len(final_commentary)} chars):")
    print(f"{final_commentary}")
    print(f"=" * 60)
    
    print(f"\n✅ Debug complete!")
    print(f"📄 Total LLM interactions: {openrouter_client.interaction_count}")
    print(f"📝 Full interaction logs saved to 'combined_prompt_interactions.log'")
    print(f"🔍 Debug logs saved to 'debug_combined_prompt.log'")


if __name__ == "__main__":
    asyncio.run(debug_combined_prompt())