# MCPSearch

**AI-powered multi-source research and crawling platform with MCP integration**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)

## Overview

MCPSearch is a self-hosted research stack for agents and developers. It combines:

- parallel web search across multiple engines
- HTTP + browser + stealth crawling
- social and developer-source collection
- structured content extraction
- MCP-native tool exposure
- higher-level research workflows via `investigate`, `compare`, and `trending`

The project has grown beyond a simple crawler. The current shape is:

- 29 MCP tools in [`mcp_server/server.py`](mcp_server/server.py)
- a unified `mcpsearch` / `mcpsearch_multi` interface
- shared action routing in [`mcp_server/handlers.py`](mcp_server/handlers.py)
- a flagship orchestration layer in [`agents/research_agent.py`](agents/research_agent.py)

## Current Capabilities

- Web search: DuckDuckGo, Google, and Bing aggregation
- Crawling modes:
  `fast` via HTTP only, `hybrid` via HTTP + Playwright, `stealth` via anti-bot fallback
- Extraction:
  markdown/text extraction, tables, code blocks, images, metadata, JSON-LD/OpenGraph/Microdata via `extruct`
- Fast parsing:
  `selectolax` on hot search parsing paths with BeautifulSoup fallback
- Social sources:
  Reddit, Twitter/X, YouTube, GitHub
- HTTP caching:
  shared async client factory with optional Hishel-backed caching on request-heavy paths
- Research workflows:
  `research_agent`, `investigate`, `compare`, `trending`
- Tool discovery:
  `list_tools`, `describe_tools`, `get_crawl_stats`

## Install

### Basic install

```bash
git clone https://github.com/JonusNattapong/MCPSearch.git
cd MCPSearch
pip install -e .
playwright install chromium
```

### Development install

```bash
make dev
```

or:

```bash
pip install -e ".[dev]"
playwright install chromium
```

### Optional stealth dependency

`crawler/stealth.py` can use Camoufox when it is installed. If Camoufox is not available, MCPSearch falls back to Playwright-based stealth behavior.

### Environment variables

- `OPENAI_API_KEY`
  Optional. Used by summarization flows when AI summaries are enabled.

## Quick Start

### CLI

```bash
# Search
mcpsearch search -q "AI agents"

# Crawl a page
mcpsearch crawl -u "https://example.com"

# Read a page in terminal-friendly format
mcpsearch read -u "https://example.com"

# Research workflow
mcpsearch research --query "browser fingerprinting" --depth deep --summarize

# Compare topics
mcpsearch compare --compare "React" "Vue" "Svelte" --depth medium

# Trending view
mcpsearch trending --max-results 10

# Run MCP server
mcpsearch server
```

### Python / MCP-facing examples

```python
# Unified tool
mcpsearch(action="search", query="LLM agents", limit=5)
mcpsearch(action="crawl", url="https://example.com", mode="hybrid")
mcpsearch(action="reddit", query="python", subreddit="learnpython")
mcpsearch(action="github", query="browser automation", sort="stars")

# Multi-action orchestration
mcpsearch_multi(actions='[
  {"action":"search","query":"agent memory patterns"},
  {"action":"reddit","query":"LocalLLaMA"},
  {"action":"github","query":"llm agents","sort":"stars"}
]')

# Flagship research tools
investigate(topic="Python async scraping", depth="deep", include_social=True)
compare(topics="React,Vue,Svelte", depth="medium", max_sources=3)
trending(platforms="reddit,github", limit=10)
```

## MCP Integration

### Claude Desktop

```json
{
  "mcpServers": {
    "mcpsearch": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/MCPSearch",
      "env": {
        "OPENAI_API_KEY": ""
      }
    }
  }
}
```

### Cursor

```json
{
  "mcpServers": {
    "mcpsearch": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/path/to/MCPSearch"
    }
  }
}
```

### Custom MCP client

```json
{
  "command": "python",
  "args": ["-m", "mcp_server"],
  "transport": "stdio"
}
```

## Tool Map

### Unified tools

- `mcpsearch`
- `mcpsearch_multi`

### Search and crawl tools

- `web_search`
- `search_and_summarize`
- `smart_search`
- `deep_search`
- `crawl_url`
- `hybrid_crawl`
- `crawl_recursive`
- `extract_content`
- `get_crawl_stats`

### Social tools

- `search_reddit`
- `get_subreddit`
- `get_reddit_post`
- `search_twitter`
- `get_user_tweets`
- `search_youtube`
- `get_youtube_channel`
- `get_youtube_content`
- `search_github`
- `get_github_user`
- `get_github_repo`
- `get_github_readme`

### Research tools

- `research_agent`
- `investigate`
- `compare`
- `trending`

### Discovery tools

- `list_tools`
- `describe_tools`

## Recommended Entry Points

If you are integrating MCPSearch into an agent:

- start with `list_tools` and `describe_tools`
- prefer `mcpsearch` for simple routing
- use `mcpsearch_multi` when you want parallel source gathering
- use `investigate` for richer topic-oriented research
- use `compare` when the output should be side-by-side
- use `trending` for source discovery and early signal collection

## Research Workflows

### `investigate`

Best when you want one topic explored across search, crawl, and social sources.

```python
investigate(
    topic="anti-bot browser strategies",
    depth="deep",
    include_social=True,
    include_summary=True,
    max_sources=5,
)
```

### `compare`

Best when you want repeated shallow or medium investigations and a compact comparison result.

```python
compare(
    topics="Playwright,Selenium,Camoufox",
    depth="medium",
    max_sources=3,
)
```

### `trending`

Best when you want new leads before deeper crawling.

```python
trending(
    platforms="reddit,github",
    limit=10,
)
```

## Architecture

### Request flow

```text
Query / URL / Topic
        |
        v
  mcpsearch / direct tool
        |
        v
 mcp_server/handlers.py
        |
        +--> search/aggregator.py
        +--> crawler/engine.py
        +--> crawler/hybrid.py
        +--> crawler/stealth.py
        +--> social/*.py
        +--> agents/research_agent.py
```

### Crawl strategy

```text
fast    -> HTTP only
hybrid  -> HTTP first, then browser rendering when needed
stealth -> multi-browser / anti-bot fallback path
```

### Current project structure

```text
MCPSearch/
├── agents/                 # Higher-level research orchestration
├── crawler/                # HTTP, hybrid, stealth, extraction logic
├── mcp_server/             # MCP server, unified tools, shared handlers
├── search/                 # Search aggregation
├── social/                 # Reddit, Twitter/X, YouTube, GitHub scrapers
├── summarizer/             # AI summarization helpers
├── tests/                  # Workflow and unit tests
├── utils/                  # Cache, dedup, rate limiting
├── cli.py                  # CLI entry point
├── Makefile                # Dev/test/release commands
└── pyproject.toml          # Package metadata and dependencies
```

## Development

### Useful commands

```bash
make install
make dev
make test
make test-cov
make lint
make lint-fix
make format
make server
python3 scripts/benchmark_search_and_crawl.py
```

### Focused test commands

```bash
make test-hybrid
make test-rate-limiter
pytest tests/test_extractor.py -v
pytest tests/test_search_parsers.py -v
pytest tests/test_mcp_integration.py -v
pytest tests/test_mcp_tools.py -v
```

### Release

```bash
make patch
make minor
make major
```

Version is sourced from [`mcpspider/version.py`](mcpspider/version.py).

## Project Status Notes

- The README now reflects `mcpsearch` / `mcpsearch_multi`, not the older `scout` naming.
- Playwright is part of declared dependencies.
- Camoufox support exists in code, but is optional at install time.
- The main research direction is now orchestration, attribution, and multi-source analysis, not just single-page crawling.

## Practical Next Improvements

See [`docs/USEFUL_LIBS.md`](docs/USEFUL_LIBS.md) for a curated list of libraries and implementation tricks that fit the current architecture.

## Legal and Ethical Usage

Use MCPSearch responsibly.

- Respect target site policies and applicable law.
- Use rate limiting and caching to reduce load.
- Review platform terms before large-scale scraping.
- Avoid collecting or redistributing restricted personal data.

## Contributing

Contribution guidance lives in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
