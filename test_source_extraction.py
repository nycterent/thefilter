#!/usr/bin/env python3
"""
Test the universal source extraction algorithm with real newsletter examples.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.source_extractor import NewsletterSourceExtractor


async def test_real_examples():
    """Test with actual newsletter intermediary sources."""
    
    test_cases = [
        {
            'name': 'IQ Study (US7 -> Clearer Thinking)',
            'url': 'https://us7.campaign-archive.com/some-mailchimp-link',
            'content': '4 Surprising Lessons from Running a Giant Study on IQ\n\nThis study examined 40 claims about IQ with 3,691 participants.\n\nRead more: Us7',
            'expected_domain': 'clearerthinking.org'
        },
        {
            'name': 'Marshmallow Test (HN -> Academic Paper)', 
            'url': 'https://news.ycombinator.com/item?id=41139854',
            'content': 'Discussion about marshmallow test replication and delayed gratification studies in children',
            'expected_domain': 'onlinelibrary.wiley.com'
        },
        {
            'name': 'Buttondown Archive',
            'url': 'https://buttondown.com/filter/archive/curated-briefing-013/',
            'content': 'Newsletter content about FDA eye drops and Israeli kidney research',
            'expected_domain': 'newatlas.com'
        },
        {
            'name': 'Direct Source (no extraction needed)',
            'url': 'https://www.nature.com/articles/d41586-025-02342-y',
            'content': 'Direct link to Nature article about quantum mechanics survey',
            'expected_domain': 'nature.com'
        }
    ]
    
    print("🧪 TESTING UNIVERSAL SOURCE EXTRACTOR")
    print("=" * 60)
    
    async with NewsletterSourceExtractor() as extractor:
        for i, test in enumerate(test_cases, 1):
            print(f"\n{i}. {test['name']}")
            print(f"   Original URL: {test['url']}")
            print(f"   Expected domain: {test['expected_domain']}")
            
            try:
                result = await extractor.extract_source(test['url'], test['content'])
                
                print(f"   📊 Results:")
                print(f"      - Is intermediary: {result.is_intermediary}")
                print(f"      - Extracted title: {result.title}")
                print(f"      - Final URL: {result.final_url}")
                print(f"      - Method: {result.extraction_method}")
                print(f"      - Confidence: {result.confidence:.2f}")
                
                # Check success
                if result.final_url and test['expected_domain'] in result.final_url:
                    print(f"   ✅ SUCCESS: Found expected domain")
                elif not result.is_intermediary and test['expected_domain'] in result.original_url:
                    print(f"   ✅ SUCCESS: Direct source (no extraction needed)")
                else:
                    print(f"   ⚠️  PARTIAL: {result.extraction_method}")
                
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
    
    print("\n" + "=" * 60)


async def test_batch_processing():
    """Test batch processing capability."""
    
    print("\n🔄 TESTING BATCH PROCESSING")
    print("=" * 60)
    
    url_content_pairs = [
        ('https://us7.campaign-archive.com/test1', '4 Surprising Lessons from Running a Giant Study on IQ'),
        ('https://news.ycombinator.com/item?id=41139854', 'Marshmallow test discussion'),
        ('https://www.nature.com/articles/direct', 'Direct nature article'),
    ]
    
    async with NewsletterSourceExtractor() as extractor:
        results = await extractor.batch_extract(url_content_pairs)
        
        for (url, content), result in zip(url_content_pairs, results):
            print(f"URL: {url}")
            if hasattr(result, 'extraction_method'):
                print(f"  Method: {result.extraction_method}")
                print(f"  Resolved: {result.final_url or 'None'}")
            else:
                print(f"  Error: {result}")
            print()


if __name__ == "__main__":
    async def main():
        await test_real_examples()
        await test_batch_processing()
    
    asyncio.run(main())