#!/usr/bin/env python3
"""
Cache warming script for Readwise API.
Pre-loads 'twiar-tagged' documents into cache to avoid rate limiting during newsletter generation.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.clients.readwise import ReadwiseClient
from src.core.readwise_cache import get_readwise_cache
from src.models.settings import Settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def warm_readwise_cache():
    """Warm the Readwise cache with twiar-tagged documents."""
    try:
        # Load settings
        print("🔑 Loading API credentials...")
        settings = Settings()
        
        if not settings.readwise_api_key:
            print("❌ Readwise API key not found. Check READWISE_API_KEY environment variable.")
            return False
        
        # Initialize Readwise client
        readwise_client = ReadwiseClient(settings.readwise_api_key, settings)
        
        # Get cache status
        cache = get_readwise_cache()
        status = cache.get_cache_status()
        print(f"📊 Cache status: {status['valid_entries']} valid entries, {status['expired_entries']} expired")
        
        # Clean up expired entries
        cache.clear_expired_cache()
        
        # Check if we already have valid cached data
        cached_docs = cache.get_cached_documents(days=30)
        if cached_docs is not None:
            print(f"✅ Cache already contains {len(cached_docs)} twiar-tagged documents")
            print("💡 Use this for newsletter generation without API calls")
            return True
        
        # Fetch fresh data
        print("📡 Fetching fresh twiar-tagged documents from Readwise...")
        documents = await readwise_client.get_recent_reader_documents(days=30)
        
        if documents:
            print(f"✅ Successfully cached {len(documents)} twiar-tagged documents for 1 hour")
            
            # Show some sample titles
            print("\n📄 Sample cached articles:")
            for i, doc in enumerate(documents[:5]):
                title = doc.get('title', 'Untitled')[:60]
                source = doc.get('source', 'Unknown')
                print(f"  {i+1}. {title}... [{source}]")
            
            if len(documents) >= 7:
                print(f"\n✅ Cache contains {len(documents)} articles (≥7 required for newsletter)")
                print("🚀 Ready for newsletter generation!")
            else:
                print(f"\n⚠️ Only {len(documents)} articles cached (<7 required for newsletter)")
                print("💡 Add more 'twiar' tags to articles in Readwise Reader")
            
            return True
        else:
            print("❌ No twiar-tagged documents found")
            print("💡 Tag articles with 'twiar' in Readwise Reader first")
            return False
            
    except Exception as e:
        print(f"❌ Error warming cache: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main execution function."""
    print("🔥 Warming Readwise cache for newsletter generation...\n")
    
    success = await warm_readwise_cache()
    
    if success:
        print("\n✅ Cache warming completed successfully!")
        print("🔄 You can now run newsletter generation without API rate limits")
    else:
        print("\n❌ Cache warming failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())