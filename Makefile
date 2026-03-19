.PHONY: install dev test lint format release patch minor major

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
	pytest --cov=.

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
	docker build -t mcpscout .

docker-run:
	docker run -it mcpscout

# MCP Server
server:
	python -m mcp_server
