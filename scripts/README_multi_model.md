# Multi-Model LLM Protocol

This implementation provides collaborative problem-solving using multiple AI models through OpenRouter.

## Overview

The protocol implements a 3-stage collaborative workflow:
1. **GLM-4.5 (Proposer)**: Generates initial comprehensive plan
2. **Gemini Pro 2.5 (Refiner)**: Reviews and suggests improvements  
3. **Deepseek R1 (Tie-breaker)**: Resolves conflicts if needed

## Setup

1. Get an OpenRouter API key from https://openrouter.ai/
2. Set environment variable:
```bash
export OPENROUTER_API_KEY="your-key-here"
```

## Usage

### Basic Usage
```bash
python scripts/multi_model_protocol.py "Your problem description here"
```

### With Context Files
```bash
python scripts/multi_model_protocol.py "Optimize my code" src/main.py src/utils.py
```

### Test the Implementation
```bash
python scripts/test_multi_model.py
```

## Examples

### Newsletter Optimization
```bash
python scripts/multi_model_protocol.py "I need to optimize my newsletter generation system for better performance and content quality" src/core/newsletter.py src/clients/openrouter.py
```

### Code Architecture Review
```bash
python scripts/multi_model_protocol.py "Review and improve the architecture of my RSS processing system" src/clients/rss.py src/core/newsletter.py
```

### Feature Implementation
```bash
python scripts/multi_model_protocol.py "Add a caching layer to reduce API calls and improve performance"
```

## Model Mappings

The script uses these OpenRouter models:
- **GLM-4.5**: `openai/gpt-4o-mini` (Best available free model)
- **Gemini Pro 2.5**: `google/gemini-flash-1.5-8b` (Fast reasoning)
- **Deepseek R1**: `meta-llama/llama-3.2-90b-vision-instruct:free` (Strong analysis)

## Output

The script provides:
- Initial plan from the proposer
- Refinement suggestions 
- Final collaborative plan
- Full dialogue history

Results are displayed in the terminal and can be saved to files for further analysis.

## Integration with Claude Code

This script complements Claude Code by:
- Providing multiple AI perspectives on complex problems
- Generating comprehensive implementation plans
- Offering collaborative refinement of solutions
- Creating detailed context-aware recommendations

Use it when you need:
- Multiple expert opinions on architecture decisions
- Comprehensive planning for complex features
- Validation of implementation approaches
- Creative problem-solving with diverse AI perspectives