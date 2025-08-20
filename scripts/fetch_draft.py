#!/usr/bin/env python3
"""
Script to fetch and analyze a specific newsletter draft from Buttondown.
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


def analyze_newsletter_content(content: str, title: str) -> dict:
    """Analyze newsletter content for the specified criteria."""
    
    # Template contamination phrases to check for
    contamination_phrases = [
        "imagine a world",
        "protocol",
        "antifragility",
        "in a world where",
        "the age of",
        "paradigm shift",
        "unprecedented",
        "revolutionize",
        "transformative",
        "disruptive"
    ]
    
    # Convert to lowercase for case-insensitive matching
    content_lower = content.lower()
    title_lower = title.lower()
    
    # Check for contamination phrases
    found_contamination = []
    for phrase in contamination_phrases:
        if phrase in content_lower or phrase in title_lower:
            found_contamination.append(phrase)
    
    # Check AI commentary quality (third person usage)
    # Look for first-person indicators that suggest improper commentary
    first_person_indicators = ["i think", "i believe", "my opinion", "i would", "i feel"]
    first_person_issues = []
    for indicator in first_person_indicators:
        if indicator in content_lower:
            first_person_issues.append(indicator)
    
    # Check for proper third-person commentary patterns
    third_person_patterns = [
        "the analysis suggests",
        "this development indicates", 
        "research shows",
        "experts note",
        "the study reveals",
        "findings demonstrate",
        "according to",
        "the report highlights",
        "signals advancements",
        "provoke questions",
        "reflecting the",
        "reminder of",
        "physicists grapple",
        "they reveal",
        "demonstrates",
        "underscores",
        "highlights",
        "suggests",
        "reveals",
        "indicates"
    ]
    
    third_person_count = sum(1 for pattern in third_person_patterns if pattern in content_lower)
    
    # Word count analysis
    word_count = len(content.split())
    
    # Section analysis - count different types of sections
    h2_count = content.count("## ")
    h3_count = content.count("### ")
    
    # Check for proper structure
    has_curated_briefing_title = "curated briefing" in title_lower
    has_proper_sections = h2_count >= 3  # Should have multiple main sections
    
    return {
        "contamination_analysis": {
            "has_contamination": bool(found_contamination),
            "contamination_phrases": found_contamination,
            "contamination_count": len(found_contamination)
        },
        "ai_commentary_quality": {
            "first_person_issues": first_person_issues,
            "third_person_patterns_count": third_person_count,
            "proper_third_person": third_person_count > 0 and len(first_person_issues) == 0
        },
        "content_structure": {
            "word_count": word_count,
            "h2_sections": h2_count,
            "h3_sections": h3_count,
            "has_curated_briefing_title": has_curated_briefing_title,
            "has_proper_sections": has_proper_sections
        },
        "overall_quality": {
            "title": title,
            "passes_contamination_check": len(found_contamination) == 0,
            "passes_ai_commentary_check": third_person_count > 0 and len(first_person_issues) == 0,
            "passes_structure_check": has_proper_sections and has_curated_briefing_title
        }
    }


def main():
    """Main function to fetch and analyze draft."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/fetch_draft.py <draft_id>")
        print("Example: python scripts/fetch_draft.py 510b39ca-1b0b-4936-a3e9-2d9933f5d7c4")
        sys.exit(1)
    
    draft_id = sys.argv[1]
    
    print(f"Fetching draft with ID: {draft_id}")
    draft_data = fetch_draft_by_id(draft_id)
    
    if not draft_data:
        print("Failed to fetch draft data")
        sys.exit(1)
    
    print(f"Successfully fetched draft: {draft_data.get('subject', 'No subject')}")
    print(f"Status: {draft_data.get('status', 'Unknown')}")
    print(f"Created: {draft_data.get('created', 'Unknown')}")
    print()
    
    # Analyze the content
    content = draft_data.get('body', '')
    title = draft_data.get('subject', '')
    
    print("=== CONTENT ANALYSIS ===")
    analysis = analyze_newsletter_content(content, title)
    
    # Print contamination analysis
    print(f"\n🔍 TEMPLATE CONTAMINATION CHECK:")
    if analysis['contamination_analysis']['has_contamination']:
        print(f"❌ CONTAMINATION DETECTED: {analysis['contamination_analysis']['contamination_count']} phrases found")
        for phrase in analysis['contamination_analysis']['contamination_phrases']:
            print(f"   - '{phrase}'")
    else:
        print("✅ NO CONTAMINATION: Template phrases eliminated successfully")
    
    # Print AI commentary analysis
    print(f"\n🤖 AI COMMENTARY QUALITY:")
    if analysis['ai_commentary_quality']['proper_third_person']:
        print(f"✅ PROPER THIRD PERSON: {analysis['ai_commentary_quality']['third_person_patterns_count']} professional patterns found")
    else:
        print(f"❌ COMMENTARY ISSUES:")
        if analysis['ai_commentary_quality']['first_person_issues']:
            print(f"   First-person issues: {analysis['ai_commentary_quality']['first_person_issues']}")
        if analysis['ai_commentary_quality']['third_person_patterns_count'] == 0:
            print("   No professional third-person patterns detected")
    
    # Print structure analysis
    print(f"\n📋 CONTENT STRUCTURE:")
    print(f"   Word count: {analysis['content_structure']['word_count']}")
    print(f"   H2 sections: {analysis['content_structure']['h2_sections']}")
    print(f"   H3 sections: {analysis['content_structure']['h3_sections']}")
    print(f"   Proper title: {'✅' if analysis['content_structure']['has_curated_briefing_title'] else '❌'}")
    print(f"   Proper sections: {'✅' if analysis['content_structure']['has_proper_sections'] else '❌'}")
    
    # Overall assessment
    print(f"\n📊 OVERALL ASSESSMENT:")
    overall = analysis['overall_quality']
    print(f"   Contamination Check: {'✅ PASS' if overall['passes_contamination_check'] else '❌ FAIL'}")
    print(f"   AI Commentary Check: {'✅ PASS' if overall['passes_ai_commentary_check'] else '❌ FAIL'}")
    print(f"   Structure Check: {'✅ PASS' if overall['passes_structure_check'] else '❌ FAIL'}")
    
    total_checks = 3
    passed_checks = sum([
        overall['passes_contamination_check'],
        overall['passes_ai_commentary_check'],
        overall['passes_structure_check']
    ])
    
    print(f"\n🎯 FINAL SCORE: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        print("🎉 EXCELLENT: All quality checks passed!")
    elif passed_checks >= 2:
        print("⚠️  GOOD: Most checks passed, minor improvements needed")
    else:
        print("🚨 NEEDS WORK: Significant improvements required")
    
    # Show first 500 characters of content for preview
    print(f"\n📄 CONTENT PREVIEW (first 500 chars):")
    print("-" * 50)
    print(content[:500] + "..." if len(content) > 500 else content)
    print("-" * 50)


if __name__ == "__main__":
    main()