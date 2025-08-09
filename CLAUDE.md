# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a newsletter automation bot that aggregates content from multiple sources (Readwise, Glasp, RSS feeds), processes it with AI, and generates publication-ready newsletter drafts. The system transforms a 4-6 hour manual process into a 15-30 minute review task.

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

- **Content Sources**: Readwise, Glasp APIs, and RSS feeds
- **AI Processing**: OpenRouter API for summarization and commentary
- **Images**: Unsplash API for relevant newsletter images  
- **Newsletter Platform**: Buttondown API for draft creation
- **Task Queue**: Redis + Celery for scheduled automation
- **Web Framework**: FastAPI + Uvicorn for web interface

### Configuration

The project supports two configuration methods:

#### Environment Variables (.env file)
Traditional configuration using environment variables defined in the Settings model at src/models/settings.py.

#### Infisical Secrets Management (Recommended)
For production deployments, the project integrates with Infisical for centralized secrets management. This includes both local development and CI/CD integration:

**Setup:**
```bash
# Enable Infisical in environment
USE_INFISICAL=true

# Infisical configuration
INFISICAL_HOST=https://your-selfhosted-infisical.com
INFISICAL_PROJECT_ID=your-project-id
INFISICAL_ENVIRONMENT=dev
INFISICAL_SECRET_PATH=/

# Authentication (choose one method):
# Method 1: Universal Auth (recommended)
INFISICAL_CLIENT_ID=your-client-id
INFISICAL_CLIENT_SECRET=your-client-secret

# Method 2: Token-based
INFISICAL_TOKEN=your-auth-token
```

**Secret Names in Infisical:**
- `READWISE_API_KEY` - Readwise API key
- `GLASP_API_KEY` - Glasp API key  
- `RSS_FEEDS` - RSS feed URLs (comma-separated list)
- `BUTTONDOWN_API_KEY` - Buttondown API key
- `OPENROUTER_API_KEY` - OpenRouter API key
- `UNSPLASH_API_KEY` - Unsplash API key

The Settings model automatically loads secrets from Infisical when `USE_INFISICAL=true`, with fallback to environment variables.

#### GitHub Actions Integration
The repository uses Infisical's GitHub App integration for automatic secrets sync:

**Setup Process:**
1. Configure Infisical GitHub App integration in your project
2. Authorize the app for your repository
3. Secrets are automatically synced to GitHub repository secrets

**Synced Secrets:** (automatically available as `${{ secrets.SECRET_NAME }}`)
- `READWISE_API_KEY`, `GLASP_API_KEY`, `RSS_FEEDS`
- `BUTTONDOWN_API_KEY`, `OPENROUTER_API_KEY`, `UNSPLASH_API_KEY`

**Workflow Features:**
- Direct access to synced secrets in workflows
- No additional authentication steps required
- Production deployment with environment protection
- Automatic sync when secrets change in Infisical

See [GitHub Actions + Infisical Setup Guide](docs/github-infisical-setup.md) for complete configuration instructions.

### Scheduling

By default, the system runs automated newsletter generation every Saturday at 9:00 AM using Celery cron scheduling. The schedule can be modified in scheduler/scheduler.py.

## Development Notes

- Python 3.11+ required
- Uses async/await patterns extensively for API calls
- Pydantic models provide type safety and validation
- Black formatter with 88-character line length
- pytest with asyncio support for testing
- Docker deployment ready with Dockerfile included