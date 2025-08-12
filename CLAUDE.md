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

# Run all tests with verbose output
./venv/bin/pytest tests/ -v

# Run specific test file
./venv/bin/pytest tests/test_cli.py -v

# Run tests with coverage
pytest --cov=src
```

### Code Quality
```bash
# Format code
black src/
./venv/bin/black src/

# Sort imports
isort src/
./venv/bin/isort --check-only src/

# Lint code - critical errors only
./venv/bin/flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Lint code - full check
./venv/bin/flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics

# Type checking (currently disabled due to model refactoring)
mypy src/
```

### Local CI Testing
```bash
# Run complete CI pipeline locally before pushing
./scripts/test-ci.sh

# Test specific components individually
./venv/bin/flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
./venv/bin/black --check src/
./venv/bin/isort --check-only src/
```

### Docker Development
```bash
# Build and run using Makefile (recommended)
make build        # Build production image
make build-dev    # Build development image
make run          # Run newsletter generation (dry-run)
make test         # Run tests in Docker
make shell        # Open development shell
make clean        # Clean up Docker resources

# Quick development workflow
make dev-setup    # Setup development environment
make run-dev      # Start development container with hot reload

# Additional Makefile commands
make health       # Run health check
make logs         # Show container logs
make ci-build     # Build for CI/CD with platform optimization
```

### Running the Application
```bash
# CLI entry point
newsletter-bot

# Direct module execution
python -m src.newsletter_bot
./venv/bin/python -m src.newsletter_bot

# Show CLI help
./venv/bin/python -m src.newsletter_bot --help

# Generate newsletter (dry-run mode)
./venv/bin/python -m src.newsletter_bot generate --dry-run

# Check configuration
./venv/bin/python -m src.newsletter_bot config

# Docker build and run
docker build -t newsletter-bot .
docker run newsletter-bot
```

## Architecture

### Core Components

- **src/newsletter_bot.py**: Main CLI entry point using Click framework
- **src/clients/**: API clients for external services (Readwise, Glasp, Feedbin, etc.)
- **src/core/**: Core business logic for content processing and newsletter generation
  - `newsletter.py`: Main newsletter generation with template system (supports 'the_filter' format)
  - `qacheck.py`: Content quality assurance and validation
  - `sanitizer.py`: Content sanitization and safety checks  
  - `secrets.py`: Infisical secrets management integration
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
- Mypy type checking temporarily disabled during model refactoring
- Virtual environment required - always use `./venv/bin/` prefix for commands
- Entry point: `src.newsletter_bot:cli` defined in pyproject.toml

## Testing Strategy

Test files are organized by component:
- `test_cli.py` - CLI interface testing  
- `test_newsletter.py` - Core newsletter generation
- `test_models.py` - Pydantic model validation
- `test_settings.py` - Configuration and settings
- `test_integration.py` - End-to-end workflow testing
- `test_infisical.py` - Secrets management testing
- `test_sanitizer.py` - Content sanitization testing
- `test_editorial_workflow.py` - Editorial process testing
- `test_check_briefing.py` - Content quality checks

Debug tools available in `debug/` directory for troubleshooting specific components.

## Quick Development Workflow

1. Activate virtual environment: `source venv/bin/activate`
2. Install in dev mode: `pip install -e ".[dev]"`
3. Run local CI checks: `./scripts/test-ci.sh`
4. Test CLI functionality: `./venv/bin/python -m src.newsletter_bot --help`
5. Run dry-run generation: `./venv/bin/python -m src.newsletter_bot generate --dry-run`