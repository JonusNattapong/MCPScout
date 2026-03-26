# AGENTS.md - MCPSearch Development Guide

## Project Overview

MCPSearch is an AI-powered multi-source intelligence platform with MCP (Model Context Protocol) interface. It features hybrid crawling (httpx + Playwright + Camoufox), parallel search aggregation, social media scrapers, and advanced content extraction.

## Build & Development Commands

```bash
# Using Makefile (recommended)
make install      # pip install -e .
make dev          # install with dev deps + playwright
make server       # python -m mcp_server

# Or manual
pip install -e .
pip install -e ".[dev]"
playwright install chromium

# Run MCP server (stdio transport)
python -m mcp_server

# CLI commands
mcpsearch search -q "query"
mcpsearch crawl -u "https://example.com"
mcpsearch read -u "https://example.com"

# Docker
make docker-build
make docker-run
```

## Version Management

Version is managed from single source: `mcpspider/version.py`

```bash
# Auto-release with changelog generation
make patch        # 1.0.0 -> 1.0.1 (bug fixes)
make minor        # 1.0.0 -> 1.1.0 (new features)
make major        # 1.0.0 -> 2.0.0 (breaking changes)

# Or directly
python scripts/release.py patch
python scripts/release.py 1.2.3  # explicit version
```

**Release process:**
1. Bumps version in `version.py` and `pyproject.toml`
2. Generates changelog from git commits (conventional commits)
3. Updates `CHANGELOG.md`
4. Creates git commit + tag
5. Pushes to GitHub
6. Creates GitHub release

**Conventional commits for changelog:**
- `feat:` -> Added
- `fix:` -> Fixed
- `refactor:`, `docs:`, `perf:` -> Changed
- `remove:`, `break:` -> Removed

## Testing

```bash
make test         # all tests
make test-cov     # with coverage

# Or manual
pytest
pytest --cov=.
pytest tests/test_crawler.py     # single file
pytest -k "test_search"          # by name
```

## Linting & Formatting

```bash
make lint         # ruff check .
make lint-fix     # ruff check --fix .
make format       # ruff format .
```

## Code Style Guidelines

### Imports
- `from __future__ import annotations` at top of every file
- Group: stdlib → third-party → local
- Absolute imports from project root
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

mcp = FastMCP("mcpsearch")

@mcp.tool()
async def tool_name(
    param: Annotated[type, "description for AI"],
) -> str:
    """Docstring becomes tool description."""
    return result_string
```

## Project Structure

```
MCPSearch/
├── mcp_server/           # FastMCP server (21 tools)
│   ├── server.py         # Main MCP tools
│   └── unified.py        # Unified mcpsearch interface
├── crawler/
│   ├── engine.py         # Async httpx crawler
│   ├── hybrid.py         # httpx + Playwright
│   ├── stealth.py        # Camoufox stealth browser
│   ├── smart_crawler.py  # Heuristic link filtering
│   └── extractor.py      # Tables, code, images
├── search/
│   └── aggregator.py     # Multi-engine parallel search
├── social/
│   ├── reddit.py         # Reddit scraper
│   ├── twitter.py        # Twitter/X scraper
│   ├── youtube.py        # YouTube scraper
│   └── github.py         # GitHub API scraper
├── summarizer/
│   └── ai_summarizer.py  # OpenAI summarization
├── utils/
│   └── rate_limiter.py   # Per-domain rate limiting
├── mcpspider/
│   └── version.py        # Single version source
├── scripts/
│   └── release.py        # Auto-release script
├── cli.py                # CLI interface
├── __main__.py           # Module entry point
├── Makefile              # Common commands
├── pyproject.toml        # Package config
└── Dockerfile            # Docker support
```

## Key Patterns

- **Hybrid crawling**: httpx → Playwright → Camoufox auto-fallback
- **Stealth mode**: Bypasses Cloudflare, Akamai, DataDome
- **Smart filtering**: `SmartCrawler` with heuristic link scoring
- **Parallel search**: `SearchAggregator` with `asyncio.gather()`
- **Content extraction**: `ContentExtractor` for tables/code/images
- **Rate limiting**: Per-domain tracking with adaptive delays
- **Social scrapers**: No API keys required (public endpoints)

## MCP Tools

| Category | Tools |
|----------|-------|
| Web Search | `web_search`, `search_and_summarize`, `smart_search`, `deep_search` |
| Web Crawl | `hybrid_crawl`, `crawl_url`, `extract_content`, `crawl_recursive` |
| Reddit | `search_reddit`, `get_subreddit`, `get_reddit_post` |
| Twitter/X | `search_twitter`, `get_user_tweets` |
| YouTube | `search_youtube`, `get_youtube_channel`, `get_youtube_content` |
| GitHub | `search_github`, `get_github_user`, `get_github_repo`, `get_github_readme` |
| Unified | `mcpsearch`, `mcpsearch_multi` |

## Environment Variables

- `OPENAI_API_KEY`: Optional, for AI summarization
- No other required env vars
