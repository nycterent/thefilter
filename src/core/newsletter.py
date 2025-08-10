"""Core newsletter generation logic."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from src.clients.openrouter import OpenRouterClient
from src.clients.readwise import ReadwiseClient
from src.clients.rss import RSSClient
from src.clients.unsplash import UnsplashClient
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
            # Improved categorization using multiple signals
            category = await self._categorize_content(item)
            categories[category].append(item)

        # Ensure balanced distribution across categories
        self._balance_categories(categories)

        # Helper for dynamic Unsplash images
        async def get_unsplash_image(category: str, topic_hint: str = "") -> str:
            """Get dynamic image using Unsplash API or fallback to curated images."""
            if self.unsplash_client:
                try:
                    return await self.unsplash_client.get_category_image(category, topic_hint)
                except Exception as e:
                    logger.debug(f"Unsplash API failed, using fallback: {e}")
            
            # Fallback to curated professional images
            curated_images = {
                "technology": "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "society": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "art": "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                "business": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
            }
            return curated_images.get(category, curated_images["technology"])

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

        async def lead_story(item, cat):
            if not item:
                return " | "
            img = await get_unsplash_image(cat)
            url = item.url or ""
            src = item.source_title or item.source or "Source Needed"
            summary = item.content[:300].replace("\n", " ")
            return f"![Image]({img}) | ![Image]({img})\n| **{item.title}** {summary} [→ {src}]({url}) | "

        out.append(await lead_story(lead_tech, "technology"))
        out.append(await lead_story(lead_other, "society"))
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
            img = await get_unsplash_image("technology")
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
        img = await get_unsplash_image("society")
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
        img = await get_unsplash_image("business")
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
        img = await get_unsplash_image("art")
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
        img = await get_unsplash_image("business")
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

    async def _categorize_content(self, item: ContentItem) -> str:
        """Intelligently categorize content using AI when available, fallback to keywords."""
        # Try AI categorization first if OpenRouter is available
        if self.openrouter_client:
            try:
                ai_category = await self.openrouter_client.categorize_content(
                    item.title, item.content, item.tags
                )
                if ai_category:
                    return ai_category
            except Exception as e:
                logger.debug(f"AI categorization failed, using fallback: {e}")
        
        # Fallback to keyword-based categorization
        tags_lower = [tag.lower() for tag in item.tags]
        
        # Technology keywords
        tech_keywords = ['technology', 'tech', 'ai', 'artificial intelligence', 'machine learning', 
                        'software', 'computer', 'digital', 'internet', 'data', 'algorithm',
                        'programming', 'code', 'cybersecurity', 'blockchain', 'crypto']
        
        # Society keywords  
        society_keywords = ['politics', 'government', 'policy', 'law', 'society', 'social',
                           'democracy', 'election', 'war', 'conflict', 'human rights', 'justice']
        
        # Art keywords
        art_keywords = ['art', 'culture', 'media', 'film', 'music', 'book', 'literature',
                       'design', 'creative', 'artist', 'entertainment', 'museum']
        
        # Business keywords
        business_keywords = ['business', 'economy', 'economic', 'finance', 'market', 'company',
                            'startup', 'investment', 'money', 'trade', 'commerce', 'industry']
        
        # Check content and title for keywords
        content_text = f"{item.title} {item.content}".lower()
        
        # Count keyword matches
        tech_score = sum(1 for keyword in tech_keywords if keyword in content_text)
        society_score = sum(1 for keyword in society_keywords if keyword in content_text)
        art_score = sum(1 for keyword in art_keywords if keyword in content_text)
        business_score = sum(1 for keyword in business_keywords if keyword in content_text)
        
        # Add tag-based scoring
        tech_score += sum(1 for tag in tags_lower if any(kw in tag for kw in tech_keywords))
        society_score += sum(1 for tag in tags_lower if any(kw in tag for kw in society_keywords))
        art_score += sum(1 for tag in tags_lower if any(kw in tag for kw in art_keywords))
        business_score += sum(1 for tag in tags_lower if any(kw in tag for kw in business_keywords))
        
        # Determine category based on highest score
        scores = {
            'technology': tech_score,
            'society': society_score, 
            'art': art_score,
            'business': business_score
        }
        
        best_category = max(scores, key=scores.get)
        
        # If no clear winner (all scores 0), use source-based fallback
        if scores[best_category] == 0:
            if item.source in ["readwise", "glasp"]:
                return "technology"
            else:
                return "society"
                
        return best_category
    
    def _balance_categories(self, categories: dict) -> None:
        """Ensure balanced distribution of content across categories."""
        total_items = sum(len(items) for items in categories.values())
        
        if total_items == 0:
            logger.warning("No content items to balance across categories")
            return
            
        # Template requirements: technology(4), society(3), art(2), business(2) = 11 minimum
        template_requirements = {
            'technology': 4,  # Headlines + technology desk  
            'society': 3,     # Society section
            'art': 2,         # Arts section
            'business': 2     # Business section
        }
        
        # Scale down requirements if we don't have enough total items
        total_required = sum(template_requirements.values())  # 11
        if total_items < total_required:
            scale_factor = total_items / total_required
            for cat in template_requirements:
                template_requirements[cat] = max(1, int(template_requirements[cat] * scale_factor))
        
        min_per_category = template_requirements
        
        # Find categories that need items
        categories_needing_items = []
        for cat, items in categories.items():
            needed = max(0, min_per_category[cat] - len(items))
            if needed > 0:
                categories_needing_items.extend([cat] * needed)
        
        if categories_needing_items:
            # Find categories with excess items (more than their requirement)
            donor_items = []
            for cat, items in categories.items():
                required = min_per_category[cat]
                if len(items) > required:
                    # Take excess items from over-populated categories
                    excess = len(items) - required
                    for _ in range(min(excess, len(categories_needing_items))):
                        if items:  # Safety check
                            donor_items.append((cat, items.pop()))
            
            # Distribute donor items to categories that need them
            for i, category_needing in enumerate(categories_needing_items):
                if i < len(donor_items):
                    donor_cat, item = donor_items[i]
                    categories[category_needing].append(item)
                    logger.debug(f"Rebalanced: moved item from {donor_cat} to {category_needing}")
        
        # Log final distribution
        distribution = {cat: len(items) for cat, items in categories.items()}
        logger.info(f"Category distribution after balancing: {distribution}")

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

        # Initialize content source clients with validation
        self.readwise_client = self._init_readwise_client(settings)
        self.glasp_client = self._init_glasp_client(settings)
        self.rss_client = self._init_rss_client(settings)
        self.openrouter_client = self._init_openrouter_client(settings)
        self.unsplash_client = self._init_unsplash_client(settings)

        # Log source configuration status
        logger.info("📋 Content source configuration:")
        logger.info(
            f"   - Readwise: {'✅ Enabled' if self.readwise_client else '❌ Disabled (no API key)'}"
        )
        logger.info(
            f"   - Glasp: {'✅ Enabled' if self.glasp_client else '❌ Disabled (no API key)'}"
        )
        logger.info(
            f"   - RSS Feeds: {'✅ Enabled' if self.rss_client else '❌ Disabled (no feeds configured)'}"
        )

        # Validate that at least one source is available
        active_sources = sum(
            [
                1
                for client in [self.readwise_client, self.glasp_client, self.rss_client]
                if client is not None
            ]
        )

        if active_sources == 0:
            logger.error(
                "🚨 FATAL: No content sources configured! Newsletter generation cannot proceed."
            )
            logger.error(
                "Please set at least one of: READWISE_API_KEY, GLASP_API_KEY, RSS_FEEDS"
            )
            raise ValueError(
                "No content sources available. Please configure at least one API key or RSS feed."
            )
        else:
            logger.info(
                f"✅ {active_sources} content source(s) configured successfully"
            )

    def _init_readwise_client(self, settings: Settings):
        """Initialize Readwise client with validation."""
        if not settings.readwise_api_key or not settings.readwise_api_key.strip():
            logger.info("🔧 Readwise disabled: READWISE_API_KEY not set or empty")
            return None
        
        try:
            return ReadwiseClient(settings.readwise_api_key.strip())
        except Exception as e:
            logger.error(f"❌ Failed to initialize Readwise client: {e}")
            return None

    def _init_glasp_client(self, settings: Settings):
        """Initialize Glasp client with validation."""
        if not settings.glasp_api_key or not settings.glasp_api_key.strip():
            logger.info("🔧 Glasp disabled: GLASP_API_KEY not set or empty")
            return None
        
        try:
            GlaspClient = __import__("src.clients.glasp", fromlist=["GlaspClient"]).GlaspClient
            return GlaspClient(settings.glasp_api_key.strip())
        except Exception as e:
            logger.error(f"❌ Failed to initialize Glasp client: {e}")
            return None

    def _init_rss_client(self, settings: Settings):
        """Initialize RSS client with validation."""
        if not settings.rss_feeds or not settings.rss_feeds.strip():
            logger.info("🔧 RSS disabled: RSS_FEEDS not set or empty")
            return None
        
        # Parse and validate RSS feeds
        rss_feeds = []
        for url in settings.rss_feeds.split(","):
            url = url.strip()
            if url:
                if self._is_valid_rss_url(url):
                    rss_feeds.append(url)
                else:
                    logger.warning(f"⚠️ Invalid RSS URL skipped: {url}")
        
        if not rss_feeds:
            logger.warning("🔧 RSS disabled: No valid RSS feed URLs found")
            return None
        
        try:
            logger.info(f"🔧 RSS enabled with {len(rss_feeds)} feed(s)")
            return RSSClient(rss_feeds)
        except Exception as e:
            logger.error(f"❌ Failed to initialize RSS client: {e}")
            return None

    def _init_openrouter_client(self, settings: Settings):
        """Initialize OpenRouter client with validation."""
        if not settings.openrouter_api_key or not settings.openrouter_api_key.strip():
            logger.info("🔧 OpenRouter disabled: OPENROUTER_API_KEY not set or empty")
            return None
        
        try:
            logger.info("🔧 OpenRouter enabled for AI content processing")
            return OpenRouterClient(settings.openrouter_api_key)
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenRouter client: {e}")
            return None

    def _init_unsplash_client(self, settings: Settings):
        """Initialize Unsplash client with validation."""
        if not settings.unsplash_api_key or not settings.unsplash_api_key.strip():
            logger.info("🔧 Unsplash disabled: UNSPLASH_API_KEY not set or empty")
            return None
        
        try:
            logger.info("🔧 Unsplash enabled for dynamic newsletter images")
            return UnsplashClient(settings.unsplash_api_key)
        except Exception as e:
            logger.error(f"❌ Failed to initialize Unsplash client: {e}")
            return None

    def _is_valid_rss_url(self, url: str) -> bool:
        """Basic validation for RSS URL format."""
        import re
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(url_pattern, url))

    async def generate_newsletter(self, dry_run: bool = False) -> NewsletterDraft:
        """Generate a complete newsletter.

        Args:
            dry_run: If True, don't actually publish, just generate content

        Returns:
            Generated newsletter draft
        """
        logger.info(f"Starting newsletter generation (dry_run={dry_run})")

        # Check if we have any configured sources before proceeding
        active_sources = sum(
            [
                1
                for client in [self.readwise_client, self.glasp_client, self.rss_client]
                if client is not None
            ]
        )

        if active_sources == 0:
            logger.error(
                "🚨 Cannot generate newsletter: No content sources are configured!"
            )
            return NewsletterDraft(
                title="Configuration Error",
                content="Newsletter generation failed: No content sources configured. Please set at least one of: READWISE_API_KEY, GLASP_API_KEY, or RSS_FEEDS.",
                items=[],
                created_at=datetime.now(timezone.utc),
            )

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
        
        # Step 2.5: Enhance content quality
        enhanced_content = await self._enhance_content_quality(processed_content)

        # Step 3: Generate newsletter draft
        newsletter = await self._create_newsletter_draft(enhanced_content)

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
        """Get content from Readwise Reader - recent documents."""
        try:
            # Get recent documents from Readwise Reader
            documents = await self.readwise_client.get_recent_reader_documents(days=7)

            content_items = []
            for doc in documents:
                # Parse document timestamps
                created_at_raw = doc.get("created_at") or doc.get("updated_at")
                created_at = None
                
                if created_at_raw:
                    try:
                        created_at = datetime.fromisoformat(
                            created_at_raw.replace("Z", "+00:00")
                        )
                    except Exception:
                        created_at = datetime.now(timezone.utc)
                else:
                    created_at = datetime.now(timezone.utc)
                    
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                try:
                    # Extract document information
                    title = doc.get("title") or "Untitled Document"
                    author = doc.get("author", "")
                    category = doc.get("category", "article")
                    summary = doc.get("summary", "")
                    url = doc.get("url", "")
                    word_count = doc.get("word_count")
                    reading_progress = doc.get("reading_progress")
                    
                    # Handle tags - Reader API returns dict instead of list
                    tags_raw = doc.get("tags", [])
                    tags = []
                    if isinstance(tags_raw, list):
                        tags = tags_raw
                    elif isinstance(tags_raw, dict):
                        # Extract tag names from dict if available
                        tags = list(tags_raw.keys()) if tags_raw else []
                    
                    # Clean and validate URL
                    clean_url = None
                    if url and isinstance(url, str) and url.strip():
                        clean_url = url.strip()
                        # Ensure it's a valid URL format
                        if not clean_url.startswith(('http://', 'https://')):
                            clean_url = None
                    
                    # Create content from summary or metadata
                    content_parts = []
                    if summary:
                        content_parts.append(summary)
                    if author:
                        content_parts.append(f"Author: {author}")
                    if word_count is not None and word_count > 0:
                        content_parts.append(f"~{word_count} words")
                    if reading_progress is not None and reading_progress > 0:
                        progress_pct = min(100, int(reading_progress * 100))
                        content_parts.append(f"{progress_pct}% read")
                        
                    content = " • ".join(content_parts) if content_parts else "Recent document from Reader"
                    
                    # Clean up title and author for better presentation
                    clean_title = title.strip() if title else "Untitled Document"
                    if not clean_title:
                        clean_title = f"Document from {category}"

                    item = ContentItem(
                        id=f"readwise_reader_{doc['id']}",
                        title=clean_title,
                        content=content,
                        source="readwise_reader",
                        url=clean_url,
                        author=author if author else None,
                        source_title="Readwise Reader",
                        tags=tags,
                        created_at=created_at,
                        metadata={
                            "category": category,
                            "location": doc.get("location", ""),
                            "word_count": word_count,
                            "reading_progress": reading_progress,
                            "reader_doc_id": doc.get("id")
                        },
                    )
                    content_items.append(item)
                except Exception as item_err:
                    logger.error(
                        "Failed to create ContentItem for Reader document %s: %s",
                        doc.get("id"),
                        item_err,
                    )
                    continue

            logger.info(f"Retrieved {len(content_items)} recent documents from Readwise Reader")
            return content_items

        except Exception as e:
            logger.error(f"Error getting Readwise Reader content: {e}")
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
        """Process and enrich content items with diverse selection.

        Args:
            content_items: Raw content items

        Returns:
            Processed content items (max 20, balanced across categories)
        """
        # First, categorize all items to ensure diversity
        categorized_items = {
            "technology": [],
            "society": [],
            "art": [],
            "business": [],
        }
        
        for item in content_items:
            category = await self._categorize_content(item)
            categorized_items[category].append(item)
        
        # Sort each category by date (newest first)
        for category in categorized_items:
            categorized_items[category] = sorted(
                categorized_items[category], 
                key=lambda x: x.created_at or "", 
                reverse=True
            )
        
        # Balance categories to meet template requirements
        self._balance_categories(categorized_items)
        
        # Select items from balanced categories (max 20 total)
        final_items = []
        for category, items in categorized_items.items():
            final_items.extend(items)
        
        # Sort final selection by date and limit to 20
        final_items = sorted(final_items, key=lambda x: x.created_at or "", reverse=True)
        return final_items[:20]
    
    async def _enhance_content_quality(self, content_items: List[ContentItem]) -> List[ContentItem]:
        """Enhance content quality by improving titles, sources, and filtering with AI when available."""
        enhanced_items = []
        
        for item in content_items:
            # Extract better title from content if current title is generic
            enhanced_title = self._extract_better_title(item)
            
            # Improve source attribution
            enhanced_source = self._improve_source_attribution(item)
            
            # Enhance content summary with AI if available
            enhanced_content = item.content
            if self.openrouter_client and len(item.content) > 200:
                try:
                    enhanced_content = await self.openrouter_client.enhance_content_summary(
                        enhanced_title, item.content, max_length=150
                    )
                except Exception as e:
                    logger.debug(f"AI content enhancement failed: {e}")
                    enhanced_content = item.content
            
            # Create enhanced item
            enhanced_item = ContentItem(
                id=item.id,
                title=enhanced_title,
                content=enhanced_content,
                source=item.source,
                url=item.url,
                author=item.author or enhanced_source.get('author', ''),
                source_title=enhanced_source.get('source_title', item.source_title),
                tags=item.tags,
                created_at=item.created_at,
                metadata=item.metadata
            )
            
            # Only include items with sufficient quality
            if self._meets_quality_standards(enhanced_item):
                enhanced_items.append(enhanced_item)
            else:
                logger.debug(f"Filtered out low-quality item: {enhanced_title[:50]}...")
        
        logger.info(f"Enhanced and filtered content: {len(enhanced_items)}/{len(content_items)} items passed quality check")
        return enhanced_items
    
    def _extract_better_title(self, item: ContentItem) -> str:
        """Extract a better title from content if the current one is generic."""
        import re
        current_title = item.title.strip()
        
        # Skip if title is already meaningful
        if self._is_meaningful_title(current_title):
            return current_title
            
        # Try to extract better title from content
        if not item.content or len(item.content) < 30:
            return current_title
            
        # Look for potential titles in content
        better_title = self._find_title_in_content(item.content)
        if better_title:
            logger.debug(f"Improved title: '{current_title}' -> '{better_title}'")
            return better_title
            
        return current_title

    def _is_meaningful_title(self, title: str) -> bool:
        """Check if a title is meaningful and specific."""
        if len(title) < 10:
            return False
            
        # Generic patterns that indicate a poor title
        import re
        generic_patterns = [
            r'.*featured article.*',
            r'untitled.*',
            r'^(article|post|highlight|note)\s*\d*$',
            r'^\w+\s+\d+\s*$',  # Date-based titles
            r'^(the|a|an)\s+\w+\s+\d+$'  # "The January 5" type titles
        ]
        
        return not any(re.match(pattern, title.lower()) for pattern in generic_patterns)
        
    def _find_title_in_content(self, content: str) -> str:
        """Find a good title within content text."""
        import re
        
        # Try different strategies to find a good title
        strategies = [
            self._extract_from_sentences,
            self._extract_from_first_line,
            self._extract_from_capitalized_phrases
        ]
        
        for strategy in strategies:
            title = strategy(content)
            if title and self._is_good_extracted_title(title):
                return title[:80]  # Limit length
                
        return ""
        
    def _extract_from_sentences(self, content: str) -> str:
        """Extract title from well-formed sentences."""
        import re
        sentences = re.split(r'[.!?]\s+', content[:500])
        
        for sentence in sentences[:3]:
            sentence = sentence.strip()
            if 15 <= len(sentence) <= 100 and self._looks_like_title(sentence):
                return sentence
        return ""
        
    def _extract_from_first_line(self, content: str) -> str:
        """Extract title from first content line."""
        lines = content.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            if 10 <= len(first_line) <= 100 and self._looks_like_title(first_line):
                return first_line
        return ""
        
    def _extract_from_capitalized_phrases(self, content: str) -> str:
        """Extract title from capitalized phrases."""
        import re
        # Look for phrases that start with capital and have good length
        words = content.split()[:15]
        if len(words) >= 4:
            phrase = ' '.join(words)
            if phrase and phrase[0].isupper():
                return phrase + "..."
        return ""
        
    def _looks_like_title(self, text: str) -> bool:
        """Check if text looks like it could be a good title."""
        import re
        return (
            text[0].isupper() and
            not text.lower().startswith(('this', 'that', 'it', 'in', 'on', 'at', 'the', 'a', 'an')) and
            not text.endswith((':')) and
            not re.match(r'^https?://', text.lower()) and
            len([c for c in text if c.isupper()]) >= 2  # Has some capitalization
        )
        
    def _is_good_extracted_title(self, title: str) -> bool:
        """Final check if extracted title is good quality."""
        return (
            10 <= len(title) <= 100 and
            title.strip() and
            not title.lower().startswith('http') and
            sum(1 for c in title if c.isalnum()) >= 5  # Has meaningful content
        )
    
    def _improve_source_attribution(self, item: ContentItem) -> dict:
        """Improve source attribution to avoid 'Unknown' sources."""
        import re
        from urllib.parse import urlparse
        
        result = {
            'source_title': item.source_title,
            'author': item.author
        }
        
        # If source_title is generic, missing, or uninformative, improve it
        needs_improvement = (
            not item.source_title or 
            item.source_title in ['Unknown', 'Unknown Source'] or
            'featured articles' in item.source_title.lower() or
            'untitled' in item.source_title.lower() or
            len(item.source_title.strip()) < 3
        )
        
        if needs_improvement and item.url:
            improved_source = self._extract_source_from_url(item.url)
            if improved_source:
                result['source_title'] = improved_source
                logger.debug(f"Improved source: '{item.source_title}' -> '{improved_source}'")
        
        # Try to improve author if missing
        if not result['author'] and item.url:
            # Some URLs contain author info that we could extract
            # This is a placeholder for future enhancement
            pass
        
        return result
        
    def _extract_source_from_url(self, url: str) -> str:
        """Extract a meaningful source name from URL."""
        import re
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            if not domain:
                return ""
            
            # Remove common prefixes and suffixes
            domain = re.sub(r'^(www\.|m\.|mobile\.)', '', domain)
            domain = re.sub(r'\.(com|org|net|edu|gov|io|co\.uk)$', '', domain)
            
            # Handle special cases for common domains
            domain_mapping = {
                'wikipedia': 'Wikipedia',
                'reddit': 'Reddit',
                'github': 'GitHub',
                'stackoverflow': 'Stack Overflow',
                'medium': 'Medium',
                'substack': 'Substack',
                'youtube': 'YouTube',
                'youtu': 'YouTube',
                'twitter': 'Twitter/X',
                'x': 'Twitter/X'
            }
            
            # Check for known mappings first
            for key, value in domain_mapping.items():
                if key in domain:
                    return value
            
            # For other domains, clean up and capitalize
            # Take the main domain part before first dot
            main_domain = domain.split('.')[0]
            
            if main_domain and len(main_domain) > 2:
                # Convert to readable format
                # Handle camelCase or underscore-separated names
                readable_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', main_domain)
                readable_name = readable_name.replace('_', ' ').replace('-', ' ')
                return readable_name.title()
                
        except Exception:
            return ""
        
        return ""
    
    def _meets_quality_standards(self, item: ContentItem) -> bool:
        """Check if content item meets minimum quality standards."""
        # Minimum content length
        if not item.content or len(item.content.strip()) < 50:
            return False
        
        # Must have a meaningful title
        if not item.title or len(item.title.strip()) < 10:
            return False
        
        # Must have either URL or source info
        if not item.url and not item.source_title:
            return False
        
        return True

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
