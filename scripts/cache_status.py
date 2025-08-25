#!/usr/bin/env python3
"""
Check Readwise cache status and effectiveness.
"""

import sys
from pathlib import Path
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.readwise_cache import get_readwise_cache


def main():
    """Check and display Readwise cache status."""
    cache = get_readwise_cache()
    status = cache.get_cache_status()
    
    print("🗄️ READWISE CACHE STATUS")
    print("=" * 50)
    
    print(f"📁 Cache file: {status['cache_file']}")
    print(f"📊 Total entries: {status['total_entries']}")
    print(f"✅ Valid entries: {status['valid_entries']}")
    print(f"❌ Expired entries: {status['expired_entries']}")
    
    if status['next_expiry']:
        next_expiry = datetime.fromisoformat(status['next_expiry'])
        time_until_expiry = next_expiry - datetime.now()
        print(f"⏰ Next expiry: {next_expiry} ({time_until_expiry})")
    else:
        print("⏰ Next expiry: None")
    
    # Check cache file size
    if os.path.exists(status['cache_file']):
        file_size = os.path.getsize(status['cache_file'])
        print(f"💾 Cache file size: {file_size:,} bytes")
    
    print("\n🔍 CACHE EFFECTIVENESS")
    print("=" * 50)
    
    if status['valid_entries'] > 0:
        print("✅ Cache is active and should prevent API rate limiting")
        print("📡 Fresh API calls will be avoided for cached documents")
    else:
        print("⚠️ Cache is empty - next API call will fetch fresh data")
        print("💡 After first successful API call, cache will be populated for 1 hour")
    
    print("\n🎯 CACHE BENEFITS")
    print("=" * 50)
    print("• Avoids Readwise API rate limiting (429 errors)")
    print("• Reduces latency for newsletter generation")
    print("• Preserves API quota for critical operations")
    print("• Maintains system reliability during high usage")
    
    if status['valid_entries'] == 0:
        print("\n💡 RECOMMENDATION")
        print("=" * 50)
        print("Run newsletter generation to populate cache:")
        print("  ./venv/bin/python -m src.newsletter_bot generate --dry-run")


if __name__ == "__main__":
    main()