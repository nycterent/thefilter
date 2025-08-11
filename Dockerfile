# syntax=docker/dockerfile:1
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a separate stage for dependencies
FROM base as dependencies

# Copy dependency files and minimal structure for installation
COPY pyproject.toml README.md ./
COPY requirements.txt ./
COPY src/ ./src/

# Install Python dependencies in a single layer
RUN pip install --upgrade pip && \
    pip install -e . && \
    pip install -r requirements.txt 2>/dev/null || true

# Production stage
FROM base as production

# Copy installed packages and application code from dependencies stage
COPY --from=dependencies /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin
COPY --from=dependencies /app/src /app/src

# Copy additional application files
COPY scripts/check_briefing.py ./scripts/

# Create non-root user for security
RUN groupadd -r newsletter && useradd -r -g newsletter newsletter
RUN chown -R newsletter:newsletter /app
USER newsletter

CMD ["python", "-m", "src.newsletter_bot"]
