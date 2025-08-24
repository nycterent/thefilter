#!/usr/bin/env python3
"""
Direct newsletter publication script that bypasses workflow dependencies.
Uses existing Infisical integration and publishes static newsletter content.
"""

import sys
import asyncio
import aiohttp
from pathlib import Path
from src.models.settings import Settings

async def publish_newsletter_direct(newsletter_file: str):
    """
    Publish newsletter directly to Buttondown using API credentials.
    
    Args:
        newsletter_file: Path to the newsletter markdown file
    """
    try:
        # Load settings with environment variables
        print("🔑 Loading API credentials...")
        settings = Settings()
        
        if not settings.buttondown_api_key:
            print("❌ Buttondown API key not found. Check BUTTONDOWN_API_KEY environment variable.")
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
        
        # Prepare Buttondown API request
        url = "https://api.buttondown.email/v1/emails"
        headers = {
            "Authorization": f"Token {settings.buttondown_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "subject": title,
            "body": content,
        }
        
        # Make API request
        timeout = aiohttp.ClientTimeout(total=settings.buttondown_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status in {200, 201}:
                    data = await response.json()
                    draft_id = data.get("id")
                    print("✅ Newsletter draft created successfully in Buttondown!")
                    print(f"📧 Draft ID: {draft_id}")
                    print(f"🔗 View in Buttondown: https://buttondown.email/filter")
                    return True
                else:
                    error_detail = await response.text()
                    print(f"❌ Buttondown API error {response.status}:")
                    print(error_detail)
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