# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a newsletter automation bot that aggregates content from multiple sources (Readwise, Glasp, Feedbin, Snipd), processes it with AI, and generates publication-ready newsletter drafts. The system transforms a 4-6 hour manual process into a 15-30 minute review task.

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src
```

### Code Quality
```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

### Running the Application
```bash
# CLI entry point
newsletter-bot

# Direct module execution
python -m src.newsletter_bot

# Docker build and run
docker build -t newsletter-bot .
docker run newsletter-bot
```

## Architecture

### Core Components

- **src/newsletter_bot.py**: Main CLI entry point using Click framework
- **src/clients/**: API clients for external services (Readwise, Glasp, Feedbin, etc.)
- **src/core/**: Core business logic for content processing and newsletter generation
- **src/models/**: Pydantic models for data validation and settings management
- **scheduler/**: Celery-based task scheduling system
- **web/**: FastAPI web interface for manual control and monitoring

### External Dependencies

- **Content Sources**: Readwise, Glasp, Feedbin, Snipd APIs
- **AI Processing**: OpenRouter API for summarization and commentary
- **Images**: Unsplash API for relevant newsletter images  
- **Newsletter Platform**: Buttondown API for draft creation
- **Task Queue**: Redis + Celery for scheduled automation
- **Web Framework**: FastAPI + Uvicorn for web interface

### Configuration

The project uses pydantic-settings for configuration management. Environment variables are defined in the Settings model at src/models/settings.py and include API keys for all integrated services.

### Scheduling

By default, the system runs automated newsletter generation every Saturday at 9:00 AM using Celery cron scheduling. The schedule can be modified in scheduler/scheduler.py.

## Development Notes

- Python 3.11+ required
- Uses async/await patterns extensively for API calls
- Pydantic models provide type safety and validation
- Black formatter with 88-character line length
- pytest with asyncio support for testing
- Docker deployment ready with Dockerfile included