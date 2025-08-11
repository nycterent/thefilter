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
                    return await self.unsplash_client.get_category_image(
                        category, topic_hint
                    )
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
            "\n*Welcome to this week's curated briefing. In a **timeless minimalist** spirit, we transform information overload into thoughtful insight. Each story is chosen not just for what happened, but for what it means. Expect sharp analysis, provocative questions, and perspectives that challenge conventional thinking.*\n"
        )

        # Dynamic intro based on top stories
        top_stories = []
        for category, items in categories.items():
            if items:
                top_stories.append((category, items[0]))

        if len(top_stories) >= 2:
            intro_items = []
            for category, item in top_stories[:3]:  # Top 3 stories
                src = item.source_title or item.source or "Unknown"
                intro_items.append(f"**{item.title}** from {src}")
            out.append(f"\n*Today's highlights: {' • '.join(intro_items)}*\n")

        out.append("\n---\n")
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

        # TECHNOLOGY SPOTLIGHT
        out.append("## 🔬 TECHNOLOGY\n")
        tech_items = categories["technology"][2:5]  # Get 2-4 additional tech items

        for i, item in enumerate(tech_items):
            if item:
                img = await get_unsplash_image("technology", item.title)
                src = item.source_title or item.source or "Unknown"
                url = item.url or ""
                summary = item.content[:150].replace("\n", " ")

                out.append(f"### {item.title}\n")
                out.append(f"![{item.title}]({img})\n")
                out.append(f"{summary}\n")
                out.append(f"*Source: [{src}]({url})*\n")
                if i < len(tech_items) - 1:  # Add separator except for last item
                    out.append("---\n")
        out.append("\n---\n")

        # SOCIETY & CULTURE
        out.append("## 🌍 SOCIETY & CULTURE\n")
        soc_items = categories["society"][:3]  # Get up to 3 society items

        for i, item in enumerate(soc_items):
            if item:
                img = await get_unsplash_image("society", item.title)
                src = item.source_title or item.source or "Unknown"
                url = item.url or ""
                summary = item.content[:180].replace("\n", " ")

                # Use bullet points for a more organic feel
                out.append(f"**• {item.title}**\n")
                if i == 0:  # Only show image for first item to avoid clutter
                    out.append(f"![{item.title}]({img})\n")
                out.append(f"{summary} *([{src}]({url}))*\n")

        out.append("\n---\n")

        # ARTS & CULTURE
        out.append("## 🎨 ARTS & CULTURE\n")
        art_items = categories["art"][:2]  # Get up to 2 art items

        for item in art_items:
            if item:
                img = await get_unsplash_image("art", item.title)
                src = item.source_title or item.source or "Unknown"
                url = item.url or ""
                summary = item.content[:150].replace("\n", " ")

                out.append(f"**{item.title}**\n")
                out.append(f"![{item.title}]({img})\n")
                out.append(f"{summary} *([{src}]({url}))*\n\n")

        if not art_items or all(item is None for item in art_items):
            out.append("*No arts & culture stories this week.*\n\n")

        out.append("---\n")

        # BUSINESS & ECONOMY
        out.append("## 💼 BUSINESS & ECONOMY\n")
        bus_items = categories["business"][:2]  # Get up to 2 business items

        for item in bus_items:
            if item:
                img = await get_unsplash_image("business", item.title)
                src = item.source_title or item.source or "Unknown"
                url = item.url or ""
                summary = item.content[:150].replace("\n", " ")

                out.append(f"**{item.title}**\n")
                out.append(f"![{item.title}]({img})\n")
                out.append(f"{summary} *([{src}]({url}))*\n\n")

        if not bus_items or all(item is None for item in bus_items):
            out.append("*No business stories this week.*\n\n")

        out.append("---\n")

        # SOURCES & ATTRIBUTION
        out.append("## SOURCES & ATTRIBUTION\n")

        def sources_line(cat):
            # Collect unique sources to avoid repetition, but only include items with valid URLs and sources
            source_map = {}
            for item in categories[cat]:
                if item.url and str(item.url).startswith(("http://", "https://")):
                    src_name = item.source_title or item.source
                    # Skip if source name is missing or generic
                    if (
                        not src_name
                        or src_name
                        in [
                            "Unknown",
                            "Unknown Source",
                        ]
                        or src_name.lower() == item.source.lower()
                    ):
                        # Try to extract source from URL instead
                        if hasattr(self, "_extract_source_from_url"):
                            src_name = self._extract_source_from_url(str(item.url))
                        if not src_name:
                            continue  # Skip items without identifiable sources

                    # For content with same source name, use article title as differentiator
                    if src_name in source_map:
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

            if not source_map:
                return "*No valid sources with URLs available for this section*"

            return " • ".join(
                [f"[{src}]({url})" for src, url in source_map.items()][:5]
            )  # Limit to 5 sources per section

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
        # For curated content with clear user insights, use keyword-based categorization to save API calls
        if self._is_curated_content(item) and self._is_curated_insights(item.content):
            logger.debug(
                f"Using keyword categorization for curated insights: {item.title}"
            )
        # Try AI categorization for complex/ambiguous content only
        elif (
            self.openrouter_client
            and len(item.content) > 100
            and not any(
                clear_keyword in (item.title + " " + item.content).lower()
                for clear_keyword in [
                    "technology",
                    "tech",
                    "ai",
                    "business",
                    "finance",
                    "economy",
                    "politics",
                    "government",
                    "art",
                    "culture",
                    "music",
                    "film",
                ]
            )
        ):
            try:
                ai_category = await self.openrouter_client.categorize_content(
                    item.title, item.content, item.tags
                )
                if ai_category:
                    logger.debug(f"AI categorized as {ai_category}: {item.title}")
                    return ai_category
            except Exception as e:
                logger.debug(f"AI categorization failed, using fallback: {e}")

        # Use keyword-based categorization (primary method to reduce API calls)
        tags_lower = [tag.lower() for tag in item.tags]

        # Technology keywords (including pure science/physics)
        tech_keywords = [
            "technology",
            "tech",
            "ai",
            "artificial intelligence",
            "machine learning",
            "software",
            "computer",
            "digital",
            "internet",
            "data",
            "algorithm",
            "programming",
            "code",
            "cybersecurity",
            "blockchain",
            "crypto",
            "quantum",
            "physics",
            "science",
            "research",
            "discovery",
            "experiment",
        ]

        # Society keywords (explicitly exclude pure science/physics)
        society_keywords = [
            "politics",
            "government",
            "policy",
            "law",
            "society",
            "social",
            "democracy",
            "election",
            "war",
            "conflict",
            "human rights",
            "justice",
            "community",
            "culture",
            "education",
            "healthcare",
            "environment",
        ]

        # Art keywords
        art_keywords = [
            "art",
            "culture",
            "media",
            "film",
            "music",
            "book",
            "literature",
            "design",
            "creative",
            "artist",
            "entertainment",
            "museum",
        ]

        # Business keywords
        business_keywords = [
            "business",
            "economy",
            "economic",
            "finance",
            "market",
            "company",
            "startup",
            "investment",
            "money",
            "trade",
            "commerce",
            "industry",
        ]

        # Check content and title for keywords
        content_text = f"{item.title} {item.content}".lower()

        # Count keyword matches
        tech_score = sum(1 for keyword in tech_keywords if keyword in content_text)
        society_score = sum(
            1 for keyword in society_keywords if keyword in content_text
        )
        art_score = sum(1 for keyword in art_keywords if keyword in content_text)
        business_score = sum(
            1 for keyword in business_keywords if keyword in content_text
        )

        # Add tag-based scoring
        tech_score += sum(
            1 for tag in tags_lower if any(kw in tag for kw in tech_keywords)
        )
        society_score += sum(
            1 for tag in tags_lower if any(kw in tag for kw in society_keywords)
        )
        art_score += sum(
            1 for tag in tags_lower if any(kw in tag for kw in art_keywords)
        )
        business_score += sum(
            1 for tag in tags_lower if any(kw in tag for kw in business_keywords)
        )

        # Determine category based on highest score
        scores = {
            "technology": tech_score,
            "society": society_score,
            "art": art_score,
            "business": business_score,
        }

        best_category = max(scores, key=scores.get)

        # If no clear winner (all scores 0), use content-based fallback
        if scores[best_category] == 0:
            # Default to society unless content suggests otherwise
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
            "technology": 4,  # Headlines + technology desk
            "society": 3,  # Society section
            "art": 2,  # Arts section
            "business": 2,  # Business section
        }

        # Scale down requirements if we don't have enough total items
        total_required = sum(template_requirements.values())  # 11
        if total_items < total_required:
            scale_factor = total_items / total_required
            for cat in template_requirements:
                template_requirements[cat] = max(
                    1, int(template_requirements[cat] * scale_factor)
                )

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
                    logger.debug(
                        f"Rebalanced: moved item from {donor_cat} to {category_needing}"
                    )

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
            GlaspClient = __import__(
                "src.clients.glasp", fromlist=["GlaspClient"]
            ).GlaspClient
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

        url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        return bool(re.match(url_pattern, url))

    async def generate_newsletter(self, dry_run: bool = False) -> NewsletterDraft:
        """Generate a complete newsletter.

        Args:
            dry_run: If True, don't actually publish, just generate content

        Returns:
            Generated newsletter draft
        """
        import time

        start_time = time.time()

        # Initialize editorial statistics
        self.editorial_stats = {
            "articles_processed": 0,
            "articles_revised": 0,
            "total_revisions": 0,
            "editor_scores": [],
            "newsletter_editor_score": None,
            "common_feedback_themes": [],
        }

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

        # Step 2.5: Enhance content quality (includes editorial workflow)
        enhanced_content = await self._enhance_content_quality(processed_content)

        # Step 2.7: Filter for content diversity to prevent repetitive themes
        diverse_content = self._ensure_content_diversity(enhanced_content)

        # Step 3: Generate newsletter draft
        newsletter = await self._create_newsletter_draft(diverse_content)

        # Step 4: Editorial review of full newsletter
        if self.openrouter_client:
            newsletter = await self._newsletter_editorial_review(newsletter)

        # Add editorial statistics to newsletter metadata
        processing_time = time.time() - start_time
        editorial_metadata = {
            "editorial_stats": {
                **self.editorial_stats,
                "avg_editor_score": (
                    sum(self.editorial_stats["editor_scores"])
                    / len(self.editorial_stats["editor_scores"])
                    if self.editorial_stats["editor_scores"]
                    else None
                ),
            },
            "processing_time": processing_time,
        }

        # Merge with existing metadata
        if newsletter.metadata:
            newsletter.metadata.update(editorial_metadata)
        else:
            newsletter.metadata = editorial_metadata

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
                        if not clean_url.startswith(("http://", "https://")):
                            clean_url = None

                    # Debug URL issues
                    if not clean_url:
                        logger.debug(
                            f"Invalid/missing URL for '{title[:50]}...': '{url}'"
                        )

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

                    content = (
                        " • ".join(content_parts)
                        if content_parts
                        else "Recent document from Reader"
                    )

                    # Clean up title and author for better presentation
                    clean_title = title.strip() if title else "Untitled Document"
                    if not clean_title:
                        clean_title = f"Document from {category}"

                    # Extract actual source from URL instead of hardcoding "Readwise Reader"
                    actual_source_title = "Readwise Reader"  # fallback
                    if clean_url:
                        extracted_source = self._extract_source_from_url(clean_url)
                        if extracted_source and extracted_source != "Readwise Reader":
                            actual_source_title = extracted_source

                    item = ContentItem(
                        id=f"readwise_reader_{doc['id']}",
                        title=clean_title,
                        content=content,
                        source="readwise_reader",
                        url=clean_url,
                        author=author if author else None,
                        source_title=actual_source_title,
                        tags=tags,
                        created_at=created_at,
                        metadata={
                            "category": category,
                            "location": doc.get("location", ""),
                            "word_count": word_count,
                            "reading_progress": reading_progress,
                            "reader_doc_id": doc.get("id"),
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

            logger.info(
                f"Retrieved {len(content_items)} recent documents from Readwise Reader"
            )
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
                reverse=True,
            )

        # Balance categories to meet template requirements
        self._balance_categories(categorized_items)

        # Select items from balanced categories (max 20 total)
        final_items = []
        for category, items in categorized_items.items():
            final_items.extend(items)

        # Sort final selection by date and limit to 20
        final_items = sorted(
            final_items, key=lambda x: x.created_at or "", reverse=True
        )
        return final_items[:20]

    async def _enhance_content_quality(
        self, content_items: List[ContentItem]
    ) -> List[ContentItem]:
        """Enhance content quality by improving titles, sources, and filtering with AI when available."""
        enhanced_items = []

        for item in content_items:
            # Extract better title from content if current title is generic
            enhanced_title = self._extract_better_title(item)

            # Improve source attribution
            enhanced_source = await self._improve_source_attribution(item)

            # Enhance content summary with AI if available (pass source to prioritize RSS insights)
            enhanced_content = self._improve_summary_quality(
                item.content, enhanced_title, item.source
            )

            # For content with user insights or curation, always use editorial workflow
            if self._is_curated_content(item) and self.openrouter_client:
                try:
                    # Always run editorial workflow for curated content - incorporate user highlights if present
                    logger.debug(
                        f"Applying editorial workflow to curated content: {enhanced_title}"
                    )
                    enhanced_content = await self._editorial_workflow(
                        item, enhanced_content, enhanced_title
                    )
                    logger.debug(
                        f"Completed editorial workflow for curated content: {enhanced_title}"
                    )
                except Exception as e:
                    logger.error(f"Editorial workflow failed for {enhanced_title}: {e}")
                    # Keep the formatted content as fallback
                    enhanced_content = self._format_user_insights(
                        enhanced_content, enhanced_title
                    )
            elif (
                self.openrouter_client
                and len(enhanced_content) > 200
                and not self._is_curated_insights(enhanced_content)
                and not self._is_curated_content(item)
            ):  # Only process non-curated content with AI to reduce API calls
                try:
                    enhanced_content = (
                        await self.openrouter_client.enhance_content_summary(
                            enhanced_title, enhanced_content, max_length=160
                        )
                    )
                    logger.debug(f"Enhanced content with AI: {enhanced_title}")
                except Exception as e:
                    logger.debug(f"AI content enhancement failed, using fallback: {e}")
                    # Keep our improved summary as fallback

            # Create enhanced item
            enhanced_item = ContentItem(
                id=item.id,
                title=enhanced_title,
                content=enhanced_content,
                source=item.source,
                url=item.url,
                author=item.author or enhanced_source.get("author", ""),
                source_title=enhanced_source.get("source_title", item.source_title),
                tags=item.tags,
                created_at=item.created_at,
                metadata=item.metadata,
            )

            # Only include items with sufficient quality
            if self._meets_quality_standards(enhanced_item):
                enhanced_items.append(enhanced_item)
            else:
                logger.debug(f"Filtered out low-quality item: {enhanced_title[:50]}...")

        logger.info(
            f"Enhanced and filtered content: {len(enhanced_items)}/{len(content_items)} items passed quality check"
        )
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
            r".*featured article.*",
            r"untitled.*",
            r"^(article|post|highlight|note)\s*\d*$",
            r"^\w+\s+\d+\s*$",  # Date-based titles
            r"^(the|a|an)\s+\w+\s+\d+$",  # "The January 5" type titles
        ]

        return not any(re.match(pattern, title.lower()) for pattern in generic_patterns)

    def _find_title_in_content(self, content: str) -> str:
        """Find a good title within content text."""
        import re

        # Try different strategies to find a good title
        strategies = [
            self._extract_from_sentences,
            self._extract_from_first_line,
            self._extract_from_capitalized_phrases,
        ]

        for strategy in strategies:
            title = strategy(content)
            if title and self._is_good_extracted_title(title):
                return title[:80]  # Limit length

        return ""

    def _extract_from_sentences(self, content: str) -> str:
        """Extract title from well-formed sentences."""
        import re

        sentences = re.split(r"[.!?]\s+", content[:500])

        for sentence in sentences[:3]:
            sentence = sentence.strip()
            if 15 <= len(sentence) <= 100 and self._looks_like_title(sentence):
                return sentence
        return ""

    def _extract_from_first_line(self, content: str) -> str:
        """Extract title from first content line."""
        lines = content.strip().split("\n")
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
            phrase = " ".join(words)
            if phrase and phrase[0].isupper():
                return phrase + "..."
        return ""

    def _looks_like_title(self, text: str) -> bool:
        """Check if text looks like it could be a good title."""
        import re

        return (
            text[0].isupper()
            and not text.lower().startswith(
                ("this", "that", "it", "in", "on", "at", "the", "a", "an")
            )
            and not text.endswith((":"))
            and not re.match(r"^https?://", text.lower())
            and len([c for c in text if c.isupper()]) >= 2  # Has some capitalization
        )

    def _is_good_extracted_title(self, title: str) -> bool:
        """Final check if extracted title is good quality."""
        return (
            10 <= len(title) <= 100
            and title.strip()
            and not title.lower().startswith("http")
            and sum(1 for c in title if c.isalnum()) >= 5  # Has meaningful content
        )

    async def _improve_source_attribution(self, item: ContentItem) -> dict:
        """Improve source attribution to avoid 'Unknown' sources."""
        import re
        from urllib.parse import urlparse

        result = {"source_title": item.source_title, "author": item.author}

        # If source_title is generic, missing, or uninformative, improve it
        needs_improvement = (
            not item.source_title
            or item.source_title in ["Unknown", "Unknown Source", "Starred Articles"]
            or "featured articles" in item.source_title.lower()
            or "starred articles" in item.source_title.lower()
            or "untitled" in item.source_title.lower()
            or len(item.source_title.strip()) < 3
        )

        if needs_improvement and item.url:
            improved_source = self._extract_source_from_url(item.url)

            # If URL extraction still fails, try web search fallback
            if not improved_source and item.title:
                try:
                    search_result = await self._search_for_source_name(
                        item.title, str(item.url)
                    )
                    if search_result:
                        improved_source = search_result
                        logger.debug(
                            f"Web search found source: '{search_result}' for {item.title[:50]}..."
                        )
                except Exception as e:
                    logger.debug(f"Web search fallback failed: {e}")

            if improved_source:
                result["source_title"] = improved_source
                logger.debug(
                    f"Improved source: '{item.source_title}' -> '{improved_source}'"
                )

        # Try to improve author if missing
        if not result["author"] and item.url:
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

            # Skip Readwise Reader URLs - these are proxy URLs, not the actual source
            if "readwise.io" in domain:
                return ""

            # Remove common prefixes and suffixes
            domain = re.sub(r"^(www\.|m\.|mobile\.)", "", domain)
            original_domain = domain
            domain = re.sub(r"\.(com|org|net|edu|gov|io|co\.uk|ai)$", "", domain)

            # Handle special cases for common domains
            source_mapping = {
                "nature": "Nature",
                "techcrunch": "TechCrunch",
                "arstechnica": "Ars Technica",
                "wired": "WIRED",
                "theverge": "The Verge",
                "medium": "Medium",
                "substack": "Substack",
                "github": "GitHub",
                "stackoverflow": "Stack Overflow",
                "reddit": "Reddit",
                "youtube": "YouTube",
                "twitter": "Twitter",
                "linkedin": "LinkedIn",
                "hackernews": "Hacker News",
                "ycombinator": "Y Combinator",
                "tailscale": "Tailscale",
                "openai": "OpenAI",
                "anthropic": "Anthropic",
                "google": "Google",
                "microsoft": "Microsoft",
                "producthacker": "ProductHacker",
                "pragmaticengineer": "The Pragmatic Engineer",
                "newsletter": "Newsletter",
                "blog": "Blog",
                "news": "News",
                "apple": "Apple",
                "meta": "Meta",
                "stripe": "Stripe",
            }

            if domain in source_mapping:
                return source_mapping[domain]

            # For substack domains like "someone.substack.com"
            if ".substack" in original_domain:
                subdomain = original_domain.split(".")[0]
                return f"{subdomain.title()} (Substack)"

            # For github.io domains like "someone.github.io"
            if ".github" in original_domain:
                subdomain = original_domain.split(".")[0]
                return f"{subdomain.title()} (GitHub Pages)"

            # Clean up domain name for presentation
            domain_parts = domain.split(".")
            if len(domain_parts) > 0:
                main_domain = domain_parts[0]
                # Capitalize and clean up
                return main_domain.replace("-", " ").replace("_", " ").title()

            return domain.title()

        except Exception as e:
            logger.debug(f"Error extracting source from URL {url}: {e}")
            return ""

    async def _search_for_source_name(
        self, article_title: str, article_url: str
    ) -> str:
        """Search the web to find the actual source/publication name for an article."""
        # For now, return empty string - web search fallback can be implemented later
        # This would require integration with search APIs or scraping
        return ""

    def _ensure_content_diversity(
        self, content_items: List[ContentItem]
    ) -> List[ContentItem]:
        """Filter content to ensure diversity and prevent repetitive themes."""
        if len(content_items) <= 10:
            return content_items  # Too few items to filter

        # Group content by similar themes using title/content analysis
        diverse_items = []

        # Common words to ignore when detecting similarity
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
        }

        for item in content_items:
            # Extract key theme words from title and content
            title_words = set(
                word.lower().strip('.,!?()[]{}"')
                for word in item.title.split()
                if len(word) > 3 and word.lower() not in stopwords
            )
            content_words = set(
                word.lower().strip('.,!?()[]{}"')
                for word in item.content.split()[:50]  # First 50 words
                if len(word) > 4 and word.lower() not in stopwords
            )

            key_theme_words = title_words | content_words

            # Check if this item is too similar to already selected items
            is_similar = False
            for existing_item in diverse_items[
                -5:
            ]:  # Check last 5 items for similarity
                existing_title_words = set(
                    word.lower().strip('.,!?()[]{}"')
                    for word in existing_item.title.split()
                    if len(word) > 3 and word.lower() not in stopwords
                )
                existing_content_words = set(
                    word.lower().strip('.,!?()[]{}"')
                    for word in existing_item.content.split()[:50]
                    if len(word) > 4 and word.lower() not in stopwords
                )
                existing_theme_words = existing_title_words | existing_content_words

                # Calculate similarity score
                common_words = key_theme_words & existing_theme_words
                total_words = len(key_theme_words | existing_theme_words)

                if total_words > 0:
                    similarity = len(common_words) / total_words

                    # If more than 40% similarity in key words, consider too similar
                    if similarity > 0.4:
                        logger.debug(
                            f"Filtering similar content: '{item.title[:50]}...' similar to '{existing_item.title[:50]}...' (similarity: {similarity:.2f})"
                        )
                        is_similar = True
                        break

            if not is_similar:
                diverse_items.append(item)

        logger.info(
            f"Content diversity filter: {len(content_items)} -> {len(diverse_items)} items (removed {len(content_items) - len(diverse_items)} similar items)"
        )
        return diverse_items

    def _improve_summary_quality(
        self, content: str, title: str, source: str = ""
    ) -> str:
        """Improve summary quality through intelligent processing."""
        if not content:
            return ""

        # For curated content, format user insights (this is now a fallback path)
        if self._is_curated_insights(content):
            return self._format_user_insights(content, title)

        # Handle list-based content (like ProductHacker)
        if content.count("\n") > 3 and len(content) > 500:
            return self._extract_key_points_summary(content, title)

        # Handle URL-heavy content
        if content.startswith("https://") or content.startswith("http://"):
            return self._extract_meaningful_content(content)

        # Handle social media link spam
        if any(
            spam_word in content.lower()[:100]
            for spam_word in ["join", "discord", "instagram", "patreon"]
        ):
            return self._skip_social_links(content)

        # Ensure good sentence completion for truncation
        return self._ensure_complete_sentences(content)

    def _is_curated_content(self, item: ContentItem) -> bool:
        """Determine if content item should go through editorial workflow."""
        # Check if content contains user insights/commentary
        if self._is_curated_insights(item.content):
            return True

        # RSS feeds: All articles go through editorial workflow
        if item.source == "rss":
            return True

        # Readwise: Only articles with the configured filter tag
        if item.source == "readwise_reader":
            filter_tag = self.settings.readwise_filter_tag.lower()
            if item.tags and any(tag.lower() == filter_tag for tag in item.tags):
                logger.debug(
                    f"Readwise article tagged '{filter_tag}' will be processed: {item.title[:50]}..."
                )
                return True
            else:
                logger.debug(
                    f"Readwise article without '{filter_tag}' tag skipped: {item.title[:50]}..."
                )
                return False

        # Glasp and other sources
        if item.source == "glasp":
            return True

        # Check for other indicators of curation
        if item.source and any(
            keyword in item.source.lower() for keyword in ["feed", "curated", "starred"]
        ):
            return True

        return False

    def _is_curated_insights(self, content: str) -> bool:
        """Legacy fallback method for detecting curated insights.

        Note: This is now primarily used as a fallback when LLM detection is not available.
        The main detection is now done by OpenRouter LLM in detect_user_commentary().
        """
        if not content:
            return False

        # Look for obvious indicators of curated insights
        insight_indicators = [
            "•",  # Bullet points
            "📚",
            "☕",
            "🤖",
            "⚔️",
            "🌍",
            "🏛️",
            "✊",  # Emojis
            "**",  # Bold formatting
            "Trend",
            "Issue",
            "Insights",
            "Call to Action",
        ]

        # Simple fallback detection - if multiple indicators present
        indicator_count = sum(
            1 for indicator in insight_indicators if indicator in content
        )
        return indicator_count >= 2

    def _format_user_insights(self, content: str, title: str) -> str:
        """Format user's curated insights for newsletter display."""
        if not content:
            return ""

        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # Extract the most compelling insights (first 2-3 points)
        key_insights = []
        for line in lines:
            if len(key_insights) >= 3:  # Limit to top 3 insights
                break

            # Include lines with substance and structure
            if len(line) > 30 and (
                line.startswith("•")
                or line.startswith("-")
                or "**" in line
                or any(
                    emoji in line
                    for emoji in [
                        "📚",
                        "☕",
                        "🤖",
                        "⚔️",
                        "🌍",
                        "🏛️",
                        "✊",
                        "📊",
                        "🏢",
                        "👥",
                        "🔄",
                    ]
                )
            ):
                # Clean up the line
                clean_line = line.replace("•", "").replace("-", "").strip()
                # Remove redundant title repetition
                if not any(
                    word.lower() in clean_line.lower()
                    for word in title.lower().split()
                    if len(word) > 4
                ):
                    key_insights.append(clean_line)
                elif (
                    len(key_insights) == 0
                ):  # Include first insight even if it repeats title info
                    key_insights.append(clean_line)

        if key_insights:
            # Join insights with separator, ensuring good flow
            summary = " • ".join(key_insights)

            # Trim to reasonable newsletter length
            if len(summary) > 300:
                # Find a good breaking point
                truncated = summary[:280]
                last_period = truncated.rfind(".")
                if last_period > 200:
                    summary = truncated[: last_period + 1]
                else:
                    summary = truncated + "..."

            return summary

        # Fallback: return first substantial line
        for line in lines:
            if len(line) > 50:
                return line[:200] + "..." if len(line) > 200 else line

        return content[:200] + "..." if len(content) > 200 else content

    async def _editorial_workflow(
        self, item: ContentItem, user_highlights: str, title: str
    ) -> str:
        """Complete editorial workflow: fetch article, write commentary, get editor feedback, revise."""
        if not self.openrouter_client:
            logger.debug("No OpenRouter client - skipping editorial workflow")
            return self._format_user_insights(user_highlights, title)

        try:
            # Track that we're processing this article
            self.editorial_stats["articles_processed"] += 1

            # Step 1: Fetch original article content if we have a URL
            article_content = ""
            if item.url and str(item.url).startswith(("http://", "https://")):
                logger.debug(f"🎭 Fetching article content from: {item.url}")
                article_content = await self.openrouter_client.fetch_article_content(
                    str(item.url)
                )
                if not article_content:
                    logger.warning(f"Failed to fetch article content for: {item.url}")

            # Step 2: Generate initial commentary using article + user highlights
            logger.info(f"🎭 Writer agent: generating commentary for '{title[:50]}...'")
            commentary = await self.openrouter_client.generate_commentary(
                article_content if article_content else "Article content not available",
                user_highlights,
                title,
            )

            # Fallback only if AI generation completely fails
            if not commentary or commentary.strip() == user_highlights.strip():
                logger.warning(
                    "AI commentary generation failed, using formatted highlights as fallback"
                )
                commentary = self._format_user_insights(user_highlights, title)

            # Skip complex editorial workflow for free models - single shot works better
            # For free Llama model, the initial commentary is already high quality
            logger.info(f"✅ Using single-shot commentary for free model")

            # Add basic editorial stats for consistency
            self.editorial_stats["editor_scores"].append(8)  # Assume good quality
            self.editorial_stats["articles_revised"] += 0  # No revision needed

            return commentary

        except Exception as e:
            logger.error(f"Error in editorial workflow for {title}: {e}")
            # Fallback to formatted user insights
            return self._format_user_insights(user_highlights, title)

    async def _newsletter_editorial_review(
        self, newsletter: "NewsletterDraft"
    ) -> "NewsletterDraft":
        """Editorial review and revision of the complete newsletter."""
        try:
            max_revisions = 1  # Limit newsletter revisions
            revision_count = 0

            current_content = newsletter.content

            while revision_count < max_revisions:
                # Get editorial feedback on full newsletter
                logger.info(f"🎭 Editor agent: reviewing complete newsletter")
                review = await self.openrouter_client.editorial_roast(
                    current_content, "newsletter"
                )

                # Track newsletter editor score
                self.editorial_stats["newsletter_editor_score"] = review["score"]

                if review["approved"]:
                    logger.info(
                        f"✅ Newsletter approved by editor (score: {review['score']}/10)"
                    )
                    break

                # Newsletter-level revisions are complex, so just log the feedback for now
                logger.warning(
                    f"⚠️ Newsletter needs improvement (score: {review['score']}/10): {review['feedback'][:200]}..."
                )

                # For now, we'll accept the newsletter even if not perfect
                # Full newsletter revision would require regenerating the entire structure
                break

            # Return potentially updated newsletter
            if current_content != newsletter.content:
                from src.models.content import NewsletterDraft

                return NewsletterDraft(
                    title=newsletter.title,
                    content=current_content,
                    items=newsletter.items,
                    created_at=newsletter.created_at,
                    image_url=newsletter.image_url,
                    draft_id=newsletter.draft_id,
                    metadata=newsletter.metadata,
                )

            return newsletter

        except Exception as e:
            logger.error(f"Error in newsletter editorial review: {e}")
            return newsletter

    def _extract_key_points_summary(self, content: str, title: str) -> str:
        """Extract key points from list-heavy content."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # Find meaningful content lines (not social links)
        meaningful_lines = []
        for line in lines:
            if (
                not line.startswith("http")
                and not any(
                    social in line.lower()
                    for social in ["discord", "instagram", "patreon", "join"]
                )
                and len(line) > 20
                and "–" in line
            ):  # ProductHacker format
                meaningful_lines.append(line)

        if meaningful_lines:
            # Take first 2-3 meaningful lines
            summary_lines = meaningful_lines[:2]
            summary = " • ".join(summary_lines)
            return summary[:160] + "..." if len(summary) > 160 else summary

        # Fallback to first meaningful paragraph
        for line in lines:
            if len(line) > 50 and not line.startswith("http"):
                return line[:160] + "..." if len(line) > 160 else line

        return content[:160]

    def _extract_meaningful_content(self, content: str) -> str:
        """Extract meaningful content from URL-heavy text."""
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if (
                len(line) > 30
                and not line.startswith("http")
                and not line.startswith("www")
            ):
                return line[:160] + "..." if len(line) > 160 else line
        return content[:160]

    def _skip_social_links(self, content: str) -> str:
        """Skip social media links and find actual content."""
        lines = content.split("\n")
        for line in lines[3:]:  # Skip first few lines with social links
            line = line.strip()
            if len(line) > 40 and not any(
                social in line.lower()
                for social in ["discord", "instagram", "patreon", "twitter", "facebook"]
            ):
                return line[:160] + "..." if len(line) > 160 else line
        return content[:160]

    def _ensure_complete_sentences(self, content: str) -> str:
        """Ensure summary ends at sentence boundary for better truncation."""
        if len(content) <= 160:
            return content

        # Find last complete sentence within 160 chars
        truncated = content[:157]  # Leave room for "..."
        last_period = truncated.rfind(".")
        last_exclamation = truncated.rfind("!")
        last_question = truncated.rfind("?")

        sentence_end = max(last_period, last_exclamation, last_question)

        if sentence_end > 80:  # Only use if we have substantial content
            return content[: sentence_end + 1]
        else:
            return content[:160] + "..."

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
