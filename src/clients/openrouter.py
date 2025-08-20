"""OpenRouter API client for AI processing and content enhancement."""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API to process content with free models."""

    def __init__(self, api_key: str, model: str = None, settings=None):
        """Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key
            model: Model to use (defaults to Venice if not specified)
            settings: Settings instance for configuration values
        """
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://thefilter.buttondown.email",  # Required by OpenRouter
            "X-Title": "The Filter Newsletter",  # Optional title
        }
        # Use free models only - default to OpenRouter's Venice model
        import os

        # Best free models prioritized by quality and reliability
        self.model_fallbacks = [
            "openai/gpt-4o-mini",  # Best overall free model
            "google/gemini-flash-1.5-8b",  # Fast and capable
            "meta-llama/llama-3.2-90b-vision-instruct:free",  # Strong reasoning
            "meta-llama/llama-3.2-11b-vision-instruct:free",  # Good balance
            "cognitivecomputations/dolphin-mistral-7b:free",  # Reliable fallback
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # Original default
        ]

        self.default_model = model or os.getenv(
            "OPENROUTER_MODEL",
            self.model_fallbacks[0],  # Use best model as default
        )

        # Rate limiting configuration - use settings if provided, fallback to defaults
        self.last_request_time = 0
        if settings:
            self.min_request_interval = settings.openrouter_min_request_interval
            self.max_backoff_multiplier = settings.openrouter_max_backoff_multiplier
            self.max_consecutive_failures = settings.openrouter_max_consecutive_failures
            self.timeout = settings.openrouter_timeout
        else:
            # Fallback to hardcoded defaults for backward compatibility
            self.min_request_interval = (
                3.2  # 3.2 seconds = ~18.75 requests/minute (safe buffer)
            )
            self.max_backoff_multiplier = 8.0
            self.max_consecutive_failures = 5
            self.timeout = 30.0

        self.consecutive_failures = 0
        self.backoff_multiplier = 1.0

    async def enhance_content_summary(
        self, title: str, content: str, max_length: int = 400
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
            prompt = f"""Write a clear, factual summary of this article for a newsletter. Focus on complete thoughts and professional reporting.

Title: {title}
Content: {content[:600]}

REQUIREMENTS:
- Write in third person, factual tone
- Start with the main fact or development
- Explain what happened and why it matters
- Write in complete paragraphs with full sentences
- Maximum {max_length} characters
- No conversational phrases, questions, or engagement tactics
- No truncated thoughts or incomplete sentences
- Professional news reporting style only
- End with complete sentences, never with "..." or mid-thought

Summary:"""

            response = await self._make_request(
                prompt, max_tokens=150
            )  # Allow longer summaries for complete sentences
            if response and "choices" in response and len(response["choices"]) > 0:
                summary = response["choices"][0]["message"]["content"].strip()

                # Remove common AI artifacts and unwanted phrases
                unwanted_phrases = [
                    "I'll never tire of hearing",
                    "I couldn't help but",
                    "It's a fascinating",
                    "What's interesting",
                    "What makes this",
                    "Here's what",
                    "Let me tell you",
                    "Picture this",
                    "Imagine if",
                ]

                # Check for critical AI refusal patterns first
                refusal_patterns = [
                    "I cannot fulfill your request",
                    "I am just an AI model",
                    "I can't provide assistance",
                    "I cannot create content",
                    "it is not within my programming",
                    "ethical guidelines",
                    "I'm unable to",
                    "I cannot help with",
                    "I'm not able to",
                    "As an AI",
                    "I'm an AI",
                    "particularly when it involves",
                ]

                # If content contains refusal patterns, reject it entirely
                summary_lower = summary.lower()
                for pattern in refusal_patterns:
                    if pattern.lower() in summary_lower:
                        logger.warning(f"AI refusal detected in summary: {pattern}")
                        return content[:max_length]  # Return original content instead

                for phrase in unwanted_phrases:
                    if summary.lower().startswith(phrase.lower()):
                        # Find the first sentence after the unwanted opening
                        sentences = summary.split(". ")
                        if len(sentences) > 1:
                            summary = ". ".join(sentences[1:])
                        break

                # Preserve complete thoughts - only truncate if absolutely necessary
                if len(summary) > max_length:
                    # Split into sentences
                    import re

                    sentences = re.split(r"(?<=[.!?])\s+", summary)
                    truncated = ""

                    for sentence in sentences:
                        # Allow more generous space for complete thoughts
                        if len(truncated + sentence) <= max_length - 5:
                            truncated += sentence + " "
                        else:
                            break

                    # Clean up and ensure proper ending
                    summary = truncated.strip()
                    # Only add period if we have content and it doesn't end properly
                    if summary and not summary.endswith((".", "!", "?")):
                        summary += "."

                    # If truncation resulted in too short content, keep more of original
                    if (
                        len(summary) < max_length * 0.7
                    ):  # Less than 70% of allowed space
                        summary = (
                            summary[: max_length - 3] + "..."
                            if len(summary) > max_length
                            else summary
                        )

                return summary
            else:
                logger.warning("OpenRouter returned no content")
                return content[:max_length]

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error enhancing content with OpenRouter: {e}")
            return content[:max_length]
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error in content enhancement: {e}")
            return content[:max_length]
        except Exception as e:
            logger.error(f"Unexpected error enhancing content with OpenRouter: {e}")
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

Choose the most appropriate category. Respond with ONLY ONE WORD: technology, society, art, or business."""

            response = await self._make_request(prompt, max_tokens=10)
            if response and "choices" in response and len(response["choices"]) > 0:
                category = response["choices"][0]["message"]["content"].strip().lower()

                # Clean up common AI formatting issues
                category = category.replace("**", "").replace(
                    "*", ""
                )  # Remove markdown
                category = category.replace(
                    ":", ""
                ).strip()  # Remove colons and extra spaces
                category = (
                    category.split()[-1] if category.split() else ""
                )  # Take last word if multiple

                # Validate category
                valid_categories = ["technology", "society", "art", "business"]
                if category in valid_categories:
                    return category
                else:
                    logger.warning(f"AI returned invalid category: {category}")
                    return self._fallback_categorize(title, content, tags)
            else:
                return self._fallback_categorize(title, content, tags)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error categorizing content with OpenRouter: {e}")
            return self._fallback_categorize(title, content, tags)
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error in content categorization: {e}")
            return self._fallback_categorize(title, content, tags)
        except Exception as e:
            logger.error(f"Unexpected error categorizing content with OpenRouter: {e}")
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

        return max(scores, key=lambda k: scores[k]) or "society"

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
        self,
        prompt: str,
        max_tokens: int = 100,
        temperature: float = 0.3,
        model: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a request to OpenRouter API with model fallback.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            model: Specific model to use (overrides default)

        Returns:
            API response or None if failed
        """
        # Try models in order of preference
        models_to_try = (
            [model] if model else [self.default_model] + self.model_fallbacks
        )

        for attempt_model in models_to_try:
            if (
                attempt_model in [self.default_model] + self.model_fallbacks
            ):  # Only try known good models
                try:
                    payload = {
                        "model": attempt_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": False,
                    }

                    result = await self._make_single_request(payload)
                    if result:
                        if attempt_model != self.default_model:
                            logger.info(f"Using fallback model: {attempt_model}")
                        return result
                except Exception as e:
                    logger.warning(f"Model {attempt_model} failed: {e}")
                    continue

        logger.error("All models failed")
        return None

    async def make_parallel_requests(
        self, requests: List[Dict[str, Any]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Make multiple API requests in parallel for faster processing.

        Args:
            requests: List of request configs with keys: prompt, max_tokens, temperature

        Returns:
            List of responses in same order as requests (None for failed requests)
        """
        # Create semaphore to limit concurrent requests (avoid rate limits)
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests

        async def limited_request(request_config):
            async with semaphore:
                return await self._make_request(**request_config)

        # Execute all requests in parallel
        tasks = [limited_request(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to None for consistent return type
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Parallel request failed: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    async def _make_single_request(
        self, payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Make a single request to OpenRouter API.

        Args:
            payload: Request payload

        Returns:
            API response or None if failed
        """

        try:
            # Rate limiting to avoid 429 errors
            await self._rate_limit_delay()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
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
                            self.max_backoff_multiplier, 2.0**self.consecutive_failures
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

        except aiohttp.ClientResponseError as e:
            # Handle HTTP errors including rate limiting
            if e.status == 429:
                logger.warning(
                    f"OpenRouter rate limit hit (HTTP {e.status}), will retry with longer delay: {e}"
                )
                await asyncio.sleep(10)  # Wait 10 seconds on rate limit
                return None
            else:
                logger.error(f"HTTP error from OpenRouter API: {e.status} - {e}")
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error in OpenRouter API request: {e}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error in OpenRouter API response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in OpenRouter API request: {e}")
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

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error testing OpenRouter connection: {e}")
            return False
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Response parsing error testing OpenRouter connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing OpenRouter connection: {e}")
            return False

    async def generate_text(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text using OpenRouter API.

        Args:
            prompt: Input prompt for text generation
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response

        Raises:
            Exception: If generation fails
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        try:
            response = await self._make_request(prompt, max_tokens=max_tokens)

            if response and "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0].get("message", {}).get("content", "")
                if content:
                    return content.strip()
                else:
                    raise ValueError("Empty response from OpenRouter API")
            else:
                raise ValueError("Invalid response format from OpenRouter API")

        except Exception as e:
            logger.error(f"Failed to generate text with OpenRouter: {e}")
            raise

    async def fetch_article_content(self, url: str) -> str:
        """Fetch and extract clean article content from URL."""
        try:
            await self._rate_limit_delay()

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 200:
                        # Handle potential encoding issues gracefully
                        try:
                            html = await response.text()
                        except UnicodeDecodeError:
                            # Try with latin-1 encoding for problematic content
                            raw_content = await response.read()
                            html = raw_content.decode("latin-1", errors="ignore")
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

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error fetching article content: {e}")
            return ""
        except (ValueError, TypeError) as e:
            logger.error(f"Data processing error fetching article content: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error fetching article content: {e}")
            return ""

    async def generate_commentary(
        self, article_content: str, user_highlights: str, article_title: str = ""
    ) -> str:
        """Generate commentary using three-phase AI workflow: fact extraction → content generation → validation."""
        if not self.api_key:
            return user_highlights  # Fallback to highlights

        try:
            # Phase 1: Fact Extraction
            facts_prompt = f"""Extract ONLY concrete, verifiable facts from this article. No interpretations, no editorial spin.

ARTICLE: {article_title}
CONTENT: {article_content[:2000]}

Return facts as a bulleted list. Include specific numbers, names, dates, locations, survey results, drug names, etc.
Example format:
• Specific fact 1 (with number/name/date)
• Specific fact 2 (with concrete detail)
• Specific fact 3 (with precise information)

CRITICAL: Only facts that appear in the source material. No summaries or interpretations."""

            facts_response = await self._make_request(
                facts_prompt, max_tokens=150, temperature=0.2
            )
            facts = ""
            if (
                facts_response
                and "choices" in facts_response
                and len(facts_response["choices"]) > 0
            ):
                facts = facts_response["choices"][0]["message"]["content"].strip()

            # Phase 2: Content Generation
            content_prompt = f"""You are the editor of The Filter, a minimalist newsletter. Write sharp editorial commentary.

VERIFIED FACTS: {facts}

USER HIGHLIGHTS: {user_highlights}

VOICE RULES:
- Tone: minimalist, sharp, contemplative
- Mix facts with light editorial bite
- Occasional dry irony or existential framing  
- ABSOLUTELY AVOID: "Imagine a world...", "game-changer", "breakthrough", "protocol", "antifragility"
- Channel: signal over noise, clarity over hype, skeptical of easy narratives

TASK: Write 2-3 sentences that:
- Start with factual core from verified facts
- Filter through user highlights as "what matters most"  
- End with significance (often skeptical, philosophical, systems-oriented)
- IMPORTANT: Write in third person - never use "I", "we", "my"

Examples:
- User highlight "still need exercise" → The FDA approved eye drops for near vision, but the real constraint isn't technology - it's that daily habits resist elegant solutions
- User highlight "privacy nightmare" → Companies harvest behavioral data with surgical precision, yet privacy law moves like continental drift

Keep under 300 words with a conversational, editorial tone in third person."""

            content_response = await self._make_request(
                content_prompt, max_tokens=200, temperature=0.7
            )
            commentary = ""
            if (
                content_response
                and "choices" in content_response
                and len(content_response["choices"]) > 0
            ):
                commentary = content_response["choices"][0]["message"][
                    "content"
                ].strip()

            # Phase 3: Validation
            if commentary:
                validation_prompt = f"""Review this commentary for template contamination and quality.

COMMENTARY: {commentary}

Check for:
1. Contains forbidden phrases: "Imagine a world", "protocol", "antifragility", "game-changer"
2. Uses first person (I, we, my) instead of third person
3. Contains made-up facts not in original article
4. Sounds generic/templated vs. specific to this article

Return: APPROVED or REJECTED with brief reason."""

                validation_response = await self._make_request(
                    validation_prompt, max_tokens=50, temperature=0.1
                )
                if validation_response and "choices" in validation_response:
                    validation = validation_response["choices"][0]["message"][
                        "content"
                    ].strip()
                    if "REJECTED" in validation:
                        logger.warning(
                            f"Commentary rejected by validation: {validation}"
                        )
                        return user_highlights  # Fallback if validation fails

            return commentary if commentary else user_highlights

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error generating commentary: {e}")
            return user_highlights  # Fallback
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error generating commentary: {e}")
            return user_highlights  # Fallback
        except Exception as e:
            logger.error(f"Unexpected error generating commentary: {e}")
            return user_highlights  # Fallback

    async def editorial_roast(
        self, content: str, content_type: str = "article"
    ) -> Dict[str, Any]:
        """Editorial agent that 'roasts' content and provides improvement feedback."""
        if not self.api_key:
            return {"approved": True, "feedback": "No editor available", "score": 7}

        try:
            if content_type == "article":
                prompt = f"""You are a tough but fair newsletter editor using journalism best practices. ROAST this article commentary with constructive feedback.

COMMENTARY TO REVIEW:
{content}

EVALUATE USING JOURNALISM STANDARDS:
1. ENGAGEMENT: Does it start with a compelling hook or thought-provoking question?
2. INSIGHT: Goes beyond basic facts to provide unique perspective?
3. STORYTELLING: Uses conversational tone with narrative elements?
4. CRITICAL THINKING: Challenges conventional thinking or raises important questions?
5. READER VALUE: Would informed subscribers find this worth their time?
6. STRUCTURE: Clear flow from hook to analysis to thought-provoking conclusion?

Provide specific feedback on:
- What journalism techniques are missing
- How to improve engagement and readability
- Suggestions for better storytelling elements
- Ways to add more thought-provoking content

Rate 1-10 (7+ passes). Be constructively critical - provide actionable advice for improvement:

Format: SCORE: X/10\nFEEDBACK: [your brutal but constructive roast with specific suggestions for improvement]\nAPPROVED: YES/NO"""
            else:  # newsletter
                prompt = f"""You are a tough newsletter editor applying journalism best practices. ROAST this full newsletter with constructive feedback.

NEWSLETTER TO REVIEW:
{content[:2000]}...

EVALUATE USING JOURNALISM STANDARDS:
1. OVERALL ENGAGEMENT: Does it attract and retain reader attention throughout?
2. CONTENT MIX: Balanced variety with strong editorial voice?
3. STORYTELLING: Uses narrative elements and conversational tone?
4. CRITICAL THINKING: Challenges readers with thought-provoking content?
5. READER VALUE: Provides unique insights beyond basic news?
6. STRUCTURE: Clear flow with compelling hooks and satisfying conclusions?

Provide specific feedback on:
- How to improve overall reader engagement
- Missing journalism techniques (storytelling, questioning, etc.)
- Opportunities for more thought-provoking content
- Ways to strengthen editorial voice and coherence

Rate 1-10 (8+ passes for full newsletter). Be constructively critical with actionable advice:

Format: SCORE: X/10\nFEEDBACK: [comprehensive feedback with specific journalism improvements]\nAPPROVED: YES/NO"""

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
                    else score >= 6  # Lowered threshold from 7 to 6
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

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error in editorial review: {e}")
            return {"approved": True, "feedback": f"Network error: {e}", "score": 7}
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error in editorial review: {e}")
            return {"approved": True, "feedback": f"Parsing error: {e}", "score": 7}
        except Exception as e:
            logger.error(f"Unexpected error in editorial review: {e}")
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
            # Check if we have user highlights to incorporate
            has_user_context = user_highlights and len(user_highlights.strip()) > 20
            context_section = (
                f"USER INSIGHTS: {user_highlights}"
                if has_user_context
                else "USER CONTEXT: This is curated content from the user's RSS feed"
            )

            prompt = f"""You are the editor of The Filter, rewriting content to match the publication's voice. Apply editorial feedback precisely.

ORIGINAL CONTENT:
{original_content}

EDITOR'S FEEDBACK:
{editor_feedback}

ARTICLE CONTEXT: {article_content[:1000] if article_content else 'N/A'}
{context_section}

VOICE RULES:
- Tone: minimalist, sharp, contemplative
- Mix facts with light editorial bite
- Occasional dry irony or existential framing
- AVOID clichés: "Imagine a world...", "game-changer", "breakthrough" 
- Channel: signal over noise, clarity over hype, skeptical of easy narratives

REWRITE GUIDELINES:
- Start with factual core (no inventions)
- Use concrete, specific language over abstract concepts
- End with philosophical or systems-oriented significance
- Cut filler - every word must earn its place
- Write in third person about what the article/research reveals
- {"Draw editorial insights from the user's perspective but write in third person" if has_user_context else "Develop a unique editorial angle in third person"}
- CRITICAL: Always write about articles/topics in third person, describing what authors/experts discuss

Implement ALL editor suggestions. Make it engaging content that attracts and retains readership. Keep under 300 words."

Create substantially improved content using journalism best practices:"""

            response = await self._make_request(prompt, max_tokens=200, temperature=0.6)
            if response and "choices" in response and len(response["choices"]) > 0:
                revised = response["choices"][0]["message"]["content"].strip()
                return revised
            else:
                return original_content

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error revising content: {e}")
            return original_content
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error revising content: {e}")
            return original_content
        except Exception as e:
            logger.error(f"Unexpected error revising content: {e}")
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

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error detecting user commentary: {e}")
            return False
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error detecting user commentary: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error detecting user commentary: {e}")
            return False

    async def assess_content_quality(
        self, content: str, content_type: str = "article"
    ) -> Dict[str, Any]:
        """Assess content quality using journalism best practices rubric."""
        if not self.api_key:
            return {
                "overall_score": 7,
                "engagement_score": 7,
                "insight_score": 7,
                "storytelling_score": 7,
                "suggestions": [
                    "No quality assessment available - OpenRouter API key not configured"
                ],
                "strengths": ["Content present"],
                "areas_for_improvement": [],
            }

        try:
            prompt = f"""You are a journalism quality assessor. Evaluate this {content_type} content using professional journalism standards.

CONTENT TO ASSESS:
{content}

JOURNALISM QUALITY RUBRIC (Rate each 1-10):

1. ENGAGEMENT (Hook & Reader Retention):
- Compelling opening that draws readers in
- Thought-provoking questions or hooks
- Maintains interest throughout

2. INSIGHT (Analysis & Perspective):
- Goes beyond surface-level facts
- Provides unique or challenging perspectives
- Explains WHY this matters to readers

3. STORYTELLING (Narrative & Flow):
- Uses conversational tone
- Incorporates narrative elements
- Clear structure and flow

4. CRITICAL THINKING (Depth & Questions):
- Challenges conventional thinking
- Raises important questions
- Encourages reader reflection

Provide detailed assessment in this format:
ENGAGEMENT_SCORE: X/10
INSIGHT_SCORE: X/10
STORYTELLING_SCORE: X/10
CRITICAL_THINKING_SCORE: X/10
OVERALL_SCORE: X/10

STRENGTHS: [List 2-3 specific strengths]
AREAS_FOR_IMPROVEMENT: [List 2-3 specific areas needing work]
SUGGESTIONS: [3-4 actionable suggestions for improvement]"""

            response = await self._make_request(prompt, max_tokens=200, temperature=0.3)
            if response and "choices" in response and len(response["choices"]) > 0:
                assessment = response["choices"][0]["message"]["content"].strip()

                # Parse the structured response
                parsed = self._parse_quality_assessment(assessment)
                return parsed
            else:
                return self._default_quality_assessment()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error assessing content quality: {e}")
            return self._default_quality_assessment()
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error assessing content quality: {e}")
            return self._default_quality_assessment()
        except Exception as e:
            logger.error(f"Unexpected error assessing content quality: {e}")
            return self._default_quality_assessment()

    def _parse_quality_assessment(self, assessment: str) -> Dict[str, Any]:
        """Parse structured quality assessment response."""
        import re

        try:
            # Extract scores
            engagement = re.search(r"ENGAGEMENT_SCORE:\s*(\d+)", assessment)
            insight = re.search(r"INSIGHT_SCORE:\s*(\d+)", assessment)
            storytelling = re.search(r"STORYTELLING_SCORE:\s*(\d+)", assessment)
            critical_thinking = re.search(
                r"CRITICAL_THINKING_SCORE:\s*(\d+)", assessment
            )
            overall = re.search(r"OVERALL_SCORE:\s*(\d+)", assessment)

            # Extract text sections
            strengths = re.search(r"STRENGTHS:\s*\[(.*?)\]", assessment, re.DOTALL)
            improvements = re.search(
                r"AREAS_FOR_IMPROVEMENT:\s*\[(.*?)\]", assessment, re.DOTALL
            )
            suggestions = re.search(r"SUGGESTIONS:\s*\[(.*?)\]", assessment, re.DOTALL)

            return {
                "engagement_score": int(engagement.group(1)) if engagement else 7,
                "insight_score": int(insight.group(1)) if insight else 7,
                "storytelling_score": int(storytelling.group(1)) if storytelling else 7,
                "critical_thinking_score": (
                    int(critical_thinking.group(1)) if critical_thinking else 7
                ),
                "overall_score": int(overall.group(1)) if overall else 7,
                "strengths": (
                    [s.strip() for s in strengths.group(1).split(",")]
                    if strengths
                    else []
                ),
                "areas_for_improvement": (
                    [s.strip() for s in improvements.group(1).split(",")]
                    if improvements
                    else []
                ),
                "suggestions": (
                    [s.strip() for s in suggestions.group(1).split(",")]
                    if suggestions
                    else []
                ),
            }
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"JSON parsing error in quality assessment: {e}")
            return self._default_quality_assessment()
        except Exception as e:
            logger.error(f"Unexpected error parsing quality assessment: {e}")
            return self._default_quality_assessment()

    def _default_quality_assessment(self) -> Dict[str, Any]:
        """Return default quality assessment when parsing fails."""
        return {
            "engagement_score": 7,
            "insight_score": 7,
            "storytelling_score": 7,
            "critical_thinking_score": 7,
            "overall_score": 7,
            "strengths": ["Content is present and readable"],
            "areas_for_improvement": [
                "Could enhance engagement",
                "Could add more insight",
            ],
            "suggestions": [
                "Add compelling hooks",
                "Include thought-provoking questions",
                "Use more conversational tone",
            ],
        }

    async def improve_title(self, current_title: str, content: str) -> str:
        """Improve content title based on content."""
        if not self.api_key:
            return current_title

        try:
            prompt = f"""Improve this article title to be more engaging and specific based on the content.

CURRENT TITLE: {current_title}
CONTENT: {content[:500]}

Write a better title that:
- Is specific and descriptive
- Captures the main news/development
- Is compelling but not clickbait
- Under 80 characters
- Uses active voice when possible

Return ONLY the improved title, no explanations:"""

            response = await self._make_request(prompt, max_tokens=50, temperature=0.4)
            if response and "choices" in response and len(response["choices"]) > 0:
                improved_title = response["choices"][0]["message"]["content"].strip()
                # Remove quotes if AI added them
                improved_title = improved_title.strip("\"'")

                # Basic validation - title should be reasonable length and not empty
                if 10 <= len(improved_title) <= 120 and not any(
                    pattern in improved_title.lower()
                    for pattern in [
                        "i cannot",
                        "i am just an ai",
                        "as an ai",
                        "i'm unable to",
                    ]
                ):
                    return improved_title
                else:
                    logger.debug(
                        f"AI returned invalid title: '{improved_title}', keeping original"
                    )
                    return current_title
            else:
                return current_title

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"Network error improving title: {e}")
            return current_title
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Data parsing error improving title: {e}")
            return current_title
        except Exception as e:
            logger.error(f"Unexpected error improving title: {e}")
            return current_title
