#!/usr/bin/env python3
"""
Test script to demonstrate the multi-LLM editorial workflow.
This shows how the writer and editor agents collaborate.
"""

import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

# Set up logging to see the editorial workflow in action
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_editorial_workflow():
    """Demonstrate the multi-LLM editorial workflow with mock data."""

    print("🎭 Multi-LLM Editorial Workflow Demonstration")
    print("=" * 50)

    # Mock OpenRouter client with realistic responses
    class MockOpenRouterClient:
        def __init__(self):
            self.request_count = 0

        async def fetch_article_content(self, url):
            """Mock article content fetching."""
            return """
            AI systems are becoming increasingly sophisticated, with new models showing remarkable 
            capabilities in reasoning, coding, and creative tasks. However, questions remain about 
            the long-term implications of these developments for society, employment, and human agency.
            The rapid pace of advancement has caught many experts by surprise, leading to calls for 
            more thoughtful governance and safety measures.
            """

        async def generate_commentary(self, article_content, user_highlights, title):
            """Mock commentary generation by writer agent."""
            self.request_count += 1
            if self.request_count == 1:
                # First attempt - deliberately mediocre
                return """
                This article discusses AI developments. AI is getting better at many tasks. 
                There are some concerns about the future impact. Experts are surprised by 
                the progress. We should think about governance.
                """
            else:
                # Revised version - much better
                return """
                The relentless march of AI capabilities isn't just a technical story—it's a 
                societal inflection point that's unfolding faster than our institutions can adapt. 
                What's particularly striking is how these advances have blindsided even seasoned 
                researchers, suggesting we may be in uncharted territory where traditional forecasting 
                methods fall short. The call for governance isn't just precautionary; it's recognition 
                that we're building systems whose emergent behaviors we don't fully understand.
                """

        async def editorial_roast(self, content, content_type="article"):
            """Mock editorial review with harsh but fair feedback."""
            if "This article discusses" in content:
                # Harsh feedback for mediocre content
                return {
                    "approved": False,
                    "score": 4,
                    "feedback": "This reads like a chatbot summary, not editorial commentary. Where's the insight? Where's the angle? You've turned a complex story about AI's unexpected trajectory into bland bullet points. The reader learns nothing they couldn't get from skimming headlines. Dig deeper - what does this MEAN? Why should they care beyond 'AI good, concerns exist'? Give me analysis, not regurgitation.",
                    "raw_review": "SCORE: 4/10\nFEEDBACK: This reads like a chatbot summary, not editorial commentary...\nAPPROVED: NO",
                }
            else:
                # Approval for improved content
                return {
                    "approved": True,
                    "score": 8,
                    "feedback": "Much better! Now you're thinking like an editor. The 'societal inflection point' framing gives readers a lens to understand the significance. The observation about blindsided researchers adds credibility and urgency. The governance angle feels earned rather than obligatory. This has voice and perspective - exactly what newsletter readers want.",
                    "raw_review": "SCORE: 8/10\nFEEDBACK: Much better! Now you're thinking like an editor...\nAPPROVED: YES",
                }

        async def revise_content(
            self,
            original_content,
            editor_feedback,
            article_content="",
            user_highlights="",
        ):
            """Mock content revision based on editor feedback."""
            return await self.generate_commentary(article_content, user_highlights, "")

    # Mock content item with user insights
    from src.models.content import ContentItem

    mock_item = ContentItem(
        id="test_1",
        title="AI Systems Show Unexpected Capabilities in Latest Research",
        content="• AI models are advancing faster than predicted\n• Experts caught off guard by rapid progress\n• Calls for better governance and safety measures\n• **Key insight**: We may be in uncharted territory for AI development",
        source="rss",
        url="https://example.com/ai-article",
        author="Tech Reporter",
        source_title="Tech News Daily",
        tags=["AI", "technology", "research"],
        created_at=datetime.now(timezone.utc),
        metadata={},
    )

    # Initialize mock stats tracking
    editorial_stats = {
        "articles_processed": 0,
        "articles_revised": 0,
        "total_revisions": 0,
        "editor_scores": [],
        "newsletter_editor_score": None,
        "common_feedback_themes": [],
    }

    # Create mock OpenRouter client
    openrouter_client = MockOpenRouterClient()

    print("\n🎯 Testing Article-Level Editorial Workflow")
    print("-" * 40)

    # Simulate the editorial workflow
    title = mock_item.title
    user_highlights = mock_item.content

    print(f"📝 Processing article: '{title[:50]}...'")
    print(f"👤 User highlights: {user_highlights[:100]}...")

    # Track article processing
    editorial_stats["articles_processed"] += 1

    # Step 1: Fetch article content
    print(f"\n🎭 Fetching article content from: {mock_item.url}")
    article_content = await openrouter_client.fetch_article_content(str(mock_item.url))
    print(f"✅ Retrieved {len(article_content)} characters of article content")

    # Step 2: Generate initial commentary
    print(f"\n🎭 Writer agent: generating commentary for '{title[:50]}...'")
    commentary = await openrouter_client.generate_commentary(
        article_content, user_highlights, title
    )
    print(f"✅ Generated initial commentary ({len(commentary)} chars)")
    print(f"📝 Commentary preview: {commentary[:150]}...")

    # Step 3: Editorial review and revision loop
    max_revisions = 2
    revision_count = 0
    article_was_revised = False

    while revision_count < max_revisions:
        print(f"\n🎭 Editor agent: reviewing article (attempt {revision_count + 1})")
        review = await openrouter_client.editorial_roast(commentary, "article")

        # Track editor score
        editorial_stats["editor_scores"].append(review["score"])

        if review["approved"]:
            print(f"✅ Editor approved article (score: {review['score']}/10)")
            print(f"💬 Editor feedback: {review['feedback'][:200]}...")
            break

        # Show rejection and feedback
        print(f"❌ Editor rejected article (score: {review['score']}/10)")
        print(f"💬 Editor roast: {review['feedback'][:200]}...")

        print(f"\n🎭 Writer agent: revising based on editor feedback...")
        commentary = await openrouter_client.revise_content(
            commentary, review["feedback"], article_content, user_highlights
        )
        print(f"📝 Revised commentary preview: {commentary[:150]}...")

        revision_count += 1
        article_was_revised = True
        editorial_stats["total_revisions"] += 1

    if revision_count >= max_revisions:
        print(f"⚠️ Max revisions reached for article: {title}")

    if article_was_revised:
        editorial_stats["articles_revised"] += 1

    print(f"\n📊 Final commentary: {commentary}")

    # Step 4: Newsletter-level editorial review
    print(f"\n🎯 Testing Newsletter-Level Editorial Review")
    print("-" * 40)

    mock_newsletter_content = f"""
# THE FILTER
*Curated Briefing • Monday, August 11, 2025*

## LEAD STORIES

{commentary}

## 🔬 TECHNOLOGY
Additional tech stories would appear here...

## 🌍 SOCIETY & CULTURE
Society stories would appear here...
"""

    print(f"🎭 Editor agent: reviewing complete newsletter")
    newsletter_review = await openrouter_client.editorial_roast(
        mock_newsletter_content, "newsletter"
    )

    editorial_stats["newsletter_editor_score"] = newsletter_review["score"]

    if newsletter_review["approved"]:
        print(
            f"✅ Newsletter approved by editor (score: {newsletter_review['score']}/10)"
        )
    else:
        print(
            f"⚠️ Newsletter needs improvement (score: {newsletter_review['score']}/10)"
        )

    print(f"💬 Newsletter feedback: {newsletter_review['feedback'][:200]}...")

    # Display final statistics
    print(f"\n📊 Editorial Workflow Results")
    print("=" * 30)
    print(f"   - Articles processed: {editorial_stats['articles_processed']}")
    print(f"   - Articles revised: {editorial_stats['articles_revised']}")
    avg_score = (
        sum(editorial_stats["editor_scores"]) / len(editorial_stats["editor_scores"])
        if editorial_stats["editor_scores"]
        else 0
    )
    print(f"   - Average editor score: {avg_score:.1f}/10")
    print(
        f"   - Newsletter editor score: {editorial_stats['newsletter_editor_score']}/10"
    )
    print(f"   - Total revisions made: {editorial_stats['total_revisions']}")

    print(f"\n🎉 Multi-LLM Editorial Workflow Complete!")
    print("This demonstrates how the writer and editor agents collaborate")
    print("to produce higher-quality newsletter content through iterative")
    print("feedback and revision cycles.")


if __name__ == "__main__":
    asyncio.run(demo_editorial_workflow())
