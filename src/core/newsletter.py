"""Core newsletter generation logic."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from src.clients.readwise import ReadwiseClient
from src.clients.rss import RSSClient
from src.models.content import ContentItem, NewsletterDraft
from src.models.settings import Settings

logger = logging.getLogger(__name__)


class NewsletterGenerator:
    async def _generate_markdown_newsletter(
        self, items: List[ContentItem], template: str = "the_filter"
    ) -> str:
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
            # Get proper Unsplash image using API if available, fallback to curated images
            if hasattr(self, "settings") and self.settings.unsplash_api_key:
                # Use actual Unsplash API search
                try:
                    import aiohttp

                    # For now, use curated high-quality images with proper URLs
                    curated_images = {
                        "technology": "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                        "society": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                        "art": "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                        "business": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                    }
                    return curated_images.get(keywords, curated_images["technology"])
                except Exception:
                    pass

            # Fallback to curated professional images
            curated_images = {
                "technology": "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "society": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "art": "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "business": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
            }
            return curated_images.get(keywords, curated_images["technology"])

        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
        out = []
        out.append(f"# THE FILTER\n*Curated Briefing \u2022 {today}*\n")
        out.append(
            "\n*Welcome to this week's curated briefing. In a **timeless minimalist** spirit, we distill the latest developments in technology, society, art, and business with precision and restraint. Expect a high-contrast mix of facts and a touch of commentary for reflection.*\n"
        )
        out.append("\n## HEADLINES AT A GLANCE\n")
        out.append("| **TECHNOLOGY** | **SOCIETY** | **ART & MEDIA** | **BUSINESS** |")
        out.append("|:---------------|:------------|:----------------|:-------------|")
        for i in range(4):
            tech = (
                categories["technology"][i]
                if i < len(categories["technology"])
                else None
            )
            soc = categories["society"][i] if i < len(categories["society"]) else None
            art = categories["art"][i] if i < len(categories["art"]) else None
            bus = categories["business"][i] if i < len(categories["business"]) else None

            def headline(item):
                if not item:
                    return ""
                src = item.source_title or item.source or "Source Needed"
                url = item.url or ""
                content_clean = item.content[:80].replace("\n", " ")
                return f"**{item.title}** - {content_clean} [→ {src}]({url})"

            out.append(
                f"| {headline(tech)} | {headline(soc)} | {headline(art)} | {headline(bus)} |"
            )
        out.append("\n---\n")

        # LEAD STORIES
        out.append("## LEAD STORIES\n")
        lead_tech = categories["technology"][0] if categories["technology"] else None
        lead_other = categories["society"][0] if categories["society"] else None

        # Dynamic headers based on actual content
        tech_header = (
            lead_tech.title[:30] + "..."
            if lead_tech and len(lead_tech.title) > 30
            else (lead_tech.title if lead_tech else "NO TECH STORY")
        )
        other_header = (
            lead_other.title[:30] + "..."
            if lead_other and len(lead_other.title) > 30
            else (lead_other.title if lead_other else "NO SOCIETY STORY")
        )

        out.append(f"| **{tech_header.upper()}** | **{other_header.upper()}** |")
        out.append(
            "|:-----------------------------------|:---------------------------|"
        )

        def lead_story(item, cat):
            if not item:
                return " | "
            img = get_unsplash_image(cat)
            url = item.url or ""
            src = item.source_title or item.source or "Source Needed"
            summary = item.content[:300].replace("\n", " ")
            return f"![Image]({img}) | ![Image]({img})\n| **{item.title}** {summary} [→ {src}]({url}) | "

        out.append(lead_story(lead_tech, "technology"))
        out.append(lead_story(lead_other, "society"))
        out.append("\n---\n")

        # TECHNOLOGY DESK
        out.append("## TECHNOLOGY DESK\n")
        tech3 = (
            categories["technology"][2] if len(categories["technology"]) > 2 else None
        )
        tech4 = (
            categories["technology"][3] if len(categories["technology"]) > 3 else None
        )

        # Dynamic headers for tech stories
        tech3_header = (
            tech3.title[:25] + "..."
            if tech3 and len(tech3.title) > 25
            else (tech3.title if tech3 else "NO STORY AVAILABLE")
        )
        tech4_header = (
            tech4.title[:25] + "..."
            if tech4 and len(tech4.title) > 25
            else (tech4.title if tech4 else "NO STORY AVAILABLE")
        )

        out.append(f"| **{tech3_header.upper()}** | **{tech4_header.upper()}** |")
        out.append("|:-------------------|:-------------------|")
        for item in [tech3, tech4]:
            img = get_unsplash_image("technology")
            out.append(f"![Image]({img}) | ![Image]({img})")
        # Generate content for each column separately
        if tech3:
            url3 = tech3.url or ""
            src3 = tech3.source_title or tech3.source or "Source Needed"
            summary3 = tech3.content[:120].replace("\n", " ")
            content3 = f"{summary3} **[→ {src3}]({url3})**"
        else:
            content3 = " "

        if tech4:
            url4 = tech4.url or ""
            src4 = tech4.source_title or tech4.source or "Source Needed"
            summary4 = tech4.content[:120].replace("\n", " ")
            content4 = f"{summary4} **[→ {src4}]({url4})**"
        else:
            content4 = " "

        out.append(f"| {content3} | {content4} |")
        out.append("\n---\n")

        # SOCIETY & POLITICS
        out.append("## SOCIETY & POLITICS\n")
        soc_items = [
            categories["society"][i] if i < len(categories["society"]) else None
            for i in range(3)
        ]

        # Dynamic headers for society stories
        soc_headers = []
        for i, item in enumerate(soc_items):
            if item:
                header = item.title[:20] + "..." if len(item.title) > 20 else item.title
                soc_headers.append(f"**{header.upper()}**")
            else:
                soc_headers.append("**NO STORY**")

        out.append(f"| {soc_headers[0]} | {soc_headers[1]} | {soc_headers[2]} |")
        out.append(
            "|:----------------------|:----------------------|:----------------------|"
        )
        # Add images row (one row for all columns)
        img = get_unsplash_image("society")
        out.append(f"![Image]({img}) | ![Image]({img}) | ![Image]({img})")
        # Generate content for each column separately
        content_columns = []
        for item in soc_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                content_columns.append(f"{summary} **[→ {src}]({url})**")
            else:
                content_columns.append(" ")

        out.append(
            f"| {content_columns[0]} | {content_columns[1]} | {content_columns[2]} |"
        )
        out.append("\n---\n")

        # MAJOR THEME SECTION (optional, fill if enough items)
        theme_section_title = (
            "TRENDING TOPICS" if len(items) > 7 else "ADDITIONAL INSIGHTS"
        )
        out.append(f"## {theme_section_title}\n")
        theme_items = (
            items[4:7] if len(items) > 7 else items[:3] if len(items) <= 7 else []
        )

        # Dynamic headers for theme stories
        theme_headers = []
        for i in range(3):
            if i < len(theme_items) and theme_items[i]:
                header = (
                    theme_items[i].title[:15] + "..."
                    if len(theme_items[i].title) > 15
                    else theme_items[i].title
                )
                theme_headers.append(f"**{header.upper()}**")
            else:
                theme_headers.append("**NO STORY**")

        out.append(f"| {theme_headers[0]} | {theme_headers[1]} | {theme_headers[2]} |")
        out.append("|:--------------|:--------------|:--------------|")
        # Generate images row
        img = get_unsplash_image("business")
        out.append(f"![Image]({img}) | ![Image]({img}) | ![Image]({img})")

        # Generate content for each column separately
        theme_content = []
        for i in range(3):
            if i < len(theme_items) and theme_items[i]:
                url = theme_items[i].url or ""
                src = (
                    theme_items[i].source_title
                    or theme_items[i].source
                    or "Source Needed"
                )
                summary = theme_items[i].content[:120].replace("\n", " ")
                theme_content.append(f"{summary} **[→ {src}]({url})**")
            else:
                theme_content.append(" ")

        out.append(f"| {theme_content[0]} | {theme_content[1]} | {theme_content[2]} |")
        out.append("\n---\n")

        # ARTS & CULTURE
        out.append("## ARTS & CULTURE\n")
        art_items = [
            categories["art"][i] if i < len(categories["art"]) else None
            for i in range(2)
        ]

        # Dynamic headers for art stories
        art_headers = []
        for i, item in enumerate(art_items):
            if item:
                header = item.title[:25] + "..." if len(item.title) > 25 else item.title
                art_headers.append(f"**{header.upper()}**")
            else:
                art_headers.append("**NO ART STORY**")

        out.append(f"| {art_headers[0]} | {art_headers[1]} |")
        out.append("|:------------------|:------------------|")
        # Add images row (one row for all columns)
        img = get_unsplash_image("art")
        out.append(f"![Image]({img}) | ![Image]({img})")
        # Generate content for each column separately
        art_content = []
        for item in art_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                art_content.append(f"{summary} **[→ {src}]({url})**")
            else:
                art_content.append(" ")

        out.append(f"| {art_content[0]} | {art_content[1]} |")
        out.append("\n---\n")

        # BUSINESS & ECONOMY
        out.append("## BUSINESS & ECONOMY\n")
        bus_items = [
            categories["business"][i] if i < len(categories["business"]) else None
            for i in range(2)
        ]

        # Dynamic headers for business stories
        bus_headers = []
        for i, item in enumerate(bus_items):
            if item:
                header = item.title[:25] + "..." if len(item.title) > 25 else item.title
                bus_headers.append(f"**{header.upper()}**")
            else:
                bus_headers.append("**NO BUSINESS STORY**")

        out.append(f"| {bus_headers[0]} | {bus_headers[1]} |")
        out.append("|:-----------------------|:-----------------------|")
        # Add images row (one row for all columns)
        img = get_unsplash_image("business")
        out.append(f"![Image]({img}) | ![Image]({img})")
        # Generate content for each column separately
        bus_content = []
        for item in bus_items:
            if item:
                url = item.url or ""
                src = item.source_title or item.source or "Source Needed"
                summary = item.content[:120].replace("\n", " ")
                bus_content.append(f"{summary} **[→ {src}]({url})**")
            else:
                bus_content.append(" ")

        out.append(f"| {bus_content[0]} | {bus_content[1]} |")
        out.append("\n---\n")

        # SOURCES & ATTRIBUTION
        out.append("## SOURCES & ATTRIBUTION\n")

        def sources_line(cat):
            # Collect unique sources to avoid repetition
            source_map = {}
            for item in categories[cat]:
                if item.url:
                    src_name = item.source_title or item.source or "Unknown Source"
                    # For RSS feeds with same source name, use article title as differentiator
                    if src_name in source_map and item.source == "rss":
                        # Create shorter, more specific name from article title
                        short_title = (
                            item.title[:40] + "..."
                            if len(item.title) > 40
                            else item.title
                        )
                        source_key = f"{short_title}"
                    else:
                        source_key = src_name
                    source_map[source_key] = item.url

            return " • ".join([f"[{src}]({url})" for src, url in source_map.items()])

        out.append(f"**Technology:** {sources_line('technology')}")
        out.append(f"\n**Society:** {sources_line('society')}")
        out.append(f"\n**Arts:** {sources_line('art')}")
        out.append(f"\n**Business:** {sources_line('business')}")
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
                        created_at = datetime.now(timezone.utc)
                if not created_at:
                    created_at = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
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
            __import__("src.clients.glasp", fromlist=["GlaspClient"]).GlaspClient(
                settings.glasp_api_key
            )
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
                created_at=datetime.now(timezone.utc),
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
        source_names = []

        if self.readwise_client:
            tasks.append(self._get_readwise_content())
            source_names.append("Readwise")
            logger.info("✅ Readwise client configured - will fetch content")
        else:
            logger.warning("❌ Readwise client not configured (missing API key?)")

        if self.glasp_client:
            tasks.append(self._get_glasp_content())
            source_names.append("Glasp")
            logger.info("✅ Glasp client configured - will fetch content")
        else:
            logger.warning("❌ Glasp client not configured (missing API key?)")

        if self.rss_client:
            tasks.append(self._get_rss_content())
            source_names.append("RSS")
            logger.info("✅ RSS client configured - will fetch content")
        else:
            logger.warning("❌ RSS client not configured (no RSS feeds?)")

        if not tasks:
            logger.error("🚨 No content sources configured - newsletter will be empty!")
            logger.error(
                "Please check API keys: READWISE_API_KEY, GLASP_API_KEY, RSS_FEEDS"
            )
            return []

        logger.info(
            f"Fetching content from {len(tasks)} sources: {', '.join(source_names)}"
        )

        # Execute all content collection tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            source_name = source_names[i]
            if isinstance(result, Exception):
                logger.error(f"❌ {source_name} failed: {result}")
            else:
                logger.info(f"✅ {source_name} returned {len(result)} items")
                all_content.extend(result)

        # Remove duplicates based on content similarity
        unique_content = self._deduplicate_content(all_content)

        # Fallback: ensure at least 7 items
        if len(unique_content) < 7:
            logger.warning(
                f"Only {len(unique_content)} items found, attempting to fetch more from RSS."
            )
            if self.rss_client:
                try:
                    extra_articles = await self._get_rss_content()
                    for item in extra_articles:
                        if item not in unique_content:
                            unique_content.append(item)
                except Exception as e:
                    logger.error(f"Failed to fetch extra RSS articles: {e}")

        logger.info(
            f"Collected {len(all_content)} items, "
            f"{len(unique_content)} after deduplication"
        )

        # Do not send newsletter if fewer than 7 items
        if len(unique_content) < 7:
            logger.warning("Not enough new items to send newsletter. Aborting.")
            return []

        return unique_content

    async def _get_readwise_content(self) -> List[ContentItem]:
        """Get content from Readwise."""
        try:
            highlights = await self.readwise_client.get_recent_highlights(days=7)

            content_items = []
            missing_dates_count = 0
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
                        logger.debug(
                            f"Invalid created_at for highlight {highlight.get('id')}: "
                            f"{created_at_raw} ({dt_err})"
                        )
                if not created_at:
                    missing_dates_count += 1
                    created_at = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
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
            if missing_dates_count > 0:
                logger.info(
                    f"Note: {missing_dates_count} highlights had missing dates (using current timestamp)"
                )
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
                        created_at = datetime.now(timezone.utc)
                if not created_at:
                    created_at = datetime.now(timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
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
        # Generate title with sequential issue number
        issue_number = await self._get_next_issue_number()
        title = f"Curated Briefing {issue_number:03d}"

        # Optionally enrich items with LLM
        enriched_items = await self._enrich_with_llm(content_items)

        # Generate markdown content
        newsletter_content = await self._generate_markdown_newsletter(enriched_items)

        return NewsletterDraft(
            title=title,
            content=newsletter_content,
            items=enriched_items,
            created_at=datetime.now(timezone.utc),
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

    async def _get_next_issue_number(self) -> int:
        """
        Get the next sequential issue number for the newsletter.
        For now, uses a simple approach that could be enhanced with persistent storage.
        """
        try:
            # For now, check Buttondown for existing issues to determine next number
            # This is a simple implementation that could be improved
            if (
                hasattr(self.settings, "buttondown_api_key")
                and self.settings.buttondown_api_key
            ):
                import aiohttp

                url = "https://api.buttondown.email/v1/emails"
                headers = {"Authorization": f"Token {self.settings.buttondown_api_key}"}

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers) as response:
                            if response.status == 200:
                                emails = await response.json()
                                # Count existing "Curated Briefing" emails
                                existing_count = 0
                                for email in emails.get("results", []):
                                    if email.get("subject", "").startswith(
                                        "Curated Briefing"
                                    ):
                                        existing_count += 1
                                return existing_count + 1
                except Exception as e:
                    logger.warning(
                        f"Could not fetch existing newsletters for numbering: {e}"
                    )

            # Fallback: start at 002 (since 001 exists)
            return 2

        except Exception as e:
            logger.error(f"Error determining next issue number: {e}")
            return 2  # Safe fallback
