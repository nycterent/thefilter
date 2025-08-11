"""Utility functions for URL and text processing."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def extract_source_from_url(url: str) -> str:
    """Extract a human friendly source name from a URL.

    Removes common subdomains and TLDs, applies known mappings and
    returns a title-cased domain name. Returns an empty string if the
    URL cannot be parsed.
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            return ""

        domain = re.sub(r"^(www\.|m\.|mobile\.)", "", domain)
        original_domain = domain
        domain = re.sub(r"\.(com|org|net|edu|gov|io|co\.uk|ai)$", "", domain)

        source_mapping = {
            "nature": "Nature",
            "techcrunch": "TechCrunch",
            "arstechnica": "Ars Technica",
            "wired": "WIRED",
            "theverge": "The Verge",
            "medium": "Medium",
            "github": "GitHub",
            "stackoverflow": "Stack Overflow",
            "reddit": "Reddit",
            "youtube": "YouTube",
            "twitter": "Twitter",
            "linkedin": "LinkedIn",
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "google": "Google",
            "microsoft": "Microsoft",
            "apple": "Apple",
            "meta": "Meta",
        }

        if domain in source_mapping:
            return source_mapping[domain]

        if ".substack" in original_domain:
            subdomain = original_domain.split(".")[0]
            return f"{subdomain.title()} (Substack)"

        parts = domain.split(".")
        if parts:
            main_domain = parts[0]
            return main_domain.replace("-", " ").replace("_", " ").title()

        return domain.title()
    except Exception:
        return ""


def clean_article_title(title: str) -> str:
    """Clean article titles by removing noisy prefixes and extra whitespace."""
    if not title:
        return "Untitled Article"

    cleaned = re.sub(r"^\[.*?\]\s*", "", title)
    cleaned = re.sub(r"^(Fwd:|Re:|FW:)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())

    if len(cleaned) < 5 or any(g in cleaned.lower() for g in ["untitled", "no subject", "fwd", "firehose"]):
        return "Article Commentary"

    return cleaned.strip()
