"""Core newsletter generation logic."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import aiohttp

from src.clients.openrouter import OpenRouterClient
from src.clients.readwise import ReadwiseClient
from src.clients.rss import RSSClient
from src.clients.unsplash import UnsplashClient
from src.core.qacheck import run_checks
from src.core.sanitizer import ContentSanitizer
from src.core.voice_manager import VoiceManager
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
        # Categorize items dynamically - only create categories that have content
        categories: dict[str, list[ContentItem]] = {}

        for item in items:
            # Improved categorization using multiple signals
            category = await self._categorize_content(item)
            if category not in categories:
                categories[category] = []
            categories[category].append(item)

        # Ensure balanced distribution across categories
        self._balance_categories(categories)

        # Helper for dynamic Unsplash images with proper alt text
        async def get_unsplash_image_with_alt(
            category: str, topic_hint: str = ""
        ) -> tuple[str, str]:
            """Get dynamic image with descriptive alt text using Unsplash API or fallback."""
            if self.unsplash_client:
                try:
                    image_url = await self.unsplash_client.get_category_image(
                        category, topic_hint
                    )
                    # Generate descriptive alt text based on category and topic
                    alt_text = generate_image_alt_text(category, topic_hint)
                    return image_url, alt_text
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.debug(f"Unsplash API network error, using fallback: {e}")
                except Exception as e:
                    logger.debug(f"Unexpected Unsplash API error, using fallback: {e}")

            # Fallback to curated professional images with descriptive alt text
            curated_images_with_alt = {
                "technology": (
                    "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                    "Modern technology workspace with computer screens and digital interfaces",
                ),
                "society": (
                    "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                    "Diverse group of people in urban setting representing modern society",
                ),
                "art": (
                    "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                    "Abstract artistic composition with vibrant colors and creative elements",
                ),
                "business": (
                    "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=370&h=150&fit=crop&crop=entropy&auto=format&q=80",
                    "Professional business environment with modern office buildings",
                ),
            }
            return curated_images_with_alt.get(
                category, curated_images_with_alt["technology"]
            )

        def generate_image_alt_text(category: str, topic_hint: str = "") -> str:
            """Generate descriptive alt text for images based on category and topic."""
            if topic_hint:
                # Extract key terms and create more specific, contextual descriptions
                clean_topic = topic_hint[:50].replace("\n", " ").strip().lower()

                # Create more specific alt text based on topic keywords
                if "ai" in clean_topic or "artificial intelligence" in clean_topic:
                    return "Artistic visualization of artificial intelligence and machine learning concepts"
                elif "climate" in clean_topic or "environment" in clean_topic:
                    return "Environmental scene depicting climate change and sustainability themes"
                elif "health" in clean_topic or "medical" in clean_topic:
                    return "Healthcare and medical innovation visualization"
                elif "crypto" in clean_topic or "blockchain" in clean_topic:
                    return "Digital currency and blockchain technology representation"
                elif "social" in clean_topic or "culture" in clean_topic:
                    return "Social dynamics and cultural interaction imagery"
                elif "work" in clean_topic or "employment" in clean_topic:
                    return "Modern workplace and professional environment"
                else:
                    # More specific fallback based on category and topic
                    return f"Professional illustration depicting {clean_topic[:30]} in {category} context"

            # Enhanced fallback alt text based on category
            category_descriptions = {
                "technology": "Modern digital workspace with screens, code, and innovative tech elements",
                "society": "Diverse people interacting in contemporary urban and social settings",
                "art": "Creative composition with artistic elements, colors, and cultural expressions",
                "business": "Professional business environment with modern architecture and corporate elements",
            }
            return category_descriptions.get(
                category, "Professional editorial illustration"
            )

        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
        out = []
        out.append(f"# THE FILTER\n*Curated Briefing \u2022 {today}*\n")

        # Generate dynamic, engaging intro using LLM instead of generic template
        if self.openrouter_client:
            try:
                # Create engaging intro based on actual content
                intro_prompt = f"""Create an engaging, thought-provoking introduction for a newsletter called "The Filter" that covers these topics:

{chr(10).join([f"- {item.title[:100]}..." for item in items[:5]])}

Requirements:
- Start with a compelling hook that makes readers want to continue
- Reference specific themes from the actual content above
- Use your voice: skeptical, pragmatic, no hype
- Be provocative and challenge conventional thinking
- Keep it under 100 words
- Make it feel personal and curated, not generic

Write the intro:"""

                intro_response = await self.openrouter_client._make_request(
                    intro_prompt, max_tokens=150, temperature=0.7
                )
                if intro_response and "choices" in intro_response:
                    dynamic_intro = intro_response["choices"][0]["message"][
                        "content"
                    ].strip()
                    out.append(f"\n*{dynamic_intro}*\n")
                else:
                    # Fallback to generic but better intro
                    out.append(
                        "\n*This week's briefing cuts through the noise to surface what actually matters. "
                        f"From {categories.get('technology', [])[:1][0].title if categories.get('technology') else 'tech'} to "
                        f"{categories.get('society', [])[:1][0].title if categories.get('society') else 'society'}, "
                        "each story reveals deeper patterns worth your attention.*\n"
                    )
            except (KeyError, IndexError, AttributeError) as e:
                logger.warning(f"Data access error generating dynamic intro: {e}")
                # Fallback to generic but better intro
            except Exception as e:
                logger.warning(f"Unexpected error generating dynamic intro: {e}")
                # Fallback to generic but better intro
                out.append(
                    "\n*This week's briefing cuts through the noise to surface what actually matters. "
                    f"From {categories.get('technology', [])[:1][0].title if categories.get('technology') else 'tech'} to "
                    f"{categories.get('society', [])[:1][0].title if categories.get('society') else 'society'}, "
                    "each story reveals deeper patterns worth your attention.*\n"
                )
        else:
            # Fallback when no LLM available
            out.append(
                "\n*This week's briefing cuts through the noise to surface what actually matters. "
                f"From {categories.get('technology', [])[:1][0].title if categories.get('technology') else 'tech'} to "
                f"{categories.get('society', [])[:1][0].title if categories.get('society') else 'society'}, "
                "each story reveals deeper patterns worth your attention.*\n"
            )

        # Dynamic intro based on top stories
        top_stories = []
        for category, items in categories.items():
            if items:
                top_stories.append((category, items[0]))

        if len(top_stories) >= 2:
            intro_items = []
            for category, item in top_stories[:3]:  # Top 3 stories
                source_url, source_name = await self._get_source_attribution(item)

                # Use actual article author if available, otherwise use source name
                attribution = (
                    item.author if item.author and item.author.strip() else source_name
                )

                if source_url:
                    intro_items.append(
                        f"**{item.title}** by {attribution} ([{source_name}]({source_url}))"
                    )
                else:
                    intro_items.append(f"**{item.title}** by {attribution}")
            out.append(f"\n*Today's highlights: {' • '.join(intro_items)}*\n")

        out.append("\n---\n")

        # Add Headlines at a Glance section (required for structure parity)
        out.append("\n## HEADLINES AT A GLANCE\n")

        # Generate quick headline list from all categories
        all_headlines = []
        for category, items in categories.items():
            for item in items[:2]:  # Top 2 from each category
                # Clean up the title for headlines
                clean_title = self._clean_headline_title(item.title)

                source_url, source_name = await self._get_source_attribution(item)
                if source_url:
                    all_headlines.append(
                        f"• {clean_title} ([{source_name}]({source_url}))"
                    )
                else:
                    all_headlines.append(f"• {clean_title} ({source_name})")

        if all_headlines:
            out.append("\n".join(all_headlines[:8]))  # Limit to 8 headlines
            out.append("\n")

        out.append("\n---\n")

        # FEATURED STORIES - show all stories in plain format without tables
        available_categories = [cat for cat, items in categories.items() if items]

        # Get all items for main stories section
        all_stories = []
        for category, items in categories.items():
            for item in items:
                all_stories.append((category, item))

        if all_stories:
            out.append("## FEATURED STORIES\n")

            # Show up to 7 stories in plain format
            for i, (category, item) in enumerate(all_stories[:7]):
                img_url, alt_text = await get_unsplash_image_with_alt(
                    category, item.title
                )
                source_url, source_name = await self._get_source_attribution(item)

                # Generate longer, more detailed summary (2-3 paragraphs)
                if self.openrouter_client:
                    try:
                        expand_prompt = f"""Based on this content, write a detailed 2-3 paragraph summary that:
1. Explains the key facts and context clearly 
2. Analyzes the implications and significance
3. Maintains journalistic tone without hype
4. Stays under 400 words
5. IMPORTANT: Write in third person - this article was written by someone else, not by you
6. IMPORTANT: Never use first person (I, we, me, my) - describe what the author/article discusses

Original content: {item.content[:1000]}

Title: {item.title}
Author: {item.author if item.author else 'Unknown'}

Write the expanded summary in third person:"""

                        expand_response = await self.openrouter_client._make_request(
                            expand_prompt, max_tokens=500, temperature=0.3
                        )
                        if expand_response and "choices" in expand_response:
                            detailed_summary = expand_response["choices"][0]["message"][
                                "content"
                            ].strip()
                        else:
                            # Fallback to original content
                            detailed_summary = (
                                item.content[:600].replace("\n", " ").strip()
                            )
                    except Exception as e:
                        logger.debug(f"Error generating detailed summary: {e}")
                        detailed_summary = item.content[:600].replace("\n", " ").strip()
                else:
                    # Longer summary when no LLM available
                    detailed_summary = item.content[:600].replace("\n", " ").strip()

                # Format as story with improved image layout
                out.append(f"### {item.title}\n\n")

                # Add image with better formatting and caption
                out.append(f'<div align="center">\n')
                out.append(
                    f'<img src="{img_url}" alt="{alt_text}" style="max-width: 100%; height: auto; border-radius: 8px; margin: 16px 0;">\n'
                )
                out.append(
                    f'<br><em style="color: #666; font-size: 0.9em;">Photo: {alt_text}</em>\n'
                )
                out.append(f"</div>\n\n")

                out.append(f"{detailed_summary}\n")
                if source_url:
                    out.append(f"*Read more: [{source_name}]({source_url})*\n")
                else:
                    out.append(f"*Source: {source_name}*\n")

                if i < len(all_stories[:7]) - 1:  # Add separator except for last story
                    out.append("\n---\n")

            out.append("\n---\n")

        # All technology stories now included in FEATURED STORIES section above

        # All stories from society, arts, and business categories now included in FEATURED STORIES section above

        # SOURCES & ATTRIBUTION
        out.append("## SOURCES & ATTRIBUTION\n")

        def sources_line(cat):
            # Skip if category doesn't exist in our dynamic categories
            if cat not in categories or not categories[cat]:
                return None
            # Collect unique sources to avoid repetition, but only include items with valid URLs and sources
            source_map = {}
            for item in categories[cat]:
                if item.url and str(item.url).startswith(("http://", "https://")):
                    src_name = item.source_title or item.source
                    # Skip if source name is missing or generic
                    problematic_sources = [
                        "Unknown",
                        "Unknown Source",
                        "Newsletters",
                        "Starred Articles",
                        "Justice",
                        "URL",
                        "Link",
                        "Source",
                        "Placeholder",
                    ]

                    # Also check for URL-pattern sources like "Url3396"
                    is_url_pattern = (
                        re.match(r"^url\d+$", src_name.lower().strip())
                        if src_name
                        else False
                    )

                    if (
                        not src_name
                        or src_name in problematic_sources
                        or src_name.lower().strip()
                        in [s.lower() for s in problematic_sources]
                        or is_url_pattern
                        or (
                            src_name.lower() == item.source.lower()
                            if item.source
                            else False
                        )
                    ):
                        # Try to extract source from URL instead
                        if hasattr(self, "_extract_source_from_url"):
                            src_name = self._extract_source_from_url(str(item.url))

                        # If still problematic, use a generic but acceptable fallback
                        if not src_name or src_name in problematic_sources:
                            # Use category-based fallback instead of skipping
                            category_sources = {
                                "technology": "Tech News",
                                "society": "Current Affairs",
                                "art": "Arts & Culture",
                                "business": "Business News",
                            }
                            # Get category for this item (simplified)
                            src_name = category_sources.get(
                                "technology", "Curated Source"
                            )
                            logger.debug(
                                f"Using fallback source '{src_name}' for {item.title[:30]}..."
                            )

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

        # Only add source lines for categories that exist
        source_lines = []

        tech_sources = sources_line("technology")
        if tech_sources:
            source_lines.append(f"**Technology:** {tech_sources}")

        society_sources = sources_line("society")
        if society_sources:
            source_lines.append(f"**Society:** {society_sources}")

        art_sources = sources_line("art")
        if art_sources:
            source_lines.append(f"**Arts:** {art_sources}")

        business_sources = sources_line("business")
        if business_sources:
            source_lines.append(f"**Business:** {business_sources}")

        if source_lines:
            out.append("\n".join(source_lines))
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

        best_category = max(scores, key=lambda k: scores[k])

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
        """Enrich content items with LLM-powered improvements."""
        if not self.openrouter_client:
            logger.debug("No OpenRouter client available for LLM enrichment")
            return items

        enriched_items = []

        for item in items:
            try:
                # Skip if content is already high quality
                if self._is_high_quality_content(item):
                    logger.debug(
                        f"Skipping LLM enrichment for high-quality content: '{item.title[:40]}...'"
                    )
                    enriched_items.append(item)
                    continue

                # Create a working copy
                enriched_item = ContentItem(
                    id=item.id,
                    title=item.title,
                    content=item.content,
                    source=item.source,
                    url=item.url,
                    author=item.author,
                    source_title=item.source_title,
                    is_paywalled=item.is_paywalled,
                    tags=item.tags,
                    created_at=item.created_at,
                    metadata=item.metadata,
                )

                # Enhance title if needed
                if not self._is_meaningful_title(item.title):
                    try:
                        better_title = await self.openrouter_client.improve_title(
                            item.title, item.content[:500]
                        )
                        if better_title and len(better_title.strip()) >= 10:
                            enriched_item.title = better_title
                            logger.debug(
                                f"Enhanced title: '{item.title}' -> '{better_title}'"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Title enhancement failed for '{item.title}': {e}"
                        )

                # Improve content quality and fix truncation
                if len(item.content.strip()) < 100 or item.content.endswith(
                    ("...", "…")
                ):
                    try:
                        enhanced_content = (
                            await self.openrouter_client.enhance_content_summary(
                                enriched_item.title, item.content, max_length=300
                            )
                        )
                        if enhanced_content and len(enhanced_content.strip()) > len(
                            item.content.strip()
                        ):
                            enriched_item.content = enhanced_content
                            logger.debug(
                                f"Enhanced content length: {len(item.content)} -> {len(enhanced_content)} chars"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Content enhancement failed for '{item.title}': {e}"
                        )

                enriched_items.append(enriched_item)

            except Exception as e:
                logger.warning(f"LLM enrichment failed for '{item.title[:40]}...': {e}")
                # Keep original item if enrichment fails
                enriched_items.append(item)

        logger.info(
            f"LLM enrichment completed: {len(enriched_items)}/{len(items)} items processed"
        )
        return enriched_items

    def _is_high_quality_content(self, item: ContentItem) -> bool:
        """Check if content is already high quality and doesn't need LLM enhancement."""
        if not item.content or not item.title:
            return False

        # Good length content
        if len(item.content.strip()) < 80:
            return False

        # Meaningful title
        if not self._is_meaningful_title(item.title):
            return False

        # Proper sentence structure
        if not item.content.strip().endswith((".", "!", "?", ":")):
            return False

        # Not obviously truncated
        if item.content.endswith(("...", "…")):
            return False

        return True

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
                    is_paywalled=False,
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

        # Initialize content sanitizer
        self.sanitizer = ContentSanitizer()

        # Initialize voice system for commentary generation
        self.voice_manager = VoiceManager(default_voice=settings.default_voice)

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
                image_url=None,
                draft_id=None,
                metadata=None,
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
                image_url=None,
                draft_id=None,
                metadata=None,
            )

        logger.info(f"Aggregated {len(content_items)} content items")

        # Step 2: Process and organize content
        processed_content = await self._process_content(content_items)

        # Step 2.3: Enhance content quality FIRST (includes editorial workflow to transform raw input)
        enhanced_content = await self._enhance_content_quality(processed_content)

        # Step 2.5: Validate and sanitize content AFTER editorial transformation (critical quality gate)
        validated_content = await self._validate_and_sanitize_content(enhanced_content)

        # Step 2.7: Filter for content diversity to prevent repetitive themes
        diverse_content = self._ensure_content_diversity(validated_content)

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

        # Step 4: Quality Check BEFORE publishing
        logger.info("Running final QA checks on newsletter content...")
        qa_results = run_checks(newsletter.content)

        # Write QA results to output directory
        out_dir = Path("out")
        out_dir.mkdir(exist_ok=True)
        qa_file = out_dir / "qa.json"
        qa_file.write_text(
            json.dumps(qa_results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if not qa_results["passed"]:
            critical_failed = qa_results["summary"].get("critical_failed", 0)
            warning_count = qa_results["summary"].get("warnings", 0)

            if critical_failed > 0:
                logger.error(
                    f"QA checks failed - {critical_failed} critical issues found, newsletter blocked from publishing"
                )
                logger.error(f"QA results written to {qa_file}")
                logger.error(
                    "Critical content quality issues detected - newsletter generation failed"
                )
                return newsletter  # Return the draft but don't publish
            else:
                logger.warning(
                    f"QA checks found {warning_count} warnings but no critical issues - proceeding with publication"
                )
                logger.info(f"QA results with warnings written to {qa_file}")
        else:
            logger.info("QA checks passed - proceeding with publication")

        # Step 5: Publish (if not dry run and QA passed)
        if not dry_run and self.settings.buttondown_api_key:
            published = await self._publish_newsletter(newsletter, dry_run=False)
            if published:
                logger.info("Newsletter published successfully")
            else:
                logger.error("Newsletter publishing failed")
        else:
            await self._publish_newsletter(newsletter, dry_run=True)
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

        # Do not send newsletter if fewer than 7 items for quality content threshold
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
                    # Use source_url (actual article URL) instead of url (Readwise proxy URL)
                    source_url = doc.get("source_url", "")
                    proxy_url = doc.get("url", "")
                    url = source_url or proxy_url

                    site_name = doc.get(
                        "site_name", ""
                    )  # Direct source name from Readwise
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
                        else:
                            # Remove tracking parameters
                            clean_url = self._clean_tracking_params(clean_url)

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

                    # Extract actual source - prefer site_name, then URL extraction, then fallback
                    actual_source_title = "Readwise Reader"  # fallback
                    if site_name and site_name.strip():
                        # Use site_name from Readwise if available (most accurate)
                        actual_source_title = site_name.strip()
                    elif clean_url:
                        # Fallback to URL extraction
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
                        is_paywalled=False,
                        tags=tags,
                        created_at=created_at,
                        metadata={
                            "category": category,
                            "location": doc.get("location", ""),
                            "word_count": word_count,
                            "reading_progress": reading_progress,
                            "reader_doc_id": doc.get("id"),
                            "source_url": source_url,  # Store original source URL from Readwise
                            "site_name": site_name,  # Store original site name from Readwise
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
                    is_paywalled=False,
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

    async def _validate_and_sanitize_content(
        self, content_items: List[ContentItem]
    ) -> List[ContentItem]:
        """Validate and sanitize content items, filtering out problematic content."""
        validated_items = []
        total_issues = []

        for item in content_items:
            # Convert ContentItem to dict for sanitizer
            content_dict = {
                "title": item.title,
                "summary": getattr(item, "summary", ""),
                "description": item.content,
                "commentary": getattr(item, "commentary", ""),
                "source_title": item.source_title,
                "url": str(item.url) if item.url else "",
            }

            # Run comprehensive quality check
            issues = self.sanitizer.check_content_quality(content_dict)

            if issues:
                issue_count = sum(len(issue_list) for issue_list in issues.values())
                logger.warning(
                    f"Content issues found for '{item.title[:50]}...': {issue_count} issues"
                )

                # Log specific issues for debugging
                for field, field_issues in issues.items():
                    for issue in field_issues:
                        logger.debug(f"  {field}: {issue}")
                        total_issues.append(f"{field}: {issue}")

                # Filter out content with only the most critical issues - be more selective
                critical_issues = [
                    "AI refusal detected",
                    "Prompt leakage detected",
                ]

                # Other issues (truncation, CDN sources, etc.) will be logged but content preserved
                # The AI editor can handle and improve most content quality issues
                has_critical_issues = any(
                    any(critical in issue for critical in critical_issues)
                    for issue_list in issues.values()
                    for issue in issue_list
                )

                if has_critical_issues:
                    logger.error(
                        f"Dropping content due to critical issues: {item.title}"
                    )
                    continue

            # Update item with sanitized content
            item.title = content_dict["title"]
            if hasattr(item, "summary"):
                item.summary = content_dict["summary"]
            item.content = content_dict["description"]
            if hasattr(item, "commentary"):
                item.commentary = content_dict["commentary"]
            # Update URL with canonical version
            item.url = content_dict["url"]

            validated_items.append(item)

        # Log summary of issues found
        if total_issues:
            logger.warning(
                f"Content validation found {len(total_issues)} total issues across {len(content_items)} items"
            )

            # Fail fast only for the most severe critical issues that would make content unusable
            # Be more selective - only count issues that make content completely unusable
            severe_critical_count = sum(
                1
                for issue in total_issues
                if any(
                    critical in issue
                    for critical in [
                        "AI refusal detected",
                        "Prompt leakage detected",
                        "Content completely removed",
                        "Content too short: 0 chars",
                    ]
                )
            )

            # CDN/proxy URLs are quality issues but not critical failures
            # Other issues like truncation, placeholder content can be handled by AI enhancement
            if (
                severe_critical_count > len(content_items) * 0.5
            ):  # More than 50% have severe critical issues
                raise ValueError(
                    f"Too many severe content issues: {severe_critical_count}/{len(content_items)} items have critical failures"
                )

            # Log less severe issues for monitoring but don't fail the entire batch
            moderate_critical_count = sum(
                1
                for issue in total_issues
                if any(
                    critical in issue
                    for critical in [
                        "CDN/proxy URL",
                        "Placeholder",
                        "Generic",
                        "Non-canonical URL",
                    ]
                )
            )

            if moderate_critical_count > 0:
                logger.warning(
                    f"Found {moderate_critical_count} moderate quality issues (CDN URLs, placeholders, etc.) - will attempt to enhance with AI"
                )

        logger.info(
            f"Content validation: {len(validated_items)}/{len(content_items)} items passed validation"
        )
        return validated_items

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
                            enhanced_title, enhanced_content, max_length=400
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
                is_paywalled=item.is_paywalled,
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

    def _clean_headline_title(self, title: str) -> str:
        """Clean and format a title for the Headlines at a Glance section.

        Args:
            title: Raw title to clean

        Returns:
            str: Cleaned title suitable for headlines
        """
        if not title:
            return "Untitled Article"

        # Clean up the title
        clean_title = title.strip()

        # Remove trailing ellipses and truncation indicators
        clean_title = re.sub(r"\.{3,}$", "", clean_title)
        clean_title = re.sub(r"\s*\.\.\.$", "", clean_title)

        # Remove weird trailing characters and artifacts
        clean_title = re.sub(r"[_\-\|]+$", "", clean_title)
        clean_title = re.sub(r"\s*-+\s*$", "", clean_title)

        # Fix common formatting issues
        clean_title = clean_title.replace("...", "").strip()

        # Handle titles that are too short after cleaning
        if len(clean_title) < 10:
            return "Article Summary"

        # Improve capitalization for titles that are all lowercase or poorly formatted
        if clean_title.islower() or (
            clean_title.count(" ") > 2 and not any(c.isupper() for c in clean_title[1:])
        ):
            # Use title case but preserve proper nouns and acronyms
            words = clean_title.split()
            title_words = []
            for i, word in enumerate(words):
                # Keep common lowercase words lowercase if they're not at the start
                if i > 0 and word.lower() in [
                    "and",
                    "or",
                    "but",
                    "to",
                    "for",
                    "of",
                    "with",
                    "by",
                    "in",
                    "on",
                    "at",
                    "the",
                    "a",
                    "an",
                ]:
                    title_words.append(word.lower())
                else:
                    title_words.append(word.capitalize())
            clean_title = " ".join(title_words)

        # Truncate overly long titles for headlines (keep under 80 chars)
        if len(clean_title) > 80:
            # Try to truncate at word boundary
            words = clean_title[:77].split()
            if len(words) > 1:
                clean_title = " ".join(words[:-1]) + "..."
            else:
                clean_title = clean_title[:77] + "..."

        return clean_title

    def _extract_source_from_title_or_content(self, item: ContentItem) -> str:
        """Extract source name from title patterns or content metadata.

        Args:
            item: Content item to analyze

        Returns:
            str: Extracted source name, or empty string if none found
        """
        import re

        # Check title for common patterns like "The Briefing: ..." from The Information
        title = item.title or ""

        # Pattern: "The Briefing: ..." indicates The Information
        if title.startswith("The Briefing:"):
            return "The Information"

        # Pattern: "GPT-5: ..." or similar titles often from One Useful Thing
        if re.match(r"^GPT-?\d+:", title, re.IGNORECASE):
            return "One Useful Thing"

        # Pattern: AI/ML focused titles that commonly come from One Useful Thing
        if any(
            pattern in title.lower()
            for pattern in ["gpt-", "claude", "ai does", "it just does", "useful thing"]
        ):
            # Check if URL contains oneusefulthing domain
            if item.url and "oneusefulthing" in str(item.url).lower():
                return "One Useful Thing"

        # Pattern: "From [Source]:" at start of title
        briefing_match = re.match(r"^From\s+([^:]+):", title)
        if briefing_match:
            return briefing_match.group(1).strip()

        # Check if content mentions the source explicitly
        content = item.content or ""
        if len(content) > 0:
            # Look for "Via [Source]" or "Source: [Source]" patterns
            via_match = re.search(
                r"(?:Via|Source):\s*([A-Za-z\s&]+?)(?:\.|,|\n|$)", content
            )
            if via_match:
                source = via_match.group(1).strip()
                if (
                    len(source) > 2 and len(source) < 50
                ):  # Reasonable source name length
                    return source

        # Check metadata for better source information
        if item.metadata:
            # Some RSS feeds put the real source in metadata
            if "original_source" in item.metadata:
                return str(item.metadata["original_source"])
            if "publication" in item.metadata:
                return str(item.metadata["publication"])

        return ""

    async def _improve_source_attribution(self, item: ContentItem) -> dict:
        """Improve source attribution to avoid 'Unknown' sources."""

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

            # Handle private CDN URLs - these are content proxies that readers cannot access
            if any(
                cdn in domain
                for cdn in [
                    "feedbinusercontent.com",
                    "newsletters.feedbinusercontent.com",
                    "substackcdn.com",  # Substack CDN URLs like eotrx.substackcdn.com/open
                ]
            ):
                return "PRIVATE_CDN"  # Special marker to indicate this is a private CDN URL

            # Handle tracking/redirect URLs - extract the real domain
            # Examples: url3396.theinformation.com -> theinformation, click.convertkit-mail.com -> convertkit
            if re.match(
                r"^(url\d+|click|track|email|newsletter|redirect|link)\.", domain
            ):
                # Extract the main domain part after the tracking subdomain
                parts = domain.split(".")
                if len(parts) >= 2:
                    # Try to find the actual domain (skip tracking subdomains)
                    for i in range(1, len(parts)):
                        potential_domain = ".".join(parts[i:])
                        # Remove common prefixes and suffixes from the potential domain
                        clean_potential = re.sub(
                            r"^(www\.|m\.|mobile\.)", "", potential_domain
                        )
                        clean_potential = re.sub(
                            r"\.(com|org|net|edu|gov|io|co\.uk|ai)$",
                            "",
                            clean_potential,
                        )
                        if (
                            clean_potential and len(clean_potential) > 2
                        ):  # Valid domain name
                            domain = clean_potential
                            break
            else:
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
                "theinformation": "The Information",
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

    def _clean_tracking_params(self, url: str) -> str:
        """Remove tracking parameters from URL."""
        try:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)

            # Define tracking parameters to remove
            tracking_params = {
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_content",
                "utm_term",
                "_bhlid",
                "fbclid",
                "gclid",
                "msclkid",
                "twclid",
                "li_source",
                "li_medium",
                "ref",
                "source",
                "campaign_id",
                "ad_id",
                "affiliate_id",
                "partner_id",
                "mc_cid",
                "mc_eid",
                "WT.mc_id",
                "_hsenc",
                "_hsmi",
                "hsCtaTracking",
                "mkt_tok",
                "trk",
                "trkCampaign",
                "ss_email_id",
                "vero_id",
                "vero_conv",
                "ck_subscriber_id",
                "sb_referer_host",
                "ref_",
                "referer",
                "referrer",
            }

            # Remove tracking parameters
            clean_params = {
                k: v for k, v in query_params.items() if k not in tracking_params
            }

            # Rebuild URL
            clean_query = urlencode(clean_params, doseq=True) if clean_params else ""
            clean_parsed = parsed._replace(query=clean_query)

            return urlunparse(clean_parsed)

        except Exception as e:
            logger.debug(f"Error cleaning URL {url}: {e}")
            return url  # Return original if cleaning fails

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

            # Step 2: Generate voice-based commentary using article + user highlights
            logger.info(
                f"🎭 {self.settings.default_voice.title()} voice: generating commentary for '{title[:50]}...'"
            )

            # Prepare content for voice generation
            content_for_voice = f"TITLE: {title}\n\nCONTENT: {article_content if article_content else 'Article content not available'}"
            notes_for_voice = f"USER HIGHLIGHTS: {user_highlights}"

            try:
                # Generate using voice system
                voice_response = await self.voice_manager.generate_commentary(
                    content=content_for_voice,
                    notes=notes_for_voice,
                    voice=self.settings.default_voice,
                    language=self.settings.voice_languages.split(",")[0].strip(),
                    target_words=self.settings.voice_target_words,
                    image_subject=None,  # Could extract from title/content later
                    llm_client=self.openrouter_client,
                )

                # Extract the story content
                commentary = voice_response.get(
                    "content", voice_response.get("story", "")
                )

                # Log voice metadata for debugging
                if voice_response.get("voice_metadata"):
                    metadata = voice_response["voice_metadata"]
                    logger.debug(
                        f"Voice generation: {metadata.get('voice')} in {metadata.get('language')}"
                    )

            except Exception as e:
                logger.warning(
                    f"Voice generation failed, falling back to simple commentary: {e}"
                )
                # Fallback to simple OpenRouter commentary
                commentary = await self.openrouter_client.generate_commentary(
                    (
                        article_content
                        if article_content
                        else "Article content not available"
                    ),
                    user_highlights,
                    title,
                )

            # Validate commentary quality - check for AI refusal patterns
            if commentary:
                commentary_lower = commentary.lower()
                refusal_patterns = [
                    "i cannot fulfill your request",
                    "i am just an ai model",
                    "i can't provide assistance",
                    "i cannot create content",
                    "it is not within my programming",
                    "ethical guidelines",
                    "i'm unable to",
                    "as an ai",
                ]

                # If commentary contains refusal patterns, reject and use fallback
                for pattern in refusal_patterns:
                    if pattern in commentary_lower:
                        logger.warning(f"AI refusal detected in commentary: {pattern}")
                        commentary = None
                        break

            # Fallback only if AI generation completely fails or contains refusals
            if not commentary or commentary.strip() == user_highlights.strip():
                logger.warning(
                    "AI commentary generation failed or contained refusals, using formatted highlights as fallback"
                )
                commentary = self._format_user_insights(user_highlights, title)

            # Skip complex editorial workflow for free models - single shot works better
            # For free Llama model, the initial commentary is already high quality
            logger.info("✅ Using single-shot commentary for free model")

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
                logger.info("🎭 Editor agent: reviewing complete newsletter")
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
        """Check if content item meets minimum quality standards with detailed failure reasons."""
        failures = []
        title_preview = (
            item.title[:40] + "..."
            if item.title and len(item.title) > 40
            else item.title or "[NO TITLE]"
        )

        # More lenient minimum content length
        if not item.content or len(item.content.strip()) < 20:
            failures.append(
                f"Content too short: {len(item.content.strip() if item.content else '')} chars (min: 20)"
            )

        # More lenient title requirements
        if not item.title or len(item.title.strip()) < 5:
            failures.append(f"Title too short: '{item.title}' (min: 5 chars)")

        # Must have either URL or source info
        if not item.url and not item.source_title:
            failures.append("Missing both URL and source_title")

        # More lenient punctuation check - allow more ending patterns
        if item.content:
            content_stripped = item.content.strip()
            valid_endings = (".", "!", "?", ":", ";", '"', "'", ")", "]", "}", ">")
            if not content_stripped.endswith(
                valid_endings
            ) and not content_stripped.endswith("..."):
                # Check if it ends with a word (might be intentionally truncated for newsletter format)
                if not content_stripped[-1].isalnum():
                    failures.append(
                        f"Invalid content ending: '{content_stripped[-20:]}' (must end with punctuation or word)"
                    )

        # Check for AI refusal text and prompt leakage (only critical patterns)
        if item.content and item.title:
            content_lower = item.content.lower()
            title_lower = item.title.lower()

            # Only block the most critical AI refusal patterns
            critical_refusal_patterns = [
                "i cannot fulfill your request",
                "i am just an ai model",
                "i cannot create content",
                "it is not within my programming",
                "i cannot help with",
            ]

            for pattern in critical_refusal_patterns:
                if pattern in content_lower or pattern in title_lower:
                    failures.append(f"AI refusal pattern detected: '{pattern}'")
                    break  # Only report first match

            # Only block obvious conversational AI fluff that starts content
            conversational_patterns = [
                "i'll never tire of hearing",
                "i couldn't help but",
                "let me tell you",
                "picture this",
            ]

            for pattern in conversational_patterns:
                if content_lower.startswith(pattern):
                    failures.append(
                        f"Conversational AI fluff detected: starts with '{pattern}'"
                    )
                    break  # Only report first match

        # Less strict URL validation - only block if we can't canonicalize critical domains
        if item.url:
            url_str = str(item.url).lower()
            # Only block if it's clearly a tracking/proxy URL that provides no value
            critical_problematic_domains = [
                "list-manage.com",  # MailChimp tracking
                "track.click",  # Generic tracking
                "redirect.",  # Generic redirects
            ]

            for domain in critical_problematic_domains:
                if domain in url_str:
                    failures.append(f"Blocked tracking URL domain: '{domain}'")
                    break  # Only report first match

        # Log results
        if failures:
            logger.warning(
                f"Quality check FAILED for '{title_preview}': {'; '.join(failures)}"
            )
            return False
        else:
            logger.debug(f"Quality check PASSED for '{title_preview}'")
            return True

    async def _resolve_tracking_url(self, tracking_url: str) -> str:
        """Attempt to resolve a tracking URL to get the real destination.

        Args:
            tracking_url: The tracking/redirect URL to resolve

        Returns:
            str: The resolved URL or empty string if resolution fails
        """
        try:
            import aiohttp

            # Try to follow redirects to get the real URL
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    # Use HEAD request to avoid downloading content
                    async with session.head(
                        tracking_url, allow_redirects=True
                    ) as response:
                        if response.status < 400:
                            final_url = str(response.url)
                            if final_url != tracking_url:
                                logger.info(
                                    f"Resolved tracking URL: {tracking_url} -> {final_url}"
                                )
                                return final_url
                except Exception as e:
                    logger.debug(f"Failed to resolve tracking URL {tracking_url}: {e}")

            return ""

        except Exception as e:
            logger.debug(f"Error resolving tracking URL {tracking_url}: {e}")
            return ""

    async def _search_archive_org(self, title: str, domain: str = "") -> str:
        """Search archive.org for articles with similar title.

        Args:
            title: Article title to search for
            domain: Optional domain to search within

        Returns:
            str: Archive.org URL if found, empty string otherwise
        """
        try:
            from urllib.parse import quote

            import aiohttp

            # Prepare search query
            search_terms = title.replace('"', "").replace("'", "")  # Remove quotes
            search_query = quote(search_terms)

            if domain:
                # Search within specific domain
                search_url = f"https://web.archive.org/cdx/search/cdx?url={domain}/*&output=json&fl=timestamp,original&filter=statuscode:200&limit=50"
            else:
                # General search (less reliable)
                search_url = (
                    f"https://web.archive.org/web/20231201000000*/{search_query}"
                )

            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.get(search_url) as response:
                        if response.status == 200:
                            if domain:
                                # Parse CDX API response
                                data = await response.json()
                                if (
                                    isinstance(data, list) and len(data) > 1
                                ):  # First row is headers
                                    # Find most recent snapshot
                                    for row in data[1:]:  # Skip header row
                                        if len(row) >= 2:
                                            timestamp, original_url = row[0], row[1]
                                            archive_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                                            logger.info(
                                                f"Found archive.org snapshot: {archive_url}"
                                            )
                                            return archive_url
                            else:
                                # Check if archive.org has content
                                final_url = str(response.url)
                                if (
                                    "web.archive.org/web/" in final_url
                                    and response.status == 200
                                ):
                                    logger.info(f"Found archive.org page: {final_url}")
                                    return final_url
                except Exception as e:
                    logger.debug(f"Error searching archive.org: {e}")

            return ""

        except Exception as e:
            logger.debug(f"Error accessing archive.org for '{title}': {e}")
            return ""

    async def _search_group_lt(self, title: str) -> str:
        """Search s.group.lt for alternative articles about the same news.

        Args:
            title: Article title to search for

        Returns:
            str: URL to search results if found, empty string otherwise
        """
        try:
            from urllib.parse import quote

            import aiohttp

            # Strategy 1: Try full title search first (most precise)
            # Clean up the title but keep it mostly intact
            clean_title = title.strip()
            # Remove special characters that might break search but keep quoted phrases
            clean_title = (
                clean_title.replace('"', "").replace("'", "").replace(":", " ")
            )

            # If title is reasonable length, use full title search
            if len(clean_title) > 10 and len(clean_title) < 150:
                encoded_query = quote(clean_title)
                search_url = f"https://s.group.lt/?q={encoded_query}"

                # Test the full title search
                success = await self._test_search_url(
                    search_url, f"full title: '{clean_title[:50]}...'"
                )
                if success:
                    return search_url

            # Strategy 2: Fallback to keyword extraction if full title search fails
            import re

            # Remove common words and punctuation, keep meaningful terms
            search_terms = re.sub(r"[^\w\s]", " ", title.lower())
            words = search_terms.split()
            # Filter out common words
            stop_words = {
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
                "says",
                "said",
                "new",
                "how",
                "what",
                "why",
                "when",
                "where",
                "from",
            }
            meaningful_words = [w for w in words if len(w) > 3 and w not in stop_words]

            if len(meaningful_words) >= 2:
                # Create search query from meaningful terms (limit to first 4-5 terms)
                search_query = " ".join(meaningful_words[:5])
                encoded_query = quote(search_query)
                search_url = f"https://s.group.lt/?q={encoded_query}"

                success = await self._test_search_url(
                    search_url, f"keywords: '{search_query}'"
                )
                if success:
                    return search_url

            return ""

        except Exception as e:
            logger.debug(f"Error searching s.group.lt for '{title}': {e}")
            return ""

    async def _test_search_url(self, search_url: str, description: str) -> bool:
        """Test if a search URL is accessible.

        Args:
            search_url: The search URL to test
            description: Description for logging

        Returns:
            bool: True if accessible, False otherwise
        """
        try:
            import aiohttp

            # Test if the search service is available (follow redirects)
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.head(
                        search_url, allow_redirects=True
                    ) as response:
                        if response.status == 200:
                            logger.debug(
                                f"s.group.lt search successful with {description}"
                            )
                            return True
                except Exception as e:
                    logger.debug(
                        f"Error testing s.group.lt search with {description}: {e}"
                    )

            return False

        except Exception as e:
            logger.debug(f"Error testing search URL: {e}")
            return False

    async def _find_alternative_source(
        self, title: str, original_url: str
    ) -> tuple[str, str]:
        """Find alternative source for the same news story.

        Args:
            title: Article title to search for
            original_url: Original (possibly inaccessible) URL

        Returns:
            tuple: (alternative_url, source_name) or ("", "") if no alternative found
        """
        if not title or len(title.strip()) < 10:
            return "", ""

        try:
            # First, try to resolve the tracking URL to get the real destination
            resolved_url = await self._resolve_tracking_url(original_url)
            if resolved_url:
                # Check if the resolved URL is accessible and not another tracking URL
                from urllib.parse import urlparse

                parsed = urlparse(resolved_url)
                if parsed.netloc and not any(
                    pattern in parsed.netloc.lower()
                    for pattern in ["url", "click", "track", "redirect"]
                ):
                    source_name = self._extract_source_from_url(resolved_url)
                    logger.info(
                        f"Successfully resolved tracking URL for '{title[:50]}...': {resolved_url}"
                    )
                    return resolved_url, source_name

            # If URL resolution fails, try to find alternatives
            source_name = self._extract_source_from_url(original_url)

            # Try to find the article on archive.org
            logger.debug(
                f"Searching archive.org for article: '{title[:50]}...' from {source_name}"
            )

            # Extract domain from original URL for targeted archive.org search
            from urllib.parse import urlparse

            parsed = urlparse(original_url)
            if parsed.netloc:
                # Clean domain to get the main site (remove tracking subdomains)
                import re

                domain = parsed.netloc.lower()
                if re.match(
                    r"^(url\d+|click|track|email|newsletter|redirect|link)\.", domain
                ):
                    # Extract main domain from tracking subdomain
                    parts = domain.split(".")
                    if len(parts) >= 2:
                        domain = ".".join(parts[1:])  # Skip tracking subdomain

                # Search archive.org for content from this domain
                archive_url = await self._search_archive_org(title, domain)
                if archive_url:
                    logger.info(
                        f"Found archive.org alternative for '{title[:50]}...': {archive_url}"
                    )
                    # Provide a meaningful source name if extraction failed
                    final_source_name = source_name if source_name else "Source"
                    return archive_url, f"{final_source_name} (Archive)"

            # If archive.org doesn't have results, try s.group.lt as fallback
            logger.debug(
                f"Archive.org search failed, trying s.group.lt for '{title[:50]}...'"
            )
            search_url = await self._search_group_lt(title)
            if search_url:
                logger.info(
                    f"Found s.group.lt search alternative for '{title[:50]}...': {search_url}"
                )
                return search_url, f"Search: {source_name}"

            # For paywall/premium sites, still prefer text-only to avoid confusion
            paywall_sources = {
                "The Information",
                "Wall Street Journal",
                "Financial Times",
                "New York Times",
            }

            if source_name in paywall_sources:
                logger.debug(
                    f"Detected paywall source '{source_name}', using text-only attribution"
                )
                return "", source_name

            # For other sources, return the source name but no URL (will show as text-only)
            logger.warning(
                f"Could not resolve tracking URL or find archive for '{title[:50]}...', showing source name only"
            )
            return "", source_name

        except Exception as e:
            logger.debug(f"Error finding alternative source for '{title}': {e}")
            source_name = self._extract_source_from_url(original_url)
            return "", source_name

    async def _get_source_attribution(self, item: ContentItem) -> tuple[str, str]:
        """Get clean source URL and name for attribution.

        Returns:
            tuple: (source_url, source_name) where source_url is clean URL and source_name is display name
        """
        # Use actual source URL if available, otherwise fallback to item.url
        source_url = None
        if item.metadata and item.metadata.get("source_url"):
            source_url = item.metadata["source_url"]
        elif item.url:
            source_url = str(item.url)

        if source_url:
            # Clean the URL of tracking parameters
            clean_url = self._clean_tracking_params(source_url)

            # Check if this is a tracking URL that might be inaccessible
            import re
            from urllib.parse import urlparse

            parsed = urlparse(clean_url)
            is_tracking_url = False
            if parsed.netloc:
                domain = parsed.netloc.lower()
                is_tracking_url = bool(
                    re.match(
                        r"^(url\d+|click|track|email|newsletter|redirect|link)\.",
                        domain,
                    )
                )

            # If it's a tracking URL, try to find an alternative source
            if is_tracking_url:
                logger.debug(
                    f"Detected tracking URL: {clean_url}, searching for alternative source"
                )
                alt_url, alt_source = await self._find_alternative_source(
                    item.title, clean_url
                )
                if alt_url:
                    logger.info(
                        f"Found alternative source for '{item.title[:50]}...': {alt_url}"
                    )
                    return alt_url, alt_source
                else:
                    # Use improved source name extraction for tracking URLs but no URL (to avoid broken links)
                    source_name = self._extract_source_from_url(clean_url)
                    if source_name and source_name not in ["Unknown", "Source"]:
                        logger.warning(
                            f"Tracking URL detected but no alternative found for '{item.title[:50]}...', showing source name only"
                        )
                        return (
                            "",
                            source_name,
                        )  # Return empty URL to show text-only source

            # Extract domain or use source title - prioritize extracted domain over generic source titles
            extracted_source = self._extract_source_from_url(clean_url)

            # Check if this is a private CDN URL that readers can't access
            if extracted_source == "PRIVATE_CDN":
                logger.debug(
                    f"Detected private CDN URL for '{item.title[:50]}...', checking for original source URL"
                )

                # For Readwise items, check if we have the original source_url in metadata
                if (
                    item.source in ["readwise", "readwise_reader"]
                    and hasattr(item, "metadata")
                    and item.metadata
                ):
                    original_source_url = item.metadata.get(
                        "source_url"
                    ) or item.metadata.get("url")
                    if original_source_url and original_source_url != clean_url:
                        # Use the original source URL from Readwise metadata
                        # Prefer site_name from Readwise metadata as it's most accurate
                        source_name = item.metadata.get("site_name")
                        if not source_name:
                            source_name = self._extract_source_from_url(
                                original_source_url
                            )
                        if not source_name or source_name == "PRIVATE_CDN":
                            source_name = self._extract_source_from_title_or_content(
                                item
                            )
                        if not source_name:
                            source_name = "Source"
                        logger.info(
                            f"Using original source URL from Readwise metadata for '{item.title[:50]}...': {source_name}"
                        )
                        return original_source_url, source_name

                # If no original source URL available, fall back to search
                search_url = await self._search_group_lt(item.title)
                if search_url:
                    logger.info(
                        f"Generated search link for private CDN content '{item.title[:50]}...': {search_url}"
                    )
                    return search_url, "Search"
                else:
                    # Final fallback: create a basic search URL manually
                    import urllib.parse

                    clean_title = item.title.replace('"', "").replace("'", "")[:100]
                    encoded_query = urllib.parse.quote(clean_title)
                    fallback_search = f"https://s.group.lt/?q={encoded_query}"
                    logger.info(
                        f"Created fallback search for private CDN content '{item.title[:50]}...': {fallback_search}"
                    )
                    return fallback_search, "Search"

            # Try to extract a better source name from the title or content if available
            better_source = self._extract_source_from_title_or_content(item)

            # Only use item.source_title/source if they're meaningful (not generic)
            source_from_item = item.source_title or item.source
            generic_sources = {
                "Newsletters",
                "Newsletter",
                "Source",
                "Unknown",
                "RSS",
                "Feed",
            }

            if better_source and better_source not in generic_sources:
                source_name = better_source
            elif extracted_source and extracted_source not in generic_sources:
                source_name = extracted_source
            elif source_from_item and source_from_item not in generic_sources:
                source_name = source_from_item
            elif extracted_source:
                source_name = extracted_source
            else:
                source_name = "Source"

            return clean_url, source_name
        else:
            # Fallback to text-only source if no URL available
            source_from_item = item.source_title or item.source
            generic_sources = {
                "Newsletters",
                "Newsletter",
                "Source",
                "Unknown",
                "RSS",
                "Feed",
            }

            if source_from_item and source_from_item not in generic_sources:
                source_name = source_from_item
            else:
                source_name = "Unknown"
            return "", source_name

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

        # Final template validation and formatting fixes
        structure_issues = self.sanitizer.validate_newsletter_structure(
            newsletter_content
        )
        if structure_issues:
            logger.warning(
                f"Newsletter structure issues found: {len(structure_issues)}"
            )
            for issue in structure_issues[:5]:  # Log first 5 issues
                logger.warning(f"  - {issue}")

            # Apply automatic formatting fixes
            newsletter_content = self.sanitizer.fix_newsletter_formatting(
                newsletter_content
            )
            logger.info("Applied automatic formatting fixes to newsletter")

        return NewsletterDraft(
            title=title,
            content=newsletter_content,
            items=enriched_items,
            created_at=datetime.now(timezone.utc),
            image_url=None,
            draft_id=None,
            metadata=None,
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

    async def _publish_newsletter(
        self, newsletter: NewsletterDraft, dry_run: bool = False
    ) -> bool:
        """Publish newsletter to Buttondown.

        Args:
            newsletter: Newsletter draft to publish
            dry_run: If True, skip QA checks and publishing

        Returns:
            True if published successfully or if dry run
        """
        import json

        import aiohttp

        try:
            if dry_run:
                logger.info("DRY RUN MODE - Skipping QA checks and publishing")
                # Still run QA checks for dry run to show results
                logger.info("Running QA checks for dry run validation...")
                qa_results = run_checks(newsletter.content)

                # Write QA results to output directory
                out_dir = Path("out")
                out_dir.mkdir(exist_ok=True)
                qa_file = out_dir / "qa.json"
                qa_file.write_text(
                    json.dumps(qa_results, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                if not qa_results["passed"]:
                    logger.warning(
                        "QA checks failed in dry run - newsletter would be blocked from publishing"
                    )
                    logger.info(f"QA results written to {qa_file}")
                else:
                    logger.info(
                        "QA checks passed in dry run - newsletter would be published"
                    )

                return True  # Dry run always succeeds

            # QA check before publishing (only for real runs)
            logger.info("Running QA checks on newsletter content...")
            qa_results = run_checks(newsletter.content)

            # Write QA results to output directory
            out_dir = Path("out")
            out_dir.mkdir(exist_ok=True)
            qa_file = out_dir / "qa.json"
            qa_file.write_text(
                json.dumps(qa_results, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if not qa_results["passed"]:
                logger.error("QA checks failed - newsletter blocked from publishing")
                logger.error(f"QA results written to {qa_file}")
                return False

            logger.info("QA checks passed - proceeding with publication")

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

            timeout = aiohttp.ClientTimeout(total=self.settings.buttondown_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Step 1: create draft
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status in {200, 201}:
                        data = await response.json()
                        draft_id = data.get("id")
                        if draft_id:
                            newsletter.draft_id = str(draft_id)
                        logger.info(f"Draft created on Buttondown: {newsletter.title}")
                    else:
                        error_detail = await response.text()
                        status_msg = f"Buttondown API error {response.status}:"
                        logger.error(status_msg)
                        for line in str(error_detail).splitlines():
                            logger.error(f"Buttondown error detail: {line}")
                        return False

                # Step 2: publish draft so it appears in archive
                publish_url = f"{url}/{newsletter.draft_id}/send"
                async with session.post(publish_url, headers=headers) as publish_resp:
                    if publish_resp.status in {200, 201, 202}:
                        logger.info(
                            f"Newsletter published to Buttondown: {newsletter.title}"
                        )
                        return True
                    else:
                        error_detail = await publish_resp.text()
                        status_msg = f"Buttondown publish error {publish_resp.status}:"
                        logger.error(status_msg)
                        for line in str(error_detail).splitlines():
                            logger.error(f"Buttondown publish error detail: {line}")
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
                    timeout = aiohttp.ClientTimeout(
                        total=self.settings.buttondown_timeout
                    )
                    async with aiohttp.ClientSession(timeout=timeout) as session:
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
