# AGENTS.md - MCPSpider Development Guide

## Project Overview

MCPSpider is an AI-powered multi-source search engine with MCP (Model Context Protocol) interface. It features hybrid crawling (httpx + Playwright), parallel search aggregation, smart link filtering, and advanced content extraction.

## Build & Development Commands

```bash
# Install dependencies
pip install -e .
pip install -e ".[dev]"  # with dev tools
playwright install chromium  # for JS rendering

# Run MCP server (stdio transport)
python -m mcpspider server

# CLI commands
mcpspider search -q "query" -s duckduckgo google
mcpspider crawl -u "https://example.com"
mcpspider read -u "https://example.com" -f text  # view in terminal

# Docker
docker build -t mcpspider .
docker run -it mcpspider server
```

## Testing

```bash
pytest                           # all tests
pytest tests/test_crawler.py     # single file
pytest -k "test_search"          # by name
pytest --cov=mcpspider           # coverage
```

## Linting & Formatting

```bash
ruff check .           # lint
ruff check --fix .     # auto-fix
ruff format .          # format
ruff format --check .  # check only
```

## Code Style Guidelines

### Imports
- `from __future__ import annotations` at top of every file
- Group: stdlib → third-party → local
- Absolute imports from `mcpspider` package
- No wildcard imports

### Types
- Python 3.11+ type hints throughout
- `Annotated[type, "description"]` for MCP tool parameters
- `dataclass` with `field(default_factory=...)` for mutable defaults
- Type aliases: `ExtractMode = Literal["text", "markdown", "structured"]`

### Naming
- Classes: `PascalCase` (e.g., `HybridCrawler`, `SearchResult`)
- Functions: `snake_case` (e.g., `hybrid_crawl`, `smart_search`)
- Private: `_leading_underscore` (e.g., `_crawl_url`)
- Constants: `UPPER_SNAKE_CASE`

### Async Patterns
- `async`/`await` for all I/O
- `asyncio.Semaphore` for concurrency
- `asyncio.gather()` for parallel ops
- `httpx.AsyncClient` for HTTP (not `requests`)
- Playwright async API for browser rendering

### Error Handling
- `logging.getLogger(__name__)` for logs
- Return errors in result objects, don't raise
- `try/except Exception as e` with logging
- Tool functions return error strings, not exceptions

### Docstrings
- Module docstring at top
- Class: brief description
- Function: one-line + Args if complex
- MCP tool docstrings = AI-visible descriptions

### MCP Tool Pattern
```python
from typing import Annotated
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mcpspider")

@mcp.tool()
async def tool_name(
    param: Annotated[type, "description for AI"],
) -> str:
    """Docstring becomes tool description."""
    return result_string
```

## Architecture

```
mcpspider/
├── mcp_server/         # FastMCP server (10 tools)
├── crawler/
│   ├── engine.py       # Async httpx crawler
│   ├── hybrid.py       # httpx + Playwright smart routing
│   ├── smart_crawler.py # Heuristic link filtering
│   └── extractor.py    # Tables, code, images extraction
├── search/
│   └── aggregator.py   # Multi-engine parallel search
├── summarizer/
│   └── ai_summarizer.py
├── cli.py              # CLI: server, search, crawl, read
└── __main__.py
```

## Key Patterns

- **Hybrid crawling**: Try httpx first, auto-detect JS, fallback to Playwright
- **Smart filtering**: `SmartCrawler` with heuristic link scoring
- **Parallel search**: `SearchAggregator` with `asyncio.gather()`
- **Content extraction**: `ContentExtractor` for tables/code/images
- **Result containers**: `@dataclass` with `field(default_factory=list)`

## Hybrid Crawler (2026 Pattern)

```python
from mcpspider.crawler.hybrid import HybridCrawler

crawler = HybridCrawler()
result = await crawler.crawl("https://example.com")
# Auto-detects JS, uses httpx or Playwright accordingly
```

## Environment Variables

- `OPENAI_API_KEY`: Optional, for AI summarization
- No other required env vars
