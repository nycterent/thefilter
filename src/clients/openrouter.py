"""OpenRouter API client for AI processing and content enhancement."""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API to process content with free models."""

    def __init__(self, api_key: str):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thefilter.buttondown.email",  # Required by OpenRouter
            "X-Title": "The Filter Newsletter",  # Optional title
        }
        # Use free models only
        self.default_model = "google/gemma-2-9b-it:free"  # Free Gemma model

        # Rate limiting for free tier (20 requests/minute)
        self.last_request_time = 0
        self.min_request_interval = (
            3.2  # 3.2 seconds between requests = ~18.75 requests/minute (safe buffer)
        )
        self.consecutive_failures = 0
        self.backoff_multiplier = 1.0

    async def enhance_content_summary(
        self, title: str, content: str, max_length: int = 160
    ) -> str:
        """Enhance content summary using AI.

        Args:
            title: Content title
            content: Original content
            max_length: Maximum summary length

        Returns:
            Enhanced summary or original content if API fails
        """
        if not self.api_key:
            logger.warning("No OpenRouter API key - skipping content enhancement")
            return content[:max_length]

        try:
            prompt = f"""Create an engaging, informative summary for a newsletter. Focus on WHY this matters to readers and what's interesting/surprising. Keep it under {max_length} characters and avoid starting with URLs or social links.

Title: {title}
Content: {content[:600]}

Write a compelling summary that hooks the reader:"""

            response = await self._make_request(prompt, max_tokens=50)
            if response and "choices" in response and len(response["choices"]) > 0:
                summary = response["choices"][0]["message"]["content"].strip()
                # Ensure we don't exceed max_length
                if len(summary) > max_length:
                    summary = summary[: max_length - 3] + "..."
                return summary
            else:
                logger.warning("OpenRouter returned no content")
                return content[:max_length]

        except Exception as e:
            logger.error(f"Error enhancing content with OpenRouter: {e}")
            return content[:max_length]

    async def categorize_content(
        self, title: str, content: str, tags: List[str] = None
    ) -> str:
        """Categorize content using AI.

        Args:
            title: Content title
            content: Content text
            tags: Optional tags

        Returns:
            Category: technology, society, art, or business
        """
        if not self.api_key:
            logger.warning(
                "No OpenRouter API key - falling back to keyword categorization"
            )
            return self._fallback_categorize(title, content, tags)

        try:
            tags_text = f"Tags: {', '.join(tags)}" if tags else ""
            prompt = f"""Categorize this content into exactly one category: technology, society, art, or business.

Title: {title}
Content: {content[:500]}
{tags_text}

Choose the most appropriate category. Respond with only the category name."""

            response = await self._make_request(prompt, max_tokens=10)
            if response and "choices" in response and len(response["choices"]) > 0:
                category = response["choices"][0]["message"]["content"].strip().lower()
                # Validate category
                valid_categories = ["technology", "society", "art", "business"]
                if category in valid_categories:
                    return category
                else:
                    logger.warning(f"AI returned invalid category: {category}")
                    return self._fallback_categorize(title, content, tags)
            else:
                return self._fallback_categorize(title, content, tags)

        except Exception as e:
            logger.error(f"Error categorizing content with OpenRouter: {e}")
            return self._fallback_categorize(title, content, tags)

    def _fallback_categorize(
        self, title: str, content: str, tags: List[str] = None
    ) -> str:
        """Fallback keyword-based categorization."""
        text = f"{title} {content}".lower()
        if tags:
            text += " " + " ".join(tags).lower()

        # Technology keywords
        tech_keywords = [
            "ai",
            "artificial intelligence",
            "machine learning",
            "software",
            "app",
            "algorithm",
            "programming",
            "code",
            "tech",
            "digital",
            "crypto",
            "blockchain",
            "computer",
            "internet",
            "web",
            "data",
            "api",
            "cloud",
            "cybersecurity",
        ]

        # Art keywords
        art_keywords = [
            "art",
            "artist",
            "painting",
            "sculpture",
            "museum",
            "gallery",
            "design",
            "creative",
            "photography",
            "music",
            "film",
            "movie",
            "book",
            "literature",
            "culture",
            "aesthetic",
            "exhibition",
            "performance",
        ]

        # Business keywords
        business_keywords = [
            "business",
            "company",
            "startup",
            "entrepreneur",
            "market",
            "finance",
            "investment",
            "economy",
            "revenue",
            "profit",
            "venture",
            "funding",
            "acquisition",
            "merger",
            "stock",
            "trade",
        ]

        # Count keyword matches
        tech_score = sum(1 for keyword in tech_keywords if keyword in text)
        art_score = sum(1 for keyword in art_keywords if keyword in text)
        business_score = sum(1 for keyword in business_keywords if keyword in text)

        # Return category with highest score
        scores = {
            "technology": tech_score,
            "art": art_score,
            "business": business_score,
            "society": 0,  # Default fallback
        }

        return max(scores, key=scores.get) or "society"

    async def _rate_limit_delay(self):
        """Ensure we don't exceed rate limits by adding delays between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        # Apply exponential backoff if we've had consecutive failures
        effective_interval = self.min_request_interval * self.backoff_multiplier

        if time_since_last < effective_interval:
            delay = effective_interval - time_since_last
            logger.debug(
                f"Rate limiting: waiting {delay:.1f}s before next OpenRouter request"
            )
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    async def _make_request(
        self, prompt: str, max_tokens: int = 100, temperature: float = 0.3
    ) -> Optional[Dict[str, Any]]:
        """Make a request to OpenRouter API.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            API response or None if failed
        """
        payload = {
            "model": self.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        try:
            # Rate limiting to avoid 429 errors
            await self._rate_limit_delay()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        # Reset backoff on successful request
                        self.consecutive_failures = 0
                        self.backoff_multiplier = 1.0
                        return await response.json()
                    elif response.status == 429:
                        # Rate limit hit - increase backoff
                        self.consecutive_failures += 1
                        self.backoff_multiplier = min(
                            8.0, 2.0**self.consecutive_failures
                        )
                        logger.warning(
                            f"Rate limit hit, backing off to {self.backoff_multiplier:.1f}x delay"
                        )
                        return None
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"OpenRouter API error: {response.status} - {error_text}"
                        )
                        return None

        except asyncio.TimeoutError:
            logger.error("OpenRouter API request timed out")
            return None
        except Exception as e:
            # Handle rate limiting with exponential backoff
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(
                    f"OpenRouter rate limit hit, will retry with longer delay: {e}"
                )
                await asyncio.sleep(10)  # Wait 10 seconds on rate limit
                return None
            else:
                logger.error(f"OpenRouter API request failed: {e}")
                return None

    async def test_connection(self) -> bool:
        """Test the OpenRouter API connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = await self._make_request("Hello, world!", max_tokens=5)
            if response and "choices" in response:
                logger.info("OpenRouter API connection successful")
                return True
            else:
                logger.error("OpenRouter API connection failed - no valid response")
                return False

        except Exception as e:
            logger.error(f"OpenRouter connection test failed: {e}")
            return False

    async def fetch_article_content(self, url: str) -> str:
        """Fetch and extract clean article content from URL."""
        try:
            await self._rate_limit_delay()

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")

                        # Remove script, style, nav, footer, ads
                        for tag in soup(
                            ["script", "style", "nav", "footer", "aside", "iframe"]
                        ):
                            tag.decompose()

                        # Try to find article content
                        article_content = None
                        for selector in [
                            "article",
                            ".article-content",
                            ".post-content",
                            ".entry-content",
                            "main",
                        ]:
                            content = soup.select_one(selector)
                            if content:
                                article_content = content.get_text(strip=True)
                                break

                        if not article_content:
                            # Fallback to body content
                            article_content = soup.get_text(strip=True)

                        # Clean up the text
                        article_content = re.sub(r"\s+", " ", article_content)
                        article_content = re.sub(r"\n+", "\n", article_content)

                        # Limit length for LLM processing
                        if len(article_content) > 8000:
                            article_content = article_content[:8000] + "..."

                        return article_content
                    else:
                        logger.warning(f"Failed to fetch article: {response.status}")
                        return ""

        except Exception as e:
            logger.error(f"Error fetching article content: {e}")
            return ""

    async def generate_commentary(
        self, article_content: str, user_highlights: str, article_title: str = ""
    ) -> str:
        """Generate commentary on article using user highlights as editorial angle."""
        if not self.api_key:
            return user_highlights  # Fallback to highlights

        try:
            prompt = f"""You are a skilled newsletter writer. Read this article and write a thoughtful commentary using the provided user highlights as your editorial angle and key insights.

ARTICLE TITLE: {article_title}

ARTICLE CONTENT:
{article_content[:3000]}

USER'S KEY INSIGHTS/HIGHLIGHTS:
{user_highlights}

TASK: Write a 2-3 paragraph commentary that:
1. Incorporates the user's specific insights and statistics
2. Uses the user's analytical angle (e.g. "silent revolt", "cultural shift")
3. Provides thoughtful analysis beyond just restating facts
4. Sounds like an informed editorial take, not a news summary
5. Keep it under 300 words for newsletter brevity

Write the commentary:"""

            response = await self._make_request(prompt, max_tokens=200, temperature=0.7)
            if response and "choices" in response and len(response["choices"]) > 0:
                commentary = response["choices"][0]["message"]["content"].strip()
                return commentary
            else:
                return user_highlights  # Fallback

        except Exception as e:
            logger.error(f"Error generating commentary: {e}")
            return user_highlights  # Fallback

    async def editorial_roast(
        self, content: str, content_type: str = "article"
    ) -> Dict[str, Any]:
        """Editorial agent that 'roasts' content and provides improvement feedback."""
        if not self.api_key:
            return {"approved": True, "feedback": "No editor available", "score": 7}

        try:
            if content_type == "article":
                prompt = f"""You are a tough but fair newsletter editor. Your job is to ROAST this article commentary and provide brutal but constructive feedback.

COMMENTARY TO REVIEW:
{content}

EVALUATE:
1. Does it have a clear, compelling angle?
2. Is it insightful beyond basic facts?
3. Does it sound engaging and editorial (not generic news)?
4. Is it well-written and flow well?
5. Would subscribers find this worth their time?

Provide a ROAST with specific feedback. Rate 1-10 (7+ passes). Be tough - mediocre content gets rejected.

Format: SCORE: X/10\nFEEDBACK: [your brutal but constructive roast]\nAPPROVED: YES/NO"""
            else:  # newsletter
                prompt = f"""You are a tough newsletter editor reviewing the full newsletter. ROAST this newsletter and provide brutal feedback on overall quality, flow, and reader value.

NEWSLETTER TO REVIEW:
{content[:2000]}...

EVALUATE:
1. Overall quality and coherence
2. Mix of content and categories
3. Editorial voice and consistency
4. Reader engagement and value
5. Professional newsletter standards

Provide a ROAST with specific feedback. Rate 1-10 (8+ passes for full newsletter). Be merciless.

Format: SCORE: X/10\nFEEDBACK: [your comprehensive roast]\nAPPROVED: YES/NO"""

            response = await self._make_request(prompt, max_tokens=150, temperature=0.8)
            if response and "choices" in response and len(response["choices"]) > 0:
                review = response["choices"][0]["message"]["content"].strip()

                # Parse the review
                score_match = re.search(r"SCORE:\s*(\d+)", review)
                approved_match = re.search(
                    r"APPROVED:\s*(YES|NO)", review, re.IGNORECASE
                )
                feedback_match = re.search(
                    r"FEEDBACK:\s*(.+?)(?=APPROVED:|$)", review, re.DOTALL
                )

                score = int(score_match.group(1)) if score_match else 5
                approved = (
                    approved_match.group(1).upper() == "YES"
                    if approved_match
                    else score >= 7
                )
                feedback = feedback_match.group(1).strip() if feedback_match else review

                return {
                    "approved": approved,
                    "feedback": feedback,
                    "score": score,
                    "raw_review": review,
                }
            else:
                return {"approved": True, "feedback": "Editor unavailable", "score": 7}

        except Exception as e:
            logger.error(f"Error in editorial review: {e}")
            return {"approved": True, "feedback": f"Editor error: {e}", "score": 7}

    async def revise_content(
        self,
        original_content: str,
        editor_feedback: str,
        article_content: str = "",
        user_highlights: str = "",
    ) -> str:
        """Revise content based on editor feedback."""
        if not self.api_key:
            return original_content

        try:
            prompt = f"""You are a newsletter writer revising your work based on tough editorial feedback.

ORIGINAL CONTENT:
{original_content}

EDITOR'S FEEDBACK:
{editor_feedback}

ARTICLE CONTEXT: {article_content[:1000] if article_content else 'N/A'}
USER INSIGHTS: {user_highlights if user_highlights else 'N/A'}

TASK: Rewrite the content addressing ALL the editor's concerns. Make it sharper, more insightful, and more engaging. Keep under 300 words.

Revised content:"""

            response = await self._make_request(prompt, max_tokens=200, temperature=0.6)
            if response and "choices" in response and len(response["choices"]) > 0:
                revised = response["choices"][0]["message"]["content"].strip()
                return revised
            else:
                return original_content

        except Exception as e:
            logger.error(f"Error revising content: {e}")
            return original_content

    async def detect_user_commentary(self, content: str, title: str = "") -> bool:
        """Use LLM to detect if content contains user commentary/insights that should trigger editorial workflow."""
        if not self.api_key:
            return False

        try:
            prompt = f"""Analyze this RSS feed content to determine if it contains personal commentary, insights, or reactions from the user.

TITLE: {title}
CONTENT: {content}

Look for:
- Personal opinions or reactions ("fuck, still need exercise", "damn this is good")
- Informal commentary or notes
- Emotional responses or personal reflections
- User's own insights or takeaways
- Casual/informal language suggesting personal thoughts

Ignore:
- Pure article excerpts or formal summaries
- Generic descriptions without personal opinion
- Purely informational content

Respond with only: YES (contains user commentary) or NO (pure article content)"""

            response = await self._make_request(prompt, max_tokens=5, temperature=0.1)
            if response and "choices" in response and len(response["choices"]) > 0:
                result = response["choices"][0]["message"]["content"].strip().upper()
                return result == "YES"
            else:
                return False

        except Exception as e:
            logger.error(f"Error detecting user commentary: {e}")
            return False
