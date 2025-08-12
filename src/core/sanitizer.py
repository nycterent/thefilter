"""Content sanitization and validation utilities."""

import logging
import re
from typing import Dict, List, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ContentSanitizer:
    """Handles content sanitization, validation, and quality checks."""

    # AI refusal patterns to detect and remove - comprehensive coverage
    AI_REFUSAL_PATTERNS = [
        # Direct refusal phrases
        r"I can't provide information or guidance on harmful or illegal activities",
        r"I can't provide information or guidance on illegal or harmful activities",
        r"I cannot help with that request",
        r"I'm not able to assist with",
        r"I cannot provide information that could be used to harm",
        r"I'm sorry, but I can't help with",
        r"As an AI assistant, I cannot",
        r"I don't feel comfortable",
        r"I cannot and will not provide",
        r"I'm not able to provide",
        r"I cannot assist with",
        r"I'm unable to help",
        r"I can't help with",
        r"I can't provide assistance",
        r"I don't have the ability to",
        r"I am just an AI model",
        r"not within my programming",
        r"particularly when it involves minors",
        r"contains or promotes harmful, illegal, or adult material",
        # Common refusal variations found in production
        r"I cannot fulfill your request",
        r"I can't fulfill your request",
        r"lfill your request",  # Truncated version
        r"I'll never tire of hearing.*but.*",  # Fake engagement followed by refusal
        r"I couldn't help but.*",  # Another fake engagement pattern
        r"ethical guidelines",
        r"programming or ethical",
        r"or ethical guidelines",
        r"harmful, illegal, or adult",
        r"I can't provide assistance with creating",
        r"I cannot provide assistance with creating",
        r"I'm not able to create",
        r"I don't have access to",
        r"As an AI language model",
        r"I'm an AI and",
        # Catch partial/truncated refusals that appear in newsletters
        r"(?:^|\.)\s*[A-Z][a-z]*\s+(?:can't|cannot|won't|will not|refuse|unable)",
        r"(?:I|We)\s+(?:apologize|regret).*(?:cannot|can't|unable)",
    ]

    # Prompt leakage patterns
    PROMPT_LEAKAGE_PATTERNS = [
        r"hint to ai:",
        r"HINT TO AI:",
        r"instruction:",
        r"INSTRUCTION:",
        r"system:",
        r"SYSTEM:",
        r"prompt:",
        r"PROMPT:",
        r"task:",
        r"TASK:",
        r"write a",
        r"generate a",
        r"create a",
    ]

    # CDN and proxy domains to canonicalize - comprehensive list
    PROXY_DOMAINS = {
        "feedbinusercontent.com",
        "substackcdn.com",
        "eotrx.substackcdn.com",
        "readwise.io",
        "cdn.substack.com",
        "medium.com/_/stat",
        "mailchimp.com",
        "list-manage.com",
        "us-east-1.amazonaws.com",
        "cloudfront.net",
        "wp.com",
        # Additional tracking and proxy domains
        "track.click",
        "click.track",
        "redirect.feedbin",
        "proxy.feedbin",
    }

    # Mapping of known proxy patterns to extraction methods
    CANONICALIZATION_PATTERNS = {
        "feedbinusercontent.com": "extract_from_feedbin",
        "substackcdn.com": "extract_from_substack",
        "list-manage.com": "extract_from_mailchimp",
        "track.click": "extract_from_query_param",
        "readwise.io": "extract_from_readwise",
    }

    def __init__(self) -> None:
        self.refusal_regex = re.compile(
            "|".join(self.AI_REFUSAL_PATTERNS), re.IGNORECASE
        )
        self.prompt_leak_regex = re.compile(
            "|".join(self.PROMPT_LEAKAGE_PATTERNS), re.IGNORECASE
        )

    def sanitize_text(self, text: str, context: str = "") -> Tuple[str, List[str]]:
        """
        Sanitize text content, removing AI refusals and prompt leakage.

        Returns:
            Tuple of (sanitized_text, list_of_issues_found)
        """
        if not text:
            return text, []

        issues = []
        # Store original for comparison if needed

        # Check for AI refusal strings with more aggressive removal
        refusal_matches = self.refusal_regex.findall(text)
        if refusal_matches:
            for match in refusal_matches:
                issues.append(f"AI refusal detected in {context}: '{match[:50]}...'")

            # More aggressive removal - split by sentences and paragraphs
            paragraphs = text.split("\n")
            clean_paragraphs = []

            for paragraph in paragraphs:
                # Split paragraph into sentences
                sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                clean_sentences = []

                for sentence in sentences:
                    # Skip entire sentence if it contains refusal patterns
                    if not self.refusal_regex.search(sentence):
                        clean_sentences.append(sentence)
                    else:
                        issues.append(f"Removed refusal sentence: '{sentence[:60]}...'")

                # Only keep paragraph if it has clean sentences
                clean_para = " ".join(clean_sentences).strip()
                if clean_para and not self.refusal_regex.search(clean_para):
                    clean_paragraphs.append(clean_para)

            text = "\n".join(clean_paragraphs)

        # Check for prompt leakage
        prompt_matches = self.prompt_leak_regex.findall(text)
        if prompt_matches:
            for match in prompt_matches:
                issues.append(f"Prompt leakage detected in {context}: '{match}'")
                # Remove the leaked prompt text
                text = self.prompt_leak_regex.sub("", text)

        # Additional cleanup for common AI artifacts
        # Remove incomplete sentences that start with common AI phrases
        ai_artifacts = [
            r"^\s*(?:I|We)\s+(?:understand|appreciate|recognize|acknowledge).*?(?:\.|$)",
            r"^\s*(?:It's|It is)\s+important to note.*?(?:\.|$)",
            r"^\s*(?:Please|Feel free to).*?(?:\.|$)",
            r"^\s*(?:However|Nevertheless|Nonetheless),?\s*I.*?(?:\.|$)",
        ]

        for pattern in ai_artifacts:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                issues.append(f"Removed AI artifact in {context}")
                text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

        # Clean up whitespace and formatting issues
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*\.\s*\.", ".", text)  # Fix double periods
        text = re.sub(r"^\s*\.\s*", "", text)  # Remove leading periods
        text = re.sub(r"\s*\.\s*$", ".", text)  # Ensure proper ending

        # If text is empty or too short after sanitization, mark as completely invalid
        if not text.strip() or len(text.strip()) < 10:
            issues.append(f"Content completely removed due to AI refusals in {context}")
            return "", issues

        return text, issues

    def validate_completeness(self, text: str, min_length: int = 10) -> List[str]:
        """Validate content fitness for survival in the information ecosystem."""
        issues = []

        if not text or len(text.strip()) < min_length:
            issues.append(
                f"Content too short for ecosystem survival: {len(text.strip())} chars (minimum: {min_length})"
            )
            return issues
            
        # Evolutionary fitness check - content must be self-sustaining
        # Check for adaptive traits that help content survive and replicate

        # Enhanced truncation detection - check for various incomplete patterns
        truncation_patterns = [
            r"\.{2,}$",  # Ends with two or more dots
            r"…$",  # Ends with ellipsis character
            r" $",  # Ends with space
            r"without a secon$",  # Specific pattern from 027
            r"their interp$",  # Specific pattern from 027
            r"perfectionism$",  # Incomplete word pattern
            r"harsh reali$",  # Specific pattern from 027
            r"has sl$",  # Specific pattern from 027
            r"\w+\.\.\.$",  # Word followed by three dots
            r"\w{1,5}$",  # Short incomplete word at end (1-5 chars)
            r":\s*$",  # Trailing colon with no continuation
            r"\([^\)]*$",  # Unclosed parenthesis at end
        ]

        for pattern in truncation_patterns:
            if re.search(pattern, text.strip()):
                issues.append(f"Content appears truncated: matches pattern '{pattern}'")
                break  # Only report first truncation pattern found

        # Check for evolutionary dead-ends - content that can't replicate/adapt
        evolutionary_dead_ends = [
            r"lorem ipsum",  # Placeholder DNA - no survival value
            r"placeholder",
            r"TODO", 
            r"FIXME",
            r"example\.com",
            r"test\d+",
            # AI-generated patterns that lack authentic replication fitness
            r"I couldn't help but chuckle",
            r"I'll never tire of hearing", 
            r"Best of ProductHunt",  # Generic content lacks uniqueness for survival
            r"Title:",  # Template artifacts show incomplete evolution
            r"The latest data from",  # Generic openings lack adaptive specificity
        ]

        for pattern in evolutionary_dead_ends:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Evolutionary dead-end detected - content lacks replication fitness: '{pattern}'")

        # Check for over-replication (genetic stagnation) - same phrase repeated
        words = text.lower().split()
        if len(words) > 5:
            # Look for genetic stagnation - phrases that replicate too much without variation
            for i in range(len(words) - 2):
                phrase = " ".join(words[i : i + 3])
                if text.lower().count(phrase) > 2:
                    issues.append(
                        f"Genetic stagnation - phrase over-replicates without variation: '{phrase}'"
                    )
                    break

        # Check for incomplete sentences

        # This duplicate check was already handled above in evolutionary_dead_ends

        return issues

    def assess_evolutionary_fitness(self, content: str) -> dict:
        """Assess content's evolutionary fitness for survival in the information ecosystem.
        
        Based on Tierra principles:
        - Replication potential (shareability, memorable phrases)
        - Adaptation capability (flexibility, contextual relevance) 
        - Competition fitness (uniqueness, value density)
        - Mutation resistance (core meaning preservation)
        """
        fitness_score = 100  # Start with perfect fitness
        fitness_factors = []
        
        # Replication potential - does content have traits that encourage sharing?
        replication_traits = [
            r"surprising",
            r"breakthrough", 
            r"first time",
            r"never before",
            r"reveals?",
            r"discovers?",
            r"uncover",
            r"behind the scenes",
            r"secret",
            r"exclusive",
        ]
        
        replication_count = sum(1 for trait in replication_traits 
                               if re.search(trait, content, re.IGNORECASE))
        if replication_count > 0:
            fitness_factors.append(f"High replication potential: {replication_count} viral traits")
        else:
            fitness_score -= 10
            fitness_factors.append("Low replication potential - lacks viral traits")
        
        # Adaptation capability - content that can survive context changes
        word_count = len(content.split())
        unique_words = len(set(content.lower().split()))
        lexical_diversity = unique_words / max(word_count, 1)
        
        if lexical_diversity > 0.7:
            fitness_factors.append("High adaptation potential - rich vocabulary")
        elif lexical_diversity < 0.4:
            fitness_score -= 15
            fitness_factors.append(f"Low adaptation potential - limited vocabulary diversity ({lexical_diversity:.2f})")
        
        # Competition fitness - uniqueness and information density
        sentence_count = len(re.split(r'[.!?]+', content))
        avg_sentence_length = word_count / max(sentence_count, 1)
        
        if 10 <= avg_sentence_length <= 25:  # Optimal information density
            fitness_factors.append("Optimal information density for competition")
        else:
            fitness_score -= 5
            fitness_factors.append(f"Suboptimal information density: {avg_sentence_length:.1f} words/sentence")
        
        # Mutation resistance - core meaning should be preserved through variations
        key_concepts = len(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content))  # Proper nouns
        if key_concepts >= 2:
            fitness_factors.append(f"Strong mutation resistance - {key_concepts} core concepts")
        else:
            fitness_score -= 10
            fitness_factors.append("Weak mutation resistance - few stable concepts")
        
        return {
            "fitness_score": max(0, fitness_score),
            "fitness_class": "highly_fit" if fitness_score >= 85 else
                            "moderately_fit" if fitness_score >= 70 else
                            "poorly_fit" if fitness_score >= 50 else "extinct",
            "factors": fitness_factors
        }

    def validate_headline(self, headline: str) -> List[str]:
        """Validate headline quality and consistency."""
        issues = []

        if not headline:
            issues.append("Missing headline")
            return issues

        # Check for placeholder headlines
        placeholder_headlines = [
            "untitled",
            "no title",
            "article",
            "post",
            "url",
            "link",
        ]

        if headline.lower().strip() in placeholder_headlines:
            issues.append(f"Placeholder headline: '{headline}'")

        # Check for overly generic headlines
        if len(headline.strip()) < 5:
            issues.append(f"Headline too short: '{headline}'")

        # Check for merged/garbled headlines (multiple story indicators)
        merged_indicators = [
            r"\.{3,}",  # Multiple dots suggesting concatenation
            r"[A-Z]{3,}\.\.\.[A-Z]{3,}",  # All caps with dots between
            r"WHO DOES NOT SEND.*COFFEE BADGING",  # Specific pattern from 027
            r"[A-Z\s]{10,}\.\.\.[A-Z\s]{10,}",  # Long caps strings with dots
            r"[A-Z]{2,}[^a-z]*,[^a-z]*[A-Z]{2,}",  # Two all-caps segments separated by comma
        ]

        for pattern in merged_indicators:
            if re.search(pattern, headline):
                issues.append(
                    f"Headline appears to merge multiple stories: '{headline}'"
                )
                break

        # Check for inconsistent casing
        if headline.isupper() and len(headline) > 30:
            issues.append(f"Headline is all caps (should be title case): '{headline}'")
        elif len(headline.split()) > 1 and all(
            word.islower() for word in headline.split()[:3]
        ):
            issues.append(f"Headline not properly capitalized: '{headline}'")

        # Check for inappropriate content in headlines
        profanity_patterns = [
            r"\bfuck\b",
            r"\bshit\b",
            r"\bbitch\b",
            r"\bdamn\b",
            r"\bass\b",
        ]

        for pattern in profanity_patterns:
            if re.search(pattern, headline, re.IGNORECASE):
                issues.append(
                    f"Headline contains potentially inappropriate language: '{headline}'"
                )
                break

        return issues

    def canonicalize_url(self, url: str) -> Tuple[str, List[str]]:
        """
        Attempt to canonicalize URLs, removing CDN/proxy domains.

        Returns:
            Tuple of (canonical_url, list_of_issues)
        """
        issues = []
        canonical_url = url

        if not url:
            return url, ["Empty URL provided"]

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check if it's a proxy/CDN domain and attempt canonicalization
            for proxy_domain in self.PROXY_DOMAINS:
                if proxy_domain in domain:
                    issues.append(f"CDN/proxy URL detected: {domain}")

                    # Attempt to extract canonical URL from common proxy patterns
                    canonical_candidate = self._extract_canonical_url(url, proxy_domain)
                    if canonical_candidate and canonical_candidate != url:
                        canonical_url = canonical_candidate
                        issues.append(
                            f"Canonicalized {proxy_domain} to: {canonical_candidate}"
                        )
                        break
                    elif canonical_candidate == "":
                        # Empty return means we should reject this URL entirely
                        canonical_url = ""
                        issues.append(
                            f"REJECTED non-canonical URL ({proxy_domain}): {url}"
                        )
                        break
                    else:
                        # If we can't canonicalize, at least flag it as non-canonical (WARNING level)
                        issues.append(f"Non-canonical URL ({proxy_domain}): {url}")
                        # Reduce severity - CDN URLs are common and sometimes necessary
                        if proxy_domain in [
                            "feedbinusercontent.com", 
                            "substackcdn.com",
                            "list-manage.com",
                        ]:
                            issues.append(
                                "WARNING: Using CDN URL - consider finding original source"
                            )

            # Validate URL structure
            parsed_canonical = urlparse(canonical_url)
            if not parsed_canonical.scheme or not parsed_canonical.netloc:
                issues.append(f"Invalid URL structure: {canonical_url}")

        except Exception as e:
            issues.append(f"URL parsing failed: {e}")

        return canonical_url, issues

    def _extract_canonical_url(self, proxy_url: str, proxy_domain: str) -> str:
        """
        Extract canonical URL from known proxy URL patterns.

        Enhanced extraction for common proxy services with better pattern matching.
        """
        from urllib.parse import parse_qs, unquote

        try:
            parsed_url = urlparse(proxy_url)

            # Feedbin proxy URLs - more aggressive extraction
            if "feedbinusercontent.com" in proxy_domain:
                # Try to extract from query parameters first
                query_params = parse_qs(parsed_url.query)
                if "url" in query_params:
                    return unquote(query_params["url"][0])

                # Fallback: look for domain patterns in path
                path_parts = parsed_url.path.strip("/").split("/")
                for part in path_parts:
                    # Look for parts that look like domains
                    if "." in part and len(part) > 4 and not part.isdigit():
                        # Common patterns: domain.com, www.domain.com
                        if part.count(".") >= 1 and not part.startswith("."):
                            return f"https://{part}"

            # Substack CDN URLs - extract publication domain
            elif "substackcdn.com" in proxy_domain or "substack.com" in proxy_domain:
                # Look for substack publication patterns
                if "/open" in parsed_url.path:
                    # These are often newsletter open tracking URLs
                    # Try to extract publication from subdomain or referrer
                    return proxy_url  # Keep as-is, it's likely a tracking URL

            # MailChimp / List-manage tracking URLs
            elif "list-manage.com" in proxy_domain:
                query_params = parse_qs(parsed_url.query)
                # Common MailChimp patterns
                if "u" in query_params or "url" in query_params:
                    for param in ["url", "u", "e"]:
                        if param in query_params:
                            candidate = unquote(query_params[param][0])
                            if candidate.startswith(("http://", "https://")):
                                return candidate

            # Readwise.io URLs - these are reader app URLs, try to preserve
            elif "readwise.io" in proxy_domain:
                # Readwise URLs like read.readwise.io/read/... are intentional
                # They provide a reading experience, so keep them
                return proxy_url

            # Generic query parameter extraction for tracking URLs
            else:
                query_params = parse_qs(parsed_url.query)
                # Common URL parameter names used by tracking services
                url_params = ["url", "target", "dest", "redirect", "link", "goto"]
                for param in url_params:
                    if param in query_params:
                        candidate = unquote(query_params[param][0])
                        if candidate.startswith(("http://", "https://")):
                            return candidate

            # If no extraction worked, return original
            return proxy_url

        except Exception as e:
            logger.debug(f"URL extraction failed for {proxy_url}: {e}")
            return proxy_url

        return proxy_url

    def validate_source_attribution(self, source_title: str, url: str) -> List[str]:
        """Validate source attribution quality."""
        issues = []

        # Check for placeholder source titles - expanded from 027 issues
        placeholder_sources = [
            "unknown",
            "unknown source",
            "newsletters",
            "starred articles",
            "url",
            "link",
            "source",
            "mailchimp",  # From 027 issues
        ]

        if not source_title or source_title.lower().strip() in placeholder_sources:
            issues.append(f"Placeholder source title: '{source_title}'")

        # Check for generic patterns like "Url3396" - comprehensive coverage
        url_patterns = [
            r"^url\d+$",
            r"^link\d+$",
            r"^source\d+$",
            r"^item\d+$",
            r"^ref\d+$",
            r"^article\d+$",
        ]

        for pattern in url_patterns:
            if source_title and re.match(pattern, source_title.lower().strip()):
                issues.append(f"Generic URL-style source: '{source_title}'")
                break

        # Check for overly generic source names (relaxed - only flag the most generic)
        overly_generic_sources = [
            "url",
            "link", 
            "source",
            "unknown",
            "unknown source",
            "newsletters",  # Keep this as it's truly generic
        ]

        if source_title and source_title.lower().strip() in overly_generic_sources:
            issues.append(f"Overly generic source: '{source_title}'")

        # Check if source title is just a single word that might be a category
        single_word_sources = ["justice", "technology", "business", "art", "society"]
        if source_title and source_title.lower().strip() in single_word_sources:
            issues.append(f"Category used as source: '{source_title}'")

        # Check if source is a CDN domain
        if source_title and url:
            from urllib.parse import urlparse

            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                for proxy_domain in self.PROXY_DOMAINS:
                    if proxy_domain in domain or proxy_domain in source_title.lower():
                        issues.append(
                            f"CDN/proxy domain used as source: '{source_title}'"
                        )
                        break
            except Exception:
                pass

        return issues

    def validate_image_metadata(self, alt_text: str, caption: str) -> List[str]:
        """Validate image metadata quality."""
        issues = []

        # Check for generic or duplicated alt text
        generic_patterns = [
            r"^image:?\s*image$",
            r"^photo$",
            r"^picture$",
            r"^img$",
            r"^untitled$",
            r"^image: professional illustration depicting",
        ]

        if alt_text:
            for pattern in generic_patterns:
                if re.match(pattern, alt_text.lower().strip()):
                    issues.append(f"Generic alt text: '{alt_text}'")
                    break
        else:
            issues.append("Missing alt text")

        if caption:
            if caption == alt_text:
                issues.append("Caption and alt text are identical")
            for pattern in generic_patterns:
                if re.match(pattern, caption.lower().strip()):
                    issues.append(f"Generic caption: '{caption}'")
                    break

        return issues

    def check_content_quality(self, content: dict) -> Dict[str, List[str]]:
        """
        Comprehensive content quality check.

        Args:
            content: Dictionary with keys like 'title', 'summary', 'source_title', etc.

        Returns:
            Dictionary mapping field names to lists of issues found
        """
        all_issues = {}

        # Sanitize and validate text fields
        text_fields = ["title", "summary", "description", "commentary"]
        for field in text_fields:
            if field in content and content[field]:
                sanitized, issues = self.sanitize_text(content[field], field)
                if issues:
                    all_issues[field] = issues

                # Update content with sanitized version
                content[field] = sanitized

                # Additional validation for specific fields
                if field == "title":
                    headline_issues = self.validate_headline(sanitized)
                    if headline_issues:
                        all_issues[f"{field}_quality"] = headline_issues
                elif field in ["summary", "description", "commentary"]:
                    completeness_issues = self.validate_completeness(
                        sanitized, min_length=20
                    )
                    if completeness_issues:
                        all_issues[f"{field}_completeness"] = completeness_issues

        # Validate and canonicalize URLs
        if "url" in content and content["url"]:
            canonical_url, url_issues = self.canonicalize_url(content["url"])
            if url_issues:
                all_issues["url"] = url_issues
            # Update content with canonical URL
            content["url"] = canonical_url

        # Validate source attribution
        if "source_title" in content:
            source_issues = self.validate_source_attribution(
                content.get("source_title", ""), content.get("url", "")
            )
            if source_issues:
                all_issues["source"] = source_issues

        # Validate image metadata
        if "image_alt" in content or "image_caption" in content:
            image_issues = self.validate_image_metadata(
                content.get("image_alt", ""), content.get("image_caption", "")
            )
            if image_issues:
                all_issues["image"] = image_issues

        # Assess evolutionary fitness for content survival
        content_text = " ".join([
            content.get("title", ""),
            content.get("summary", ""), 
            content.get("description", ""),
            content.get("commentary", "")
        ]).strip()
        
        if content_text:
            fitness = self.assess_evolutionary_fitness(content_text)
            if fitness["fitness_class"] in ["poorly_fit", "extinct"]:
                all_issues["evolutionary_fitness"] = [
                    f"Content fitness: {fitness['fitness_class']} (score: {fitness['fitness_score']})",
                    *fitness["factors"]
                ]

        return all_issues

    def validate_newsletter_structure(self, newsletter_content: str) -> List[str]:
        """Validate newsletter structure and formatting consistency."""
        issues = []

        # Check for core required sections (relaxed - only check for essential structure)
        core_required_sections = [
            r"# THE FILTER",
            r"## HEADLINES AT A GLANCE",
        ]

        for section in core_required_sections:
            if not re.search(section, newsletter_content, re.IGNORECASE):
                issues.append(f"Missing core section: {section}")

        # Check for content sections (at least 2 of these should be present)
        content_sections = [
            r"## LEAD STORIES",
            r"## TECHNOLOGY", 
            r"## SOCIETY",
            r"## ART",
            r"## BUSINESS",
        ]
        
        found_sections = sum(1 for section in content_sections 
                           if re.search(section, newsletter_content, re.IGNORECASE))
        
        if found_sections < 2:
            issues.append(f"Insufficient content sections: found {found_sections}, need at least 2")

        # Check for formatting issues

        # Double separators
        if re.search(r"---\s*\n\s*---", newsletter_content):
            issues.append("Double separator blocks found (should be single ---)")

        # Double spaces in headers - enhanced detection
        double_space_headers = re.findall(r"##\s{2,}\w+", newsletter_content)
        if double_space_headers:
            issues.append(f"Double spaces in headers: {double_space_headers}")

        # Raw URLs in body text - more comprehensive detection
        raw_url_patterns = [
            r"(?<!\[)(?<!\()https?://[^\s\)\]]+(?![\]\)])",  # Basic raw URLs
            r"(?<!\[)(?<!\()www\.[^\s\)\]]+(?![\]\)])",  # www URLs without protocol
            r"[a-zA-Z0-9.-]+\.substack\.com(?![^\[\s]*\])",  # Raw Substack domains
            r"x\.com/[^\s\)]+(?![^\[\s]*\])",  # Raw X/Twitter links
            r"twitter\.com/[^\s\)]+(?![^\[\s]*\])",  # Raw Twitter links
            r"(?<!\[)(?<!\()[a-zA-Z0-9.-]+\.[a-z]{2,}(?:/[^\s\)\]]+)?(?![\]\)])",  # Bare domains
        ]

        raw_urls_found = []
        for pattern in raw_url_patterns:
            matches = re.findall(pattern, newsletter_content)
            raw_urls_found.extend(matches)

        if raw_urls_found:
            issues.append(
                f"Raw URLs in body text (should be titled links): {len(raw_urls_found)} found"
            )

        # Check specifically for raw URLs in Headlines at a Glance section
        headlines_section = re.search(
            r"## HEADLINES AT A GLANCE(.*?)(?=##|\Z)",
            newsletter_content,
            re.DOTALL | re.IGNORECASE,
        )
        if headlines_section:
            headlines_text = headlines_section.group(1)
            for pattern in raw_url_patterns:
                if re.search(pattern, headlines_text):
                    issues.append("Raw URLs found in Headlines at a Glance section")
                    break

            # Check for placeholder sources in Headlines at a Glance
            placeholder_sources = [
                r"newsletters",
                r"readwise reader",
                r"url\d+",
            ]
            for pattern in placeholder_sources:
                if re.search(pattern, headlines_text, re.IGNORECASE):
                    issues.append(
                        "Placeholder source found in Headlines at a Glance section"
                    )
                    break

        # Generic image captions
        generic_image_patterns = [
            r"Image:\s*Image",
            r"Photo:\s*Photo",
            r"Picture:\s*Picture",
            r"\!\[Image\]\(",
            r"\!\[\]\(",
        ]

        for pattern in generic_image_patterns:
            if re.search(pattern, newsletter_content, re.IGNORECASE):
                issues.append(f"Generic image caption pattern found: {pattern}")

        # Duplicate images
        image_urls = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", newsletter_content)
        from collections import Counter

        duplicates = [url for url, count in Counter(image_urls).items() if count > 1]
        if duplicates:
            issues.append(f"Duplicate images detected: {len(duplicates)} duplicates")

        # Check for placeholder or broken links in Sources section
        sources_section = re.search(
            r"## SOURCES & ATTRIBUTION.*?(?=##|\Z)",
            newsletter_content,
            re.DOTALL | re.IGNORECASE,
        )
        if sources_section:
            sources_text = sources_section.group(0)

            # Check for placeholder sources
            placeholder_patterns = [
                r"Don't be demoralized",
                r"Url\d+",
                r"Unknown Source",
                r"Placeholder",
                r"Example\.com",
            ]

            for pattern in placeholder_patterns:
                if re.search(pattern, sources_text, re.IGNORECASE):
                    issues.append(f"Placeholder source found: {pattern}")

        # Check headline consistency (should be title case)
        headlines = re.findall(r"## ([A-Z\s]+)", newsletter_content)
        for headline in headlines:
            if (
                headline.strip() != headline.strip().upper()
                and headline.strip() != headline.strip().title()
            ):
                # Only flag if it's clearly inconsistent (all lowercase, mixed case)
                if headline.strip().islower():
                    issues.append(f"Inconsistent headline casing: '{headline.strip()}'")

        # Redundant top branding
        if len(re.findall(r"# THE FILTER", newsletter_content, re.IGNORECASE)) > 1:
            issues.append("Redundant top branding detected")

        return issues

    def fix_newsletter_formatting(self, newsletter_content: str) -> str:
        """Apply common formatting fixes to newsletter content."""

        # Fix double separators
        newsletter_content = re.sub(r"---\s*\n\s*---", "---", newsletter_content)

        # Fix double spaces in headers - more comprehensive
        newsletter_content = re.sub(r"(##)\s{2,}", r"\1 ", newsletter_content)

        # Ensure consistent spacing after separators
        newsletter_content = re.sub(r"---\s*\n\s*", "---\n\n", newsletter_content)

        # Fix multiple newlines (more than 2)
        newsletter_content = re.sub(r"\n{3,}", "\n\n", newsletter_content)

        # Ensure headers have proper spacing
        newsletter_content = re.sub(
            r"\n(## [A-Z\s&]+)\n", r"\n\n\1\n\n", newsletter_content
        )

        # Convert basic raw URLs to placeholder links where possible
        # This is a basic fallback - proper URL handling should happen earlier in the pipeline
        newsletter_content = re.sub(
            r"(?<!\[)(?<!\()https?://([^\s\)\]]+)(?![\]\)])",
            r"[\1](https://\1)",
            newsletter_content,
        )
        newsletter_content = re.sub(
            r"(?<!\[)(?<!\()[a-zA-Z0-9.-]+\.[a-z]{2,}(?:/[^\s\)\]]+)?(?![\]\)])",
            lambda m: f"[{m.group(0)}](https://{m.group(0)})",
            newsletter_content,
        )

        # Fix common typos found in 027
        typo_fixes = [
            (r"\bshareers\b", "sharers"),  # Specific typo from 027
            (r"\bdata shareers\b", "data sharers"),
        ]

        for typo, correction in typo_fixes:
            newsletter_content = re.sub(
                typo, correction, newsletter_content, flags=re.IGNORECASE
            )

        return newsletter_content
