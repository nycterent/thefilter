# Debug Scripts

This directory contains debugging and testing scripts for the newsletter automation system.

## Purpose

These scripts are used for:
- Testing individual components in isolation
- Debugging API interactions with external services
- Experimenting with different AI models and prompts
- Analyzing newsletter generation workflows

## Available Scripts

- `debug_simple.py` - Basic functionality tests
- `debug_detailed.py` - Detailed component testing
- `debug_editorial.py` - Editorial workflow debugging
- `debug_combined_prompt.py` - Combined prompt testing
- `debug_free_models.py` - Free AI model testing
- `debug_llama_combined.py` - Llama model specific tests
- `debug_llm_interactions.py` - LLM interaction debugging

## Usage

Most scripts can be run directly from the project root:

```bash
# Activate your virtual environment first
source venv/bin/activate

# Run a debug script
python debug/debug_simple.py
```

## Log Files

**Log files are NOT tracked in git.** When running debug scripts:
- Log files will be generated in this directory
- They are automatically ignored by git
- Clean them up periodically to avoid clutter

## Adding New Debug Scripts

When creating new debug scripts:
1. Name them with the `debug_` prefix
2. Keep them focused on a specific component or issue
3. Add brief documentation at the top of the script
4. Don't commit log files or temporary output

## Environment

Make sure you have:
- Virtual environment activated
- Required environment variables set (see `.env.example`)
- All dependencies installed (`pip install -e ".[dev]"`)