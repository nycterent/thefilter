"""Core newsletter generation logic."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from src.clients.readwise import ReadwiseClient
from src.clients.rss import RSSClient
from src.models.content import ContentItem, NewsletterDraft
from src.models.settings import Settings

logger = logging.getLogger(__name__)


class NewsletterGenerator:
    """Main newsletter generation orchestrator."""

    def __init__(self, settings: Settings):
        """Initialize newsletter generator.

        Args:
            settings: Application settings with API keys
        """
        self.settings = settings
        self.readwise_client = (
            ReadwiseClient(settings.readwise_api_key)
            if settings.readwise_api_key
            else None
        )

        # Parse RSS feeds from comma-separated string
        rss_feeds = []
        if settings.rss_feeds:
            rss_feeds = [
                url.strip() for url in settings.rss_feeds.split(",") if url.strip()
            ]
        self.rss_client = RSSClient(rss_feeds) if rss_feeds else None

    async def generate_newsletter(self, dry_run: bool = False) -> NewsletterDraft:
        """Generate a complete newsletter.

        Args:
            dry_run: If True, don't actually publish, just generate content

        Returns:
            Generated newsletter draft
        """
        logger.info(f"Starting newsletter generation (dry_run={dry_run})")

        # Step 1: Aggregate content from all sources
        content_items = await self._aggregate_content()

        if not content_items:
            logger.warning("No content found from any sources")
                return NewsletterDraft(
                    title="No Content Available",
                    content="No new content was found from configured sources this week.",
                    items=[],
                    created_at=datetime.utcnow(),
                )

        logger.info(f"Aggregated {len(content_items)} content items")

        # Step 2: Process and organize content
        processed_content = await self._process_content(content_items)

        # Step 3: Generate newsletter draft
        newsletter = await self._create_newsletter_draft(processed_content)

        # Step 4: Publish (if not dry run)
        if not dry_run and self.settings.buttondown_api_key:
            await self._publish_newsletter(newsletter)
            logger.info("Newsletter published successfully")
        else:
            logger.info(
                "Newsletter generation completed (not published - dry run mode)"
            )

        return newsletter

    async def _aggregate_content(self) -> List[ContentItem]:
        """Aggregate content from all configured sources.

        Returns:
            List of content items from all sources
        """
        all_content = []

        # Collect content from all sources concurrently
        tasks = []

        if self.readwise_client:
            tasks.append(self._get_readwise_content())

        if self.rss_client:
            tasks.append(self._get_rss_content())

        if not tasks:
            logger.warning("No content sources configured")
            return []

        # Execute all content collection tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Content source {i} failed: {result}")
            else:
                all_content.extend(result)

        # Remove duplicates based on content similarity
        unique_content = self._deduplicate_content(all_content)

        logger.info(
            f"Collected {len(all_content)} items, "
            f"{len(unique_content)} after deduplication"
        )
        return unique_content

    async def _get_readwise_content(self) -> List[ContentItem]:
        """Get content from Readwise."""
        try:
            highlights = await self.readwise_client.get_recent_highlights(days=7)

            content_items = []
            for highlight in highlights:
                item = ContentItem(
                    id=f"readwise_{highlight['id']}",
                    title=highlight["title"],
                    content=highlight["content"],
                    source=highlight["source"],
                    url=highlight.get("url"),
                    author=highlight.get("author"),
                    source_title=highlight.get("source_title"),
                    tags=highlight.get("tags", []),
                    created_at=highlight.get("created_at"),
                    metadata={
                        "note": highlight.get("note"),
                        "location": highlight.get("location"),
                        "location_type": highlight.get("location_type"),
                    },
                )
                content_items.append(item)

            logger.info(f"Retrieved {len(content_items)} items from Readwise")
            return content_items

        except Exception as e:
            logger.error(f"Error getting Readwise content: {e}")
            return []

    async def _get_rss_content(self) -> List[ContentItem]:
        """Get content from RSS feeds."""
        try:
            articles = await self.rss_client.get_recent_articles(days=7)

            content_items = []
            for article in articles:
                item = ContentItem(
                    id=f"rss_{hash(article['id'])}",
                    title=article["title"],
                    content=article.get("summary", article.get("content", "")),
                    source=article["source"],
                    url=article.get("url"),
                    author=article.get("author"),
                    source_title=article.get("source_title"),
                    tags=article.get("tags", []),
                    created_at=article.get("published_at"),
                    metadata={
                        "source_url": article.get("source_url"),
                        "full_content": article.get("content"),
                    },
                )
                content_items.append(item)

            logger.info(f"Retrieved {len(content_items)} items from RSS feeds")
            return content_items

        except Exception as e:
            logger.error(f"Error getting RSS content: {e}")
            return []

    def _deduplicate_content(
        self, content_items: List[ContentItem]
    ) -> List[ContentItem]:
        """Remove duplicate content items.

        Args:
            content_items: List of content items

        Returns:
            Deduplicated list
        """
        # Simple deduplication by title similarity
        unique_items = []
        seen_titles = set()

        for item in content_items:
            # Normalize title for comparison
            normalized_title = item.title.lower().strip()

            # Skip if we've seen a very similar title
            is_duplicate = False
            for seen_title in seen_titles:
                if self._title_similarity(normalized_title, seen_title) > 0.8:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_items.append(item)
                seen_titles.add(normalized_title)

        return unique_items

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate simple similarity between two titles.

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score between 0 and 1
        """
        if not title1 or not title2:
            return 0.0

        # Simple word-based similarity
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    async def _process_content(
        self, content_items: List[ContentItem]
    ) -> List[ContentItem]:
        """Process and enrich content items.

        Args:
            content_items: Raw content items

        Returns:
            Processed content items
        """
        # For now, just return items sorted by date
        # TODO: Add AI processing, categorization, summarization

        processed_items = sorted(
            content_items, key=lambda x: x.created_at or "", reverse=True
        )

        # Limit to top 20 items to keep newsletter manageable
        return processed_items[:20]

    async def _create_newsletter_draft(
        self, content_items: List[ContentItem]
    ) -> NewsletterDraft:
        """Create newsletter draft from processed content.

        Args:
            content_items: Processed content items

        Returns:
            Newsletter draft
        """
        # Generate title with current date
        today = datetime.utcnow()
        title = f"Weekly Newsletter - {today.strftime('%B %d, %Y')}"

        # Create sections
        readwise_items = [item for item in content_items if item.source == "readwise"]
        rss_items = [item for item in content_items if item.source == "rss"]

        content_sections = []

        if readwise_items:
            content_sections.append(self._create_readwise_section(readwise_items))

        if rss_items:
            content_sections.append(self._create_rss_section(rss_items))

        # Combine all sections
        newsletter_content = "\\n\\n".join(content_sections)

        # Add footer
        newsletter_content += (
            "\\n\\n---\\n\\n*This newsletter was automatically generated "
            "by your Newsletter Bot.*"
        )

        return NewsletterDraft(
            title=title,
            content=newsletter_content,
            content_items=content_items,
            generated_at=datetime.utcnow().isoformat(),
            metadata={
                "total_items": len(content_items),
                "readwise_items": len(readwise_items),
                "rss_items": len(rss_items),
            },
        )

    def _create_readwise_section(self, items: List[ContentItem]) -> str:
        """Create Readwise highlights section.

        Args:
            items: Readwise content items

        Returns:
            Formatted section content
        """
        section = "## 📚 Highlights from Readwise\\n\\n"

        for item in items[:10]:  # Limit to top 10
            section += f"### {item.source_title}"
            if item.author:
                section += f" by {item.author}"
            section += "\\n\\n"
            section += f"> {item.content}\\n\\n"

            if item.metadata and item.metadata.get("note"):
                section += f"**My note:** {item.metadata['note']}\\n\\n"

            section += "---\\n\\n"

        return section

    def _create_rss_section(self, items: List[ContentItem]) -> str:
        """Create RSS articles section.

        Args:
            items: RSS content items

        Returns:
            Formatted section content
        """
        section = "## 🌐 Latest Articles\\n\\n"

        for item in items[:10]:  # Limit to top 10
            section += f"### [{item.title}]({item.url})\\n\\n"

            if item.author:
                section += f"*By {item.author}*\\n\\n"

            section += f"{item.content}\\n\\n"
            section += f"*Source: {item.source_title}*\\n\\n"
            section += "---\\n\\n"

        return section

    async def _publish_newsletter(self, newsletter: NewsletterDraft) -> bool:
        """Publish newsletter to Buttondown.

        Args:
            newsletter: Newsletter draft to publish

        Returns:
            True if published successfully
        """
        try:
            # TODO: Implement Buttondown API integration
            logger.info("Publishing newsletter to Buttondown...")

            # Placeholder for now
            logger.info(f"Would publish newsletter: {newsletter.title}")
            logger.info(f"Content length: {len(newsletter.content)} characters")
            logger.info(f"Total items: {len(newsletter.content_items)}")

            return True

        except Exception as e:
            logger.error(f"Error publishing newsletter: {e}")
            return False

    async def test_connections(self) -> Dict[str, bool]:
        """Test connections to all configured services.

        Returns:
            Dictionary of service connection statuses
        """
        results = {}

        # Test Readwise
        if self.readwise_client:
            results["readwise"] = await self.readwise_client.test_connection()
        else:
            results["readwise"] = False

        # Test RSS feeds
        if self.rss_client:
            rss_results = await self.rss_client.test_feeds()
            results["rss_feeds"] = rss_results
            results["rss_overall"] = any(rss_results.values()) if rss_results else False
        else:
            results["rss_overall"] = False

        # TODO: Test other services (Buttondown, OpenRouter, etc.)

        return results
