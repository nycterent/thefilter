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
    async def _generate_markdown_newsletter(self, items: List[ContentItem], template: str = "the_filter") -> str:
        """
        Generate newsletter content in Markdown format using the specified template.
        Supported templates: 'the_filter' (default), others can be added.
        """
        if template == "the_filter":
            return await self._generate_the_filter_newsletter(items)
        # Fallback to legacy simple grouping
        return await self._generate_simple_newsletter(items)

    async def _generate_the_filter_newsletter(self, items: List[ContentItem]) -> str:
        """
        Generate 'The Filter' newsletter in strict markdown table format.
        """
        # Categorize items
        categories = {
            "technology": [],
            "society": [],
            "art": [],
            "business": [],
        }
        for item in items:
            cats = [t.lower() for t in item.tags]
            # Heuristic: tag/category mapping
            if "tech" in cats or "technology" in cats:
                categories["technology"].append(item)
            elif "society" in cats or "politics" in cats:
                categories["society"].append(item)
            elif "art" in cats or "media" in cats or "culture" in cats:
                categories["art"].append(item)
            elif "business" in cats or "economy" in cats:
                categories["business"].append(item)
            else:
                # Fallback: assign by source
                if item.source in ["readwise", "glasp"]:
                    categories["technology"].append(item)
                elif item.source == "rss":
                    categories["society"].append(item)
                else:
                    categories["business"].append(item)

        # Helper for Unsplash image
        def get_unsplash_image(keywords: str) -> str:
            # Use a static Unsplash image for now; can be replaced with API call
            # Example: circuits, people, gallery, office
            images = {
                "technology": "circuit-board-370x150?auto=format",
                "society": "people-meeting-370x150?auto=format",
                "art": "art-gallery-370x150?auto=format",
                "business": "office-370x150?auto=format",
            }
            return f"https://images.unsplash.com/photo-{images.get(keywords, 'circuit-board-370x150?auto=format')}"

        today = datetime.utcnow().strftime("%B %d, %Y")
        out = []
        out.append(f"# THE FILTER\n*Weekly Curated Briefing • {today}*\n\n---\n")

        # HEADLINES AT A GLANCE
        out.append("## HEADLINES AT A GLANCE\n")
        out.append("| **TECHNOLOGY** | **SOCIETY** | **ART & MEDIA** | **BUSINESS** |")
        out.append("|:---------------|:------------|:----------------|:-------------|")
        for i in range(4):
            tech = categories["technology"][i] if i < len(categories["technology"]) else None
            soc = categories["society"][i] if i < len(categories["society"]) else None
            art = categories["art"][i] if i < len(categories["art"]) else None
            bus = categories["business"][i] if i < len(categories["business"]) else None

            def headline(item):
                if not item:
                    return ""
                src = item.source_title or item.source or "Source Needed"
                url = item.url or ""
                link = (
                    f"**[→ {src}]({url})**" if url else "**[→ Source Needed]**"
                )
                return f"{item.title} {link}"

            out.append(
                f"| {headline(tech)} | {headline(soc)} | "
                f"{headline(art)} | {headline(bus)} |"
            )
        out.append("\n---\n")

        # LEAD STORIES
        out.append("## LEAD STORIES\n")
        lead_tech = categories["technology"][0] if categories["technology"] else None

        def lead_story(item, cat):
            if not item:
                return ""
            img = get_unsplash_image(cat)
            url = item.url or ""
            src = item.source_title or item.source or "Source Needed"
            summary = item.content[:180].replace("\n", " ")
            return (
                f"![Image]({img}) | ![Image]({img})\n| "
                f"{summary} **[→ {src}]({url})** | "
                f"{summary} **[→ {src}]({url})**"
            )
        out.append("| **[BIGGEST TECH STORY]** | **[BIGGEST OTHER STORY]** |")
        out.append("|:-------------------------|:---------------------------|")
        out.append(
            lead_story(lead_tech, "technology")
        )
        out.append("\n---\n")

        # TECHNOLOGY DESK
        out.append("## TECHNOLOGY DESK\n")
        tech3 = categories["technology"][2] if len(categories["technology"]) > 2 else None
        tech4 = categories["technology"][3] if len(categories["technology"]) > 3 else None
        out.append("| **[TECH STORY 3]** | **[TECH STORY 4]** |")
        out.append("|:-------------------|:-------------------|")
        for item in [tech3, tech4]:
            img = get_unsplash_image("technology")
            out.append(
                f"![Image]({img}) | ![Image]({img})"
            )
        for item in [tech3, tech4]:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                out.append(
                    f"{summary} **[→ {src}]({url})** | "
                    f"{summary} **[→ {src}]({url})**"
                )
            else:
                out.append(" | ")
        out.append("\n---\n")

        # SOCIETY & POLITICS
        out.append("## SOCIETY & POLITICS\n")
        soc_items = [categories["society"][i] if i < len(categories["society"]) else None for i in range(3)]
        out.append("| **[SOCIETY STORY 1]** | **[SOCIETY STORY 2]** | **[SOCIETY STORY 3]** |")
        out.append("|:----------------------|:----------------------|:----------------------|")
        for item in soc_items:
            img = get_unsplash_image("society")
            out.append(
                f"![Image]({img}) | ![Image]({img}) | ![Image]({img})"
            )
        for item in soc_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                out.append(
                    f"{summary} **[→ {src}]({url})** | "
                    f"{summary} **[→ {src}]({url})** | "
                    f"{summary} **[→ {src}]({url})**"
                )
            else:
                out.append(" | | ")
        out.append("\n---\n")

        # MAJOR THEME SECTION (optional, fill if enough items)
        out.append("## [MAJOR THEME SECTION IF APPLICABLE]\n")
        theme_items = items[4:7] if len(items) > 7 else []
        out.append("| **[STORY 1]** | **[STORY 2]** | **[STORY 3]** |")
        out.append("|:--------------|:--------------|:--------------|")
        for item in theme_items:
            img = get_unsplash_image("business")
            out.append(
                f"![Image]({img}) | | "
            )
        for item in theme_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                out.append(f"{summary} | | ")
            else:
                out.append(" | | ")
        out.append("\n---\n")

        # ARTS & CULTURE
        out.append("## ARTS & CULTURE\n")
        art_items = [categories["art"][i] if i < len(categories["art"]) else None for i in range(2)]
        out.append("| **[ART STORY 1]** | **[ART STORY 2]** |")
        out.append("|:------------------|:------------------|")
        for item in art_items:
            img = get_unsplash_image("art")
            out.append(
                f"![Image]({img}) | ![Image]({img})"
            )
        for item in art_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                out.append(
                    f"{summary} **[→ {src}]({url})** | "
                    f"{summary} **[→ {src}]({url})**"
                )
            else:
                out.append(" | ")
        out.append("\n---\n")

        # BUSINESS & ECONOMY
        out.append("## BUSINESS & ECONOMY\n")
        bus_items = [categories["business"][i] if i < len(categories["business"]) else None for i in range(2)]
        out.append("| **[BUSINESS STORY 1]** | **[BUSINESS STORY 2]** |")
        out.append("|:-----------------------|:-----------------------|")
        for item in bus_items:
            img = get_unsplash_image("business")
            out.append(
                f"![Image]({img}) | ![Image]({img})"
            )
        for item in bus_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                out.append(
                    f"{summary} **[→ {src}]({url})** | "
                    f"{summary} **[→ {src}]({url})**"
                )
            else:
                out.append(" | ")
        out.append("\n---\n")

        # SOURCES & ATTRIBUTION
        out.append("## SOURCES & ATTRIBUTION\n")
        def sources_line(cat):
            srcs = [item.source_title or item.source for item in categories[cat] if item.url]
            urls = [item.url for item in categories[cat] if item.url]
            return " • ".join(
                [f"[{src}]({url})" for src, url in zip(srcs, urls)]
            )
        out.append(
            f"**Technology:** {sources_line('technology')}"
        )
        out.append(
            f"\n**Society:** {sources_line('society')}"
        )
        out.append(
            f"\n**Arts:** {sources_line('art')}"
        )
        out.append(
            f"\n**Business:** {sources_line('business')}"
        )
        out.append(
            "\n*The Filter curates and synthesizes from original reporting. All rights remain with original publishers.*\n"
        )
        return "\n".join(out)

    async def _generate_simple_newsletter(self, items: List[ContentItem]) -> str:
        """Legacy fallback: simple grouping by source."""
        sections = []
        sources = {item.source for item in items}
        for source in sorted(sources):
            source_items = [item for item in items if item.source == source]
            sections.append(f"## {source.title()}\n")
            for item in source_items:
                sections.append(f"### {item.title}")
                if item.author:
                    sections.append(f"*By {item.author}*")
                if item.source_title:
                    sections.append(f"*Source: {item.source_title}*")
                sections.append(f"> {item.content}")
                if item.metadata and item.metadata.get("note"):
                    sections.append(f"**Note:** {item.metadata['note']}")
                sections.append("---\n")
        sections.append(
            "\n---\n*This newsletter was automatically generated by your Newsletter Bot.*"
        )
        return "\n".join(sections)

    async def _enrich_with_llm(self, items: List[ContentItem]) -> List[ContentItem]:
        """Scaffold for LLM enrichment (summarization, categorization, etc.)."""
        # TODO: Integrate with OpenAI, Claude, or other LLM APIs
        # For now, return items unchanged
        return items

    async def _get_glasp_content(self) -> List[ContentItem]:
        """Get content from Glasp."""
        try:
            highlights = await self.glasp_client.get_highlights(days=7)
            content_items = []
            for highlight in highlights:
                created_at_raw = highlight.get("created_at")
                created_at = None
                if created_at_raw:
                    try:
                        created_at = datetime.fromisoformat(
                            created_at_raw.replace("Z", "+00:00")
                        )
                    except Exception:
                        created_at = datetime.utcnow()
                if not created_at:
                    created_at = datetime.now(datetime.timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                item = ContentItem(
                    id=f"glasp_{highlight.get('id', '')}",
                    title=highlight.get("title", ""),
                    content=highlight.get("text", ""),
                    source="glasp",
                    url=highlight.get("url"),
                    author=highlight.get("author"),
                    source_title=highlight.get("source_title"),
                    tags=highlight.get("tags", []),
                    created_at=created_at,
                    metadata={
                        "note": highlight.get("note"),
                        "location": highlight.get("location"),
                        "location_type": highlight.get("location_type"),
                    },
                )
                content_items.append(item)
            logger.info(f"Retrieved {len(content_items)} items from Glasp")
            return content_items
        except Exception as e:
            logger.error(f"Error getting Glasp content: {e}")
            return []
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

        self.glasp_client = (
            __import__("src.clients.glasp", fromlist=["GlaspClient"])
            .GlaspClient(settings.glasp_api_key)
            if getattr(settings, "glasp_api_key", None)
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

        if self.glasp_client:
            tasks.append(self._get_glasp_content())

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
                created_at_raw = highlight.get("created_at")
                created_at = None
                if created_at_raw:
                    try:
                        # Try parsing ISO format
                        created_at = datetime.fromisoformat(
                            created_at_raw.replace("Z", "+00:00")
                        )
                    except Exception as dt_err:
                        logger.warning(
                            f"Invalid created_at for highlight {highlight.get('id')}: "
                            f"{created_at_raw} ({dt_err})"
                        )
                if not created_at:
                    logger.info(
                        f"Highlight {highlight.get('id')} missing or invalid date."
                    )
                    logger.info("Using now() as fallback.")
                    created_at = datetime.now(datetime.timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                try:
                    item = ContentItem(
                        id=f"readwise_{highlight['id']}",
                        title=highlight["title"],
                        content=highlight["content"],
                        source=highlight["source"],
                        url=highlight.get("url"),
                        author=highlight.get("author"),
                        source_title=highlight.get("source_title"),
                        tags=highlight.get("tags", []),
                        created_at=created_at,
                        metadata={
                            "note": highlight.get("note"),
                            "location": highlight.get("location"),
                            "location_type": highlight.get("location_type"),
                        },
                    )
                    content_items.append(item)
                except Exception as item_err:
                    logger.error(
                        "Failed to create ContentItem for highlight %s: %s",
                        highlight.get("id"),
                        item_err,
                    )
                    continue

            logger.info(f"Retrieved {len(content_items)} valid items from Readwise")
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
                published_at = article.get("published_at")
                created_at = None
                if published_at:
                    try:
                        created_at = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except Exception:
                        created_at = datetime.now(datetime.timezone.utc)
                if not created_at:
                    created_at = datetime.now(datetime.timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                item = ContentItem(
                    id=f"rss_{hash(article['id'])}",
                    title=article["title"],
                    content=article.get("summary", article.get("content", "")),
                    source=article["source"],
                    url=article.get("url"),
                    author=article.get("author"),
                    source_title=article.get("source_title"),
                    tags=article.get("tags", []),
                    created_at=created_at,
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
        title = f"Curated Briefing - {today.strftime('%B %d, %Y')}"

        # Optionally enrich items with LLM
        enriched_items = await self._enrich_with_llm(content_items)

        # Generate markdown content
        newsletter_content = await self._generate_markdown_newsletter(enriched_items)

        return NewsletterDraft(
            title=title,
            content=newsletter_content,
            items=enriched_items,
            created_at=datetime.utcnow(),
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
        import aiohttp

        try:
            logger.info("Publishing newsletter to Buttondown...")
            api_key = self.settings.buttondown_api_key
            if not api_key:
                logger.error("No Buttondown API key provided.")
                return False

            url = "https://api.buttondown.email/v1/emails"
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "subject": newsletter.title,
                "body": newsletter.content,
                # Optionally, you can add "to" or "tags" if needed
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 201:
                        logger.info(
                            f"Draft published to Buttondown: {newsletter.title}"
                        )
                        return True
                    else:
                        error_detail = await response.text()
                        status_msg = f"Buttondown API error {response.status}:"
                        logger.error(status_msg)
                        # Split error detail into multiple lines if needed
                        for line in str(error_detail).splitlines():
                            logger.error(f"Buttondown error detail: {line}")
                        return False

        except Exception as e:
            logger.error(f"Error publishing newsletter: {e}")
            return False

    async def test_connections(self) -> Dict[str, bool]:
        """Test connections to all configured services.
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
