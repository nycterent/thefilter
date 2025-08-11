"""Content sanitization and validation utilities."""

import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ContentSanitizer:
    """Handles content sanitization, validation, and quality checks."""

    # AI refusal patterns to detect and remove
    AI_REFUSAL_PATTERNS = [
        r"I can't provide information or guidance on harmful or illegal activities",
        r"I cannot help with that request",
        r"I'm not able to assist with",
        r"I cannot provide information that could be used to harm",
        r"I'm sorry, but I can't help with",
        r"As an AI assistant, I cannot",
        r"I don't feel comfortable",
        r"I cannot and will not provide",
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

    # CDN and proxy domains to canonicalize
    PROXY_DOMAINS = {
        "feedbinusercontent.com",
        "substackcdn.com",
        "readwise.io",
        "cdn.substack.com",
        "medium.com/_/stat",
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
        original_text = text

        # Check for AI refusal strings
        refusal_matches = self.refusal_regex.findall(text)
        if refusal_matches:
            for match in refusal_matches:
                issues.append(f"AI refusal detected in {context}: '{match[:50]}...'")
                # Remove the entire sentence containing the refusal
                sentences = text.split(".")
                clean_sentences = []
                for sentence in sentences:
                    if not self.refusal_regex.search(sentence):
                        clean_sentences.append(sentence)
                text = ".".join(clean_sentences)

        # Check for prompt leakage
        prompt_matches = self.prompt_leak_regex.findall(text)
        if prompt_matches:
            for match in prompt_matches:
                issues.append(f"Prompt leakage detected in {context}: '{match}'")
                # Remove the leaked prompt text
                text = self.prompt_leak_regex.sub("", text)

        # Clean up whitespace and formatting issues
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*\.\s*\.", ".", text)  # Fix double periods

        return text, issues

    def validate_completeness(self, text: str, min_length: int = 10) -> List[str]:
        """Validate that content meets minimum quality standards."""
        issues = []

        if not text or len(text.strip()) < min_length:
            issues.append(
                f"Content too short: {len(text.strip())} chars (minimum: {min_length})"
            )
            return issues

        # Check for truncated sentences
        if text.endswith(("...", "..", " ", "concerni", "paint a concerni")):
            issues.append("Content appears truncated or incomplete")

        # Check for placeholder content
        placeholder_patterns = [
            r"lorem ipsum",
            r"placeholder",
            r"TODO",
            r"FIXME",
            r"example\.com",
            r"test\d+",
        ]

        for pattern in placeholder_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Placeholder content detected: {pattern}")

        return issues

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

        # Check for inconsistent casing (should be title case for quality)
        words = headline.split()
        if len(words) > 1 and all(word.islower() for word in words[:2]):
            issues.append(f"Headline not properly capitalized: '{headline}'")

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
                        issues.append(f"Canonicalized to: {canonical_url}")
                        break
                    else:
                        # If we can't canonicalize, flag as problematic
                        issues.append(f"Unable to canonicalize {proxy_domain} URL")

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

        This is a best-effort approach for common proxy services.
        """
        try:
            # Feedbin proxy URLs often have the original URL embedded
            if "feedbinusercontent.com" in proxy_domain:
                # Pattern: https://feedbinusercontent.com/123/original-url-encoded
                # This is simplified - real implementation would need URL decoding
                parts = proxy_url.split("/")
                if len(parts) > 4:
                    # Try to reconstruct from path segments
                    potential_domain = parts[4] if len(parts) > 4 else None
                    if potential_domain and "." in potential_domain:
                        return f"https://{potential_domain}"

            # Substack CDN URLs
            elif "substackcdn.com" in proxy_domain:
                # Pattern: https://substackcdn.com/image/fetch/...
                # These are usually image URLs, harder to canonicalize
                return proxy_url

            # Readwise.io URLs
            elif "readwise.io" in proxy_domain:
                # These are reader URLs, not the original article
                # We'd need the original URL from the API response
                return proxy_url

        except Exception:
            pass

        return proxy_url

    def validate_source_attribution(self, source_title: str, url: str) -> List[str]:
        """Validate source attribution quality."""
        issues = []

        # Check for placeholder source titles
        placeholder_sources = [
            "unknown",
            "unknown source",
            "newsletters",
            "starred articles",
            "url",
            "link",
            "source",
        ]

        if not source_title or source_title.lower().strip() in placeholder_sources:
            issues.append(f"Placeholder source title: '{source_title}'")

        # Check for generic patterns like "Url3396"
        if re.match(r"^url\d+$", source_title.lower().strip()):
            issues.append(f"Generic URL-style source: '{source_title}'")

        # Check if source title is just a single word that might be a category
        single_word_sources = ["justice", "technology", "business", "art", "society"]
        if source_title and source_title.lower().strip() in single_word_sources:
            issues.append(f"Category used as source: '{source_title}'")

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
        ]

        if alt_text:
            for pattern in generic_patterns:
                if re.match(pattern, alt_text.lower().strip()):
                    issues.append(f"Generic alt text: '{alt_text}'")
                    break
        else:
            issues.append("Missing alt text")

        if caption and caption == alt_text:
            issues.append("Caption and alt text are identical")

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

        return all_issues

    def validate_newsletter_structure(self, newsletter_content: str) -> List[str]:
        """Validate newsletter structure and formatting consistency."""
        issues = []

        # Check for required sections
        required_sections = [
            r"# THE FILTER",
            r"## HEADLINES AT A GLANCE",
            r"## LEAD STORIES",
            r"## TECHNOLOGY",
            r"## SOCIETY",
            r"## ART",
            r"## BUSINESS",
        ]

        for section in required_sections:
            if not re.search(section, newsletter_content, re.IGNORECASE):
                issues.append(f"Missing required section: {section}")

        # Check for formatting issues

        # Double separators
        if re.search(r"---\s*\n\s*---", newsletter_content):
            issues.append("Double separator blocks found (should be single ---)")

        # Double spaces in headers
        double_space_headers = re.findall(r"##\s\s+\w+", newsletter_content)
        if double_space_headers:
            issues.append(f"Double spaces in headers: {double_space_headers}")

        # Raw URLs in body text
        raw_url_pattern = r"(?<![\[\(])https?://[^\s\)]+(?![\]\)])"
        raw_urls = re.findall(raw_url_pattern, newsletter_content)
        if raw_urls:
            issues.append(
                f"Raw URLs in body text (should be titled links): {len(raw_urls)} found"
            )

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

        return issues

    def fix_newsletter_formatting(self, newsletter_content: str) -> str:
        """Apply common formatting fixes to newsletter content."""

        # Fix double separators
        newsletter_content = re.sub(r"---\s*\n\s*---", "---", newsletter_content)

        # Fix double spaces in headers
        newsletter_content = re.sub(r"(##)\s\s+", r"\1 ", newsletter_content)

        # Ensure consistent spacing after separators
        newsletter_content = re.sub(r"---\s*\n\s*", "---\n\n", newsletter_content)

        # Fix multiple newlines (more than 2)
        newsletter_content = re.sub(r"\n{3,}", "\n\n", newsletter_content)

        # Ensure headers have proper spacing
        newsletter_content = re.sub(
            r"\n(## [A-Z\s]+)\n", r"\n\n\1\n\n", newsletter_content
        )

        return newsletter_content
