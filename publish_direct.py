#!/usr/bin/env python3
"""
Direct newsletter publication script that bypasses workflow dependencies.
Uses existing Infisical integration and publishes static newsletter content.
"""

import sys
import asyncio
from pathlib import Path
from src.models.settings import Settings
from src.clients.buttondown import ButtondownClient

async def publish_newsletter_direct(newsletter_file: str):
    """
    Publish newsletter directly to Buttondown using Infisical-managed credentials.
    
    Args:
        newsletter_file: Path to the newsletter markdown file
    """
    try:
        # Load settings with Infisical integration
        print("🔑 Loading API credentials via Infisical...")
        settings = Settings()
        
        if not settings.buttondown_api_key:
            print("❌ Buttondown API key not found. Ensure Infisical is configured.")
            return False
            
        # Read newsletter content
        newsletter_path = Path(newsletter_file)
        if not newsletter_path.exists():
            print(f"❌ Newsletter file not found: {newsletter_file}")
            return False
            
        print(f"📄 Reading newsletter content from: {newsletter_file}")
        content = newsletter_path.read_text(encoding='utf-8')
        
        # Extract title from content
        lines = content.split('\n')
        title = "THE FILTER - Weekly Curated Briefing"
        for line in lines[:10]:  # Check first 10 lines
            if line.startswith('# '):
                title = line[2:].strip()
                break
        
        print(f"📧 Publishing newsletter: {title}")
        
        # Initialize Buttondown client
        buttondown = ButtondownClient(
            api_key=settings.buttondown_api_key,
            timeout=settings.buttondown_timeout
        )
        
        # Publish newsletter
        result = await buttondown.publish_newsletter(
            subject=title,
            body=content,
            newsletter_type="primary"
        )
        
        if result.get('status') == 'success':
            print("✅ Newsletter published successfully!")
            print(f"🔗 Newsletter URL: {result.get('url', 'N/A')}")
            print(f"📊 Subscribers notified: {result.get('subscribers', 'N/A')}")
            return True
        else:
            print(f"❌ Publication failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error during publication: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main execution function."""
    if len(sys.argv) != 2:
        print("Usage: python publish_direct.py <newsletter_file>")
        print("Example: python publish_direct.py newsletter_final.md")
        sys.exit(1)
        
    newsletter_file = sys.argv[1]
    success = await publish_newsletter_direct(newsletter_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())