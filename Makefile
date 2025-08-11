# Newsletter Bot Docker Management
.PHONY: build build-dev run run-dev test health clean cache-clean help

# Default target
help:
	@echo "Newsletter Bot Docker Commands:"
	@echo "  build          Build production Docker image"
	@echo "  build-dev      Build development Docker image"
	@echo "  run            Run newsletter generation (dry-run)"
	@echo "  run-prod       Run newsletter generation (production)"
	@echo "  run-dev        Run development container with hot reload"
	@echo "  test           Run tests in Docker container"
	@echo "  health         Run health check"
	@echo "  shell          Open shell in development container"
	@echo "  logs           Show container logs"
	@echo "  clean          Clean up Docker images and containers"
	@echo "  cache-clean    Clean Docker build cache"

# Build targets
build:
	@echo "🔨 Building production Docker image..."
	docker build --target production -t newsletter-bot:latest .

build-dev:
	@echo "🔨 Building development Docker image..."
	docker build --target base -t newsletter-bot:dev .

build-cached:
	@echo "🔨 Building with BuildKit cache..."
	docker buildx build \
		--target production \
		--cache-from type=local,src=.docker-cache \
		--cache-to type=local,dest=.docker-cache,mode=max \
		-t newsletter-bot:latest .

# Run targets
run: build
	@echo "🚀 Running newsletter bot (dry-run)..."
	docker-compose up newsletter-bot

run-prod: build
	@echo "🚀 Running newsletter bot (PRODUCTION)..."
	docker run --rm --env-file .env newsletter-bot:latest python -m src.newsletter_bot generate

run-dev: build-dev
	@echo "🚀 Starting development environment..."
	docker-compose --profile dev up newsletter-bot-dev

# Utility targets
test: build-dev
	@echo "🧪 Running tests..."
	docker run --rm -v $(PWD):/app newsletter-bot:dev pytest tests/ -v

health: build
	@echo "🔍 Running health check..."
	docker run --rm --env-file .env newsletter-bot:latest python -m src.newsletter_bot health

shell: build-dev
	@echo "🐚 Opening development shell..."
	docker run --rm -it -v $(PWD):/app --env-file .env newsletter-bot:dev /bin/bash

logs:
	@echo "📋 Showing container logs..."
	docker-compose logs -f newsletter-bot

# Cleanup targets
clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker-compose down --remove-orphans
	docker system prune -f
	docker images | grep newsletter-bot | awk '{print $$3}' | xargs -r docker rmi

cache-clean:
	@echo "🧹 Cleaning Docker build cache..."
	docker builder prune -f
	rm -rf .docker-cache

# Development workflow
dev-setup: build-dev
	@echo "🛠️  Setting up development environment..."
	@echo "Run 'make run-dev' to start development container"
	@echo "Run 'make shell' to access development shell"

# CI/CD helpers
ci-build:
	@echo "🔧 Building for CI/CD..."
	docker buildx build \
		--platform linux/amd64 \
		--target production \
		--cache-from type=gha \
		--cache-to type=gha,mode=max \
		-t newsletter-bot:ci .

# Quick commands
.PHONY: quick-test quick-health quick-run
quick-test: test
quick-health: health
quick-run: run