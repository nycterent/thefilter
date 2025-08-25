#!/usr/bin/env python3
"""
Test script for the Multi-Model LLM Protocol

This script tests the collaborative refinement workflow with a simple example.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the script directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from multi_model_protocol import MultiModelProtocol


async def test_protocol():
    """Test the Multi-Model LLM Protocol with a simple example."""
    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY environment variable not set")
        print("Set it with: export OPENROUTER_API_KEY='your-key-here'")
        return
    
    # Test problem
    test_problem = """
    I need to optimize my newsletter generation system. Currently it takes too long to process 
    multiple RSS feeds and generate quality content. The system should be faster, more reliable, 
    and produce better editorial content that engages readers.
    
    Key constraints:
    - Must handle 10+ RSS feeds efficiently
    - Content quality is crucial (no generic summaries)
    - System should be resilient to API failures
    - Editorial voice should be consistent and engaging
    """
    
    # Context files to include
    context_files = [
        "src/core/newsletter.py",
        "src/clients/openrouter.py"
    ]
    
    print("🧪 Testing Multi-Model LLM Protocol...")
    print(f"Problem: {test_problem.strip()}")
    print(f"Context files: {', '.join(context_files)}")
    
    # Run the protocol
    protocol = MultiModelProtocol(api_key)
    result = await protocol.run_protocol(test_problem, context_files)
    
    # Display results
    print("\n" + "="*60)
    print("📊 TEST RESULTS")
    print("="*60)
    
    if "error" in result:
        print(f"❌ Test failed: {result['error']}")
    else:
        print("✅ Test completed successfully!")
        print(f"\nStatus: {result['status']}")
        print(f"\nFinal plan length: {len(result['final_plan'])} characters")
        
        # Save full results to file
        output_file = Path(__file__).parent / "test_results.txt"
        with open(output_file, 'w') as f:
            f.write("MULTI-MODEL LLM PROTOCOL TEST RESULTS\n")
            f.write("="*50 + "\n\n")
            f.write(f"Problem: {result['problem']}\n\n")
            f.write(f"Initial Plan (GLM-4.5):\n{result['initial_plan']}\n\n")
            f.write(f"Refinement (Gemini Pro 2.5):\n{result['refinement']}\n\n")
            f.write(f"Final Plan:\n{result['final_plan']}\n")
        
        print(f"\n📁 Full results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(test_protocol())