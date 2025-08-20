#!/usr/bin/env python3
"""
Script to get the full content of a newsletter draft for detailed analysis.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_draft_by_id(draft_id: str) -> dict:
    """Fetch a specific draft from Buttondown by ID."""
    # Get API key from environment (injected by infisical)
    api_key = os.getenv('BUTTONDOWN_API_KEY')
    
    if not api_key:
        logger.error("No Buttondown API key available")
        return {}
    
    url = f"https://api.buttondown.email/v1/emails/{draft_id}"
    
    try:
        request = urllib.request.Request(url)
        request.add_header('Authorization', f'Token {api_key}')
        
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                return json.loads(data)
            else:
                logger.error(f"Failed to fetch draft: HTTP {response.status}")
                return {}
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error fetching draft: {e.code} - {e.reason}")
        return {}
    except Exception as e:
        logger.error(f"Error fetching draft: {e}")
        return {}


def main():
    """Main function to fetch and display full draft content."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/detailed_analysis.py <draft_id>")
        print("Example: python scripts/detailed_analysis.py 510b39ca-1b0b-4936-a3e9-2d9933f5d7c4")
        sys.exit(1)
    
    draft_id = sys.argv[1]
    
    print(f"Fetching full content for draft ID: {draft_id}")
    draft_data = fetch_draft_by_id(draft_id)
    
    if not draft_data:
        print("Failed to fetch draft data")
        sys.exit(1)
    
    print(f"Title: {draft_data.get('subject', 'No subject')}")
    print(f"Status: {draft_data.get('status', 'Unknown')}")
    print("-" * 80)
    
    content = draft_data.get('body', '')
    print(content)


if __name__ == "__main__":
    main()