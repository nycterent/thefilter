#!/usr/bin/env python3
"""
Warm Readwise cache by fetching and caching documents.
This prevents rate limiting during actual newsletter generation.
"""

import asyncio
import sys
from pathlib import Path
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clients.readwise import ReadwiseClient
from models.settings import Settings


async def warm_cache():
    """Warm the Readwise cache by fetching documents."""
    try:
        print("🔥 WARMING READWISE CACHE")
        print("=" * 50)
        
        # Load settings
        settings = Settings()
        
        if not settings.readwise_api_key:
            print("❌ No Readwise API key found")
            print("Set READWISE_API_KEY environment variable")
            return
        
        print(f"🔑 Using Readwise API key: {settings.readwise_api_key[:8]}...")
        
        # Create Readwise client
        readwise_client = ReadwiseClient(settings.readwise_api_key, settings)
        
        print("📡 Fetching Readwise documents...")
        print("⏰ This will populate cache for 1 hour")
        
        # Fetch documents - this will cache them
        documents = await readwise_client.get_recent_reader_documents(days=30)
        
        if documents:
            print(f"✅ Successfully cached {len(documents)} documents")
            print("🎯 Cache is now warm - newsletter generation will be faster")
            print("⏱️ Cache valid for next 1 hour")
            
            # Show sample of cached content
            twiar_docs = [doc for doc in documents if 'twiar' in str(doc.get('tags', {})).lower()]
            print(f"📰 Found {len(twiar_docs)} 'twiar' tagged articles for newsletter")
            
            if twiar_docs:
                print("\n📋 Sample articles:")
                for i, doc in enumerate(twiar_docs[:3], 1):
                    title = doc.get('title', 'Unknown')[:60]
                    print(f"  {i}. {title}")
        else:
            print("⚠️ No documents retrieved - check API key or network connection")
            
    except Exception as e:
        print(f"❌ Cache warming failed: {e}")
        return


async def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python scripts/warm_cache.py")
        print("")
        print("This script fetches Readwise documents and caches them for 1 hour.")
        print("This prevents rate limiting during newsletter generation.")
        print("")
        print("Required: READWISE_API_KEY environment variable")
        return
    
    await warm_cache()
    
    # Show final cache status
    print("\n" + "=" * 50)
    from core.readwise_cache import get_readwise_cache
    cache = get_readwise_cache()
    status = cache.get_cache_status()
    print(f"📊 Final cache status: {status['valid_entries']} valid entries")


if __name__ == "__main__":
    asyncio.run(main())