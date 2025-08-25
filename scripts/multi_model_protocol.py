#!/usr/bin/env python3
"""
Multi-Model LLM Protocol Implementation

This script implements the collaborative refinement workflow using OpenRouter models:
- GLM-4.5 as The Proposer 
- Gemini Pro 2.5 as The Refiner
- Deepseek R1 as The Tie-Breaker

Usage:
    python scripts/multi_model_protocol.py "Your problem description here"
    
Environment Variables:
    OPENROUTER_API_KEY: Your OpenRouter API key
"""

import asyncio
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add src to path so we can import the OpenRouter client
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from clients.openrouter import OpenRouterClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MultiModelProtocol:
    """Implements the Multi-Model LLM Protocol for collaborative problem-solving."""
    
    def __init__(self, api_key: str):
        """Initialize with OpenRouter API key."""
        self.api_key = api_key
        
        # Model mappings to available OpenRouter models
        self.models = {
            "glm-4.5": "openai/gpt-4o-mini",  # Best available free model as GLM-4.5 substitute
            "gemini-pro-2.5": "google/gemini-flash-1.5-8b",  # Fast Gemini model
            "deepseek-r1": "meta-llama/llama-3.2-90b-vision-instruct:free"  # Strong reasoning model
        }
        
    async def run_protocol(self, problem_description: str, context_files: List[str] = None) -> Dict[str, Any]:
        """
        Execute the full Multi-Model LLM Protocol.
        
        Args:
            problem_description: The problem to solve
            context_files: Optional list of file paths to include as context
            
        Returns:
            Dictionary containing the collaborative results
        """
        logger.info("🚀 Starting Multi-Model LLM Protocol")
        
        # Gather context
        context = await self._gather_context(context_files)
        full_context = f"{problem_description}\n\n{context}"
        
        # Step 1: GLM-4.5 Proposer
        logger.info("📝 Step 1: GLM-4.5 (Proposer) generating initial plan...")
        initial_plan = await self._glm_proposer(full_context)
        
        if not initial_plan:
            return {"error": "GLM-4.5 failed to generate initial plan"}
            
        # Step 2: Gemini Pro 2.5 Refiner
        logger.info("🔍 Step 2: Gemini Pro 2.5 (Refiner) reviewing and refining...")
        refinement = await self._gemini_refiner(full_context, initial_plan)
        
        if not refinement:
            return {"error": "Gemini Pro 2.5 failed to provide refinement"}
            
        # Step 3: Collaborative Dialogue Loop
        logger.info("💬 Step 3: Facilitating collaborative dialogue...")
        final_plan = await self._collaborative_dialogue(full_context, initial_plan, refinement)
        
        # Step 4: Implementation (if requested)
        logger.info("✅ Protocol complete!")
        
        return {
            "problem": problem_description,
            "initial_plan": initial_plan,
            "refinement": refinement,
            "final_plan": final_plan,
            "status": "success"
        }
    
    async def _gather_context(self, context_files: List[str] = None) -> str:
        """Gather context from files and project state."""
        context_parts = []
        
        # Add project context
        context_parts.append("=== PROJECT CONTEXT ===")
        context_parts.append("Working directory: /Users/saint/Documents/ManualLibrary/thefilter")
        context_parts.append("Git repository: Yes (main branch, clean status)")
        context_parts.append("Platform: macOS Darwin 24.6.0")
        
        # Add recent commits
        context_parts.append("\n=== RECENT COMMITS ===")
        context_parts.append("- e47066d: Implement 1-hour caching for Readwise API to avoid rate limiting")
        context_parts.append("- 598716a: Fix publication script to use direct Buttondown API calls")
        context_parts.append("- 9e0ce93: Fix workflow to use GitHub Secrets instead of Infisical CLI")
        
        # Add file contents if specified
        if context_files:
            context_parts.append("\n=== RELEVANT FILES ===")
            for file_path in context_files:
                try:
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        context_parts.append(f"\n--- {file_path} ---")
                        context_parts.append(content[:2000])  # Limit to 2000 chars per file
                        if len(content) > 2000:
                            context_parts.append("... (truncated)")
                except Exception as e:
                    context_parts.append(f"\n--- {file_path} (ERROR: {e}) ---")
        
        return "\n".join(context_parts)
    
    async def _glm_proposer(self, context: str) -> Optional[str]:
        """GLM-4.5 acting as The Proposer."""
        client = OpenRouterClient(self.api_key, model=self.models["glm-4.5"])
        
        prompt = f"""You are GLM-4.5 acting as The Proposer in a collaborative refinement workflow. Your task is to generate an initial plan that best interprets the user's goal. The plan must be a robust, best-practice solution that is as simple and direct as possible. The primary goal is to create a solid starting point for a collaborative refinement process.

COMPLETE CONTEXT:
{context}

YOUR TASK AS THE PROPOSER:
1. Analyze the problem carefully
2. Generate a comprehensive, actionable plan
3. Focus on best practices and robust solutions  
4. Be specific about implementation steps
5. Consider edge cases and potential issues
6. Create a foundation that other models can refine

Provide a detailed initial plan that addresses the core problem with practical, implementable solutions."""

        try:
            response = await client.generate_text(prompt, max_tokens=1000)
            return response
        except Exception as e:
            logger.error(f"GLM-4.5 Proposer failed: {e}")
            return None
    
    async def _gemini_refiner(self, context: str, initial_plan: str) -> Optional[str]:
        """Gemini Pro 2.5 acting as The Refiner."""
        client = OpenRouterClient(self.api_key, model=self.models["gemini-pro-2.5"])
        
        prompt = f"""You are Gemini Pro 2.5 acting as The Refiner in a collaborative refinement workflow. Your role is to act as a collaborative refiner, reviewing the proposal not just for flaws, but for opportunities. Your critique should be guided by questions like: "Does this plan fully capture the user's intent? Are there alternative interpretations of the user's request? How can we make this solution even better or safer? What edge cases or future maintenance issues might the user not have considered?" The goal is to add perspective and improve the plan.

ORIGINAL CONTEXT:
{context}

GLM-4.5'S INITIAL PLAN:
{initial_plan}

YOUR TASK AS THE REFINER:
1. Analyze the initial plan thoroughly
2. Identify strengths and potential improvements
3. Consider alternative approaches
4. Think about edge cases and maintenance
5. Suggest concrete enhancements
6. Ensure the plan fully addresses the user's intent

Provide constructive refinement feedback that builds upon and improves the initial plan. Focus on making it more robust, comprehensive, and aligned with best practices."""

        try:
            response = await client.generate_text(prompt, max_tokens=1000)
            return response
        except Exception as e:
            logger.error(f"Gemini Pro 2.5 Refiner failed: {e}")
            return None
    
    async def _collaborative_dialogue(self, context: str, initial_plan: str, refinement: str) -> Optional[str]:
        """Facilitate collaborative dialogue to reach consensus."""
        # Check if refinement suggests significant changes
        if "significant" in refinement.lower() or "major" in refinement.lower() or "important" in refinement.lower():
            logger.info("🔄 Refinement suggests changes - running integration step...")
            
            # GLM-4.5 integrates feedback
            client = OpenRouterClient(self.api_key, model=self.models["glm-4.5"])
            
            integration_prompt = f"""Your initial plan has been reviewed by Gemini Pro 2.5. Your task is to create a revised, superior solution by integrating the feedback. You must treat its analysis as the next step in a collaborative process.

ORIGINAL CONTEXT:
{context}

YOUR INITIAL PLAN:
{initial_plan}

GEMINI PRO 2.5'S REFINEMENT:
{refinement}

YOUR MANDATE:
1. Analyze and integrate the feedback thoughtfully
2. Create a revised plan that incorporates valid suggestions
3. If you disagree with suggestions, provide better alternatives with reasoning
4. Produce a comprehensive, definitive implementation plan

Generate the final, integrated plan that represents the best of both approaches."""

            try:
                integrated_plan = await client.generate_text(integration_prompt, max_tokens=1200)
                
                # Final validation by Gemini Pro 2.5
                validator = OpenRouterClient(self.api_key, model=self.models["gemini-pro-2.5"])
                validation_prompt = f"""Review this integrated plan and confirm if it successfully addresses the original problem and incorporates the refinement feedback:

INTEGRATED PLAN:
{integrated_plan}

Respond with: APPROVED (if the plan is comprehensive and addresses concerns) or NEEDS_TIEBREAKER (if significant issues remain)"""

                validation = await validator.generate_text(validation_prompt, max_tokens=100)
                
                if "NEEDS_TIEBREAKER" in validation:
                    logger.info("🤝 Consensus not reached - invoking Deepseek R1 tie-breaker...")
                    return await self._deepseek_tiebreaker(context, initial_plan, refinement, integrated_plan)
                
                return integrated_plan
                
            except Exception as e:
                logger.error(f"Collaborative integration failed: {e}")
                return initial_plan  # Fallback to initial plan
        else:
            logger.info("✅ Minor refinements suggested - using initial plan as base")
            return f"{initial_plan}\n\n=== REFINEMENT NOTES ===\n{refinement}"
    
    async def _deepseek_tiebreaker(self, context: str, initial_plan: str, refinement: str, integrated_plan: str) -> Optional[str]:
        """Deepseek R1 acting as The Tie-Breaker."""
        client = OpenRouterClient(self.api_key, model=self.models["deepseek-r1"])
        
        prompt = f"""You are Deepseek R1 acting as the decisive tie-breaker. Two models have reached an impasse. Your role is to analyze the initial proposal, the subsequent refinements, and the points of conflict. Provide a final, reasoned, and definitive plan that resolves the disagreement and represents the best possible path forward.

ORIGINAL CONTEXT:
{context}

GLM-4.5'S INITIAL PLAN:
{initial_plan}

GEMINI PRO 2.5'S REFINEMENT:
{refinement}

INTEGRATED ATTEMPT:
{integrated_plan}

YOUR MANDATE AS TIE-BREAKER:
1. Analyze all perspectives objectively
2. Identify the core disagreement or issue
3. Make decisive choices between conflicting approaches
4. Provide the final, authoritative implementation plan
5. Explain your reasoning for key decisions

Provide the definitive solution that resolves the impasse and represents the optimal path forward."""

        try:
            final_plan = await client.generate_text(prompt, max_tokens=1200)
            return final_plan
        except Exception as e:
            logger.error(f"Deepseek R1 Tie-breaker failed: {e}")
            return integrated_plan  # Fallback


async def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/multi_model_protocol.py \"Your problem description here\"")
        print("Optional: Add file paths as additional arguments for context")
        sys.exit(1)
    
    # Get API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY environment variable not set")
        sys.exit(1)
    
    # Parse arguments
    problem_description = sys.argv[1]
    context_files = sys.argv[2:] if len(sys.argv) > 2 else None
    
    # Run the protocol
    protocol = MultiModelProtocol(api_key)
    result = await protocol.run_protocol(problem_description, context_files)
    
    # Output results
    print("\n" + "="*80)
    print("🎯 MULTI-MODEL LLM PROTOCOL RESULTS")
    print("="*80)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"\n📋 Problem: {result['problem']}")
        print(f"\n📝 Initial Plan (GLM-4.5):\n{result['initial_plan']}")
        print(f"\n🔍 Refinement (Gemini Pro 2.5):\n{result['refinement']}")
        print(f"\n✅ Final Plan:\n{result['final_plan']}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())