#!/usr/bin/env python3
"""Quick test script to generate newsletter content and show the results."""

import asyncio
import os
from src.core.newsletter import NewsletterGenerator
from src.models.settings import Settings

async def test_newsletter():
    # Set RSS feeds
    os.environ['RSS_FEEDS'] = "https://en.wikipedia.org/w/api.php?action=featuredfeed&feed=featured&feedformat=atom"
    
    # Create settings
    settings = Settings()
    
    # Generate newsletter
    generator = NewsletterGenerator(settings)
    newsletter = await generator.generate_newsletter(dry_run=True)
    
    # Print first 1500 chars of content
    print("=== GENERATED NEWSLETTER CONTENT ===")
    print(newsletter.content[:1500])
    print("\n=== END PREVIEW ===")
    
    return newsletter

if __name__ == "__main__":
    newsletter = asyncio.run(test_newsletter())