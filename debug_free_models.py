#!/usr/bin/env python3
"""Debug script testing different free models on OpenRouter."""

import asyncio
import os
import logging
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_free_models.log')
    ]
)

llm_logger = logging.getLogger('LLM_DEBUG')
llm_logger.setLevel(logging.INFO)

llm_handler = logging.FileHandler('free_models_test.log')
llm_formatter = logging.Formatter('%(asctime)s - %(message)s')
llm_handler.setFormatter(llm_formatter)
llm_logger.addHandler(llm_handler)

from src.clients.openrouter import OpenRouterClient
from src.clients.rss import RSSClient
from src.models.settings import Settings


class FreeModelTester(OpenRouterClient):
    """OpenRouter client that tests different free models."""
    
    def __init__(self, api_key: str, model: str):
        super().__init__(api_key)
        self.default_model = model
        self.interaction_count = 0
        self.model_name = model
    
    async def _make_request(self, prompt: str, max_tokens: int = 100, temperature: float = 0.3) -> Dict[str, Any]:
        """Override to log all interactions."""
        self.interaction_count += 1
        
        # Log the input
        llm_logger.info(f"\n{'='*80}")
        llm_logger.info(f"MODEL TEST: {self.model_name} - INTERACTION #{self.interaction_count}")
        llm_logger.info(f"{'='*80}")
        llm_logger.info(f"MAX_TOKENS: {max_tokens}")
        llm_logger.info(f"TEMPERATURE: {temperature}")
        llm_logger.info(f"\nINPUT PROMPT:\n{'-'*40}")
        llm_logger.info(prompt)
        llm_logger.info(f"{'-'*40}")
        
        # Make the actual request
        response = await super()._make_request(prompt, max_tokens, temperature)
        
        # Log the response
        if response and "choices" in response:
            content = response["choices"][0]["message"]["content"]
            llm_logger.info(f"\nLLM RESPONSE:\n{'-'*40}")
            llm_logger.info(content)
            llm_logger.info(f"{'-'*40}")
            
            if "usage" in response:
                usage = response["usage"]
                llm_logger.info(f"\nTOKEN USAGE:")
                llm_logger.info(f"Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                llm_logger.info(f"Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                llm_logger.info(f"Total tokens: {usage.get('total_tokens', 'N/A')}")
        else:
            llm_logger.info(f"\nLLM RESPONSE: FAILED")
            llm_logger.info(f"Raw response: {response}")
        
        llm_logger.info(f"{'='*80}\n")
        
        return response
    
    async def test_simple_task(self) -> str:
        """Test a simple writing task."""
        prompt = """Write a 2-paragraph commentary about societal collapse. Focus on inequality and elite classes. Keep it under 200 words and conversational."""
        
        response = await self._make_request(prompt, max_tokens=150, temperature=0.7)
        if response and "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0]["message"]["content"].strip()
        return "FAILED"


async def test_free_models():
    """Test different free models available on OpenRouter."""
    
    print("🔍 Testing different free models on OpenRouter...")
    
    # Check required environment variables
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        print("❌ OPENROUTER_API_KEY environment variable not set")
        return
    
    # Free models to test (as of 2025)
    free_models = [
        "meta-llama/llama-3.1-8b-instruct:free",
        "microsoft/wizardlm-2-8x22b:free", 
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "qwen/qwen-2-7b-instruct:free",
        "huggingfaceh4/zephyr-7b-beta:free",
        "openchat/openchat-7b:free",
        "gryphe/mythomist-7b:free",
        "undi95/toppy-m-7b:free"
    ]
    
    results = {}
    
    for model in free_models:
        print(f"\n🤖 Testing model: {model}")
        try:
            client = FreeModelTester(openrouter_key, model)
            
            # Test simple task
            result = await client.test_simple_task()
            
            if result != "FAILED" and len(result) > 10:
                print(f"   ✅ SUCCESS: Generated {len(result)} characters")
                results[model] = {
                    "status": "SUCCESS", 
                    "output_length": len(result),
                    "sample": result[:100] + "..." if len(result) > 100 else result
                }
            else:
                print(f"   ❌ FAILED: {result}")
                results[model] = {"status": "FAILED", "output": result}
                
        except Exception as e:
            print(f"   💥 ERROR: {e}")
            results[model] = {"status": "ERROR", "error": str(e)}
        
        # Rate limiting
        await asyncio.sleep(4)
    
    print(f"\n📋 FINAL RESULTS:")
    print(f"=" * 60)
    
    successful_models = []
    for model, result in results.items():
        print(f"\n{model}:")
        if result["status"] == "SUCCESS":
            print(f"   ✅ {result['status']} - {result['output_length']} chars")
            print(f"   Sample: {result['sample']}")
            successful_models.append(model)
        else:
            print(f"   ❌ {result['status']}")
            if "error" in result:
                print(f"   Error: {result['error']}")
    
    print(f"\n🎯 BEST WORKING MODELS:")
    for model in successful_models:
        print(f"   - {model}")
    
    if successful_models:
        print(f"\n💡 RECOMMENDATION:")
        print(f"   Use: {successful_models[0]}")
        print(f"   Update OpenRouterClient.default_model to this value")
    else:
        print(f"\n⚠️  No free models are working properly!")
        print(f"   Consider using a paid model or different approach")
    
    print(f"\n📝 Full interaction logs saved to 'free_models_test.log'")


if __name__ == "__main__":
    asyncio.run(test_free_models())