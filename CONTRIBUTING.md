# Contributing to Newsletter Bot

We love your input! We want to make contributing to Newsletter Bot as easy and transparent as possible.

## Development Process

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code lints
6. Issue that pull request!

## Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/newsletter-automation-bot.git
cd newsletter-automation-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black src/
isort src/
flake8 src/
mypy src/
```

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the version number in pyproject.toml
3. The PR will be merged once you have the sign-off of a maintainer

## Code Style

- We use Black for code formatting
- We use isort for import sorting
- We use flake8 for linting
- We use mypy for type checking
- Write meaningful commit messages
- Add docstrings to public functions

## Testing

- Write tests for new features
- Ensure all tests pass before submitting
- Use pytest for testing
- Mock external API calls in tests

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
