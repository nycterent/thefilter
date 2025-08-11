#!/usr/bin/env python3
"""Debug script to trace the editorial workflow dataflow."""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, 'src')

from src.clients.openrouter import OpenRouterClient
from src.models.content import ContentItem
from src.models.settings import Settings

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def debug_editorial_workflow():
    """Debug the complete editorial workflow with one article."""
    
    print("🔍 DEBUGGING EDITORIAL WORKFLOW")
    print("=" * 50)
    
    # Load settings
    settings = Settings()
    
    if not settings.openrouter_api_key:
        print("❌ No OpenRouter API key found. Please set OPENROUTER_API_KEY")
        return
    
    # Initialize OpenRouter client
    openrouter = OpenRouterClient(settings.openrouter_api_key)
    
    # Create a sample RSS article with user highlights
    sample_article = ContentItem(
        id="debug_1",
        title="The Future of AI Safety: New Research Breakthrough",
        content="""🤖 This is fascinating - researchers at Anthropic have developed a new approach to AI alignment that actually works in practice. 

• The key insight: instead of trying to specify what we want, they're teaching AI systems to ask better questions about human values
• **Game changer**: This could solve the value learning problem that's been plaguing AI safety for years
• My take: This feels like the missing piece we've been waiting for. The implications for AGI development are massive.

The paper shows concrete results with GPT-4 class models becoming much better at understanding nuanced human preferences.""",
        source="rss",
        url="https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback",
        author="Claude Shannon", 
        source_title="Anthropic Research",
        tags=["ai-safety", "machine-learning", "alignment"],
        created_at=datetime.now(timezone.utc),
        metadata={"feed_url": "https://example.com/feed.xml"}
    )
    
    print(f"📄 SAMPLE ARTICLE:")
    print(f"   Title: {sample_article.title}")
    print(f"   Source: {sample_article.source}")
    print(f"   URL: {sample_article.url}")
    print(f"   Content length: {len(sample_article.content)} chars")
    print()
    
    # Step 1: Detect if this is user-curated content
    print("🔍 STEP 1: Detecting User Commentary")
    print("-" * 30)
    
    has_user_commentary = await openrouter.detect_user_commentary(
        sample_article.content, 
        sample_article.title
    )
    print(f"   User commentary detected: {has_user_commentary}")
    print()
    
    # Step 2: Fetch article content
    print("🌐 STEP 2: Fetching Original Article Content")
    print("-" * 30)
    
    article_content = await openrouter.fetch_article_content(sample_article.url)
    print(f"   Fetched content length: {len(article_content)} chars")
    if article_content:
        print(f"   Preview: {article_content[:200]}...")
    else:
        print("   ⚠️ Failed to fetch article content")
    print()
    
    # Step 3: Generate initial commentary
    print("✍️ STEP 3: Writer Agent - Initial Commentary Generation")
    print("-" * 30)
    
    initial_commentary = await openrouter.generate_commentary(
        article_content if article_content else "Fallback: Using user highlights only",
        sample_article.content,
        sample_article.title
    )
    
    print(f"   Generated commentary ({len(initial_commentary)} chars):")
    print(f"   {initial_commentary}")
    print()
    
    # Step 4: Editorial review loop (3 revisions max)
    print("🎭 STEP 4: Editorial Review Loop")
    print("-" * 30)
    
    current_commentary = initial_commentary
    revision_count = 0
    max_revisions = 3
    editorial_scores = []
    
    while revision_count < max_revisions:
        print(f"\n📝 EDITORIAL REVIEW #{revision_count + 1}")
        print("." * 25)
        
        # Get editorial feedback
        review = await openrouter.editorial_roast(current_commentary, "article")
        editorial_scores.append(review["score"])
        
        print(f"   Editor Score: {review['score']}/10")
        print(f"   Approved: {review['approved']}")
        print(f"   Feedback: {review['feedback'][:150]}...")
        
        if review["approved"]:
            print(f"   ✅ Article APPROVED after {revision_count + 1} review(s)")
            break
            
        if revision_count == max_revisions - 1:
            print(f"   ⏰ Maximum revisions reached")
            break
            
        # Revise based on feedback
        print(f"   🔄 Revision {revision_count + 1} in progress...")
        
        revised_commentary = await openrouter.revise_content(
            current_commentary,
            review["feedback"],
            article_content,
            sample_article.content
        )
        
        print(f"   Revised commentary ({len(revised_commentary)} chars):")
        print(f"   {revised_commentary[:150]}...")
        
        current_commentary = revised_commentary
        revision_count += 1
    
    # Final results
    print("\n📊 FINAL RESULTS")
    print("=" * 30)
    print(f"   Total revisions: {revision_count}")
    print(f"   Editorial scores: {editorial_scores}")
    print(f"   Average score: {sum(editorial_scores)/len(editorial_scores):.1f}/10")
    print(f"   Final approved: {'Yes' if editorial_scores and editorial_scores[-1] >= 7 else 'No'}")
    print()
    
    print("📝 FINAL COMMENTARY:")
    print("-" * 20)
    print(current_commentary)
    print()
    
    # Show data flow summary
    print("🔄 DATA FLOW SUMMARY")
    print("=" * 30)
    print("1. RSS Content → User Commentary Detection")
    print("2. URL → Article Content Fetching")  
    print("3. Article + User Highlights → Writer Agent → Initial Commentary")
    print("4. Commentary → Editor Agent → Review + Score + Feedback")
    print("5. If Not Approved → Writer Agent → Revision (repeat up to 3x)")
    print("6. Final Commentary → Newsletter Integration")
    
if __name__ == "__main__":
    asyncio.run(debug_editorial_workflow())