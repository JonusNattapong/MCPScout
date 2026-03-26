.PHONY: install dev test lint format release patch minor major docker-build docker-run docker-compose-up docker-compose-down run clean help

# Install
install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	playwright install chromium

# Testing
test:
	pytest

test-cov:
	pytest --cov=. --cov-report=html --cov-report=term

test-verbose:
	pytest -v

test-hybrid:
	pytest tests/test_hybrid.py -v

test-rate-limiter:
	pytest tests/test_rate_limiter.py -v

# Linting
lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	ruff format .

format-check:
	ruff format --check .

# Release
release:
	python scripts/release.py

patch:
	python scripts/release.py patch

minor:
	python scripts/release.py minor

major:
	python scripts/release.py major

# Docker
docker-build:
	docker build -t mcpsearch .

docker-run:
	docker run -it mcpsearch

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

docker-compose-logs:
	docker-compose logs -f

# MCP Server
server:
	python -m mcp_server

# CLI commands
run:
	python -m mcpsearch

search:
	python -m mcpsearch search -q "$(q)"

crawl:
	python -m mcpsearch crawl -u "$(u)"

read:
	python -m mcpsearch read -u "$(u)"

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.db" -delete 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/ 2>/dev/null || true

# Help
help:
	@echo "Available commands:"
	@echo "  install          - Install package in development mode"
	@echo "  dev              - Install with dev dependencies and Playwright"
	@echo "  test             - Run all tests"
	@echo "  test-cov         - Run tests with coverage report"
	@echo "  test-verbose     - Run tests with verbose output"
	@echo "  test-hybrid      - Run hybrid crawler tests"
	@echo "  test-rate-limiter - Run rate limiter tests"
	@echo "  lint             - Run linter"
	@echo "  lint-fix         - Run linter with auto-fix"
	@echo "  format           - Format code"
	@echo "  format-check     - Check code formatting"
	@echo "  server           - Run MCP server"
	@echo "  run              - Run MCPSearch CLI"
	@echo "  search           - Search (usage: make search q='query')"
	@echo "  crawl            - Crawl URL (usage: make crawl u='url')"
	@echo "  read             - Read URL (usage: make read u='url')"
	@echo "  docker-build     - Build Docker image"
	@echo "  docker-run       - Run Docker container"
	@echo "  docker-compose-up - Start services with docker-compose"
	@echo "  docker-compose-down - Stop services"
	@echo "  docker-compose-logs - View docker-compose logs"
	@echo "  clean            - Clean cache and build files"
	@echo "  release          - Create a release"
	@echo "  patch            - Bump patch version"
	@echo "  minor            - Bump minor version"
	@echo "  major            - Bump major version"
	@echo "  help             - Show this help message"
