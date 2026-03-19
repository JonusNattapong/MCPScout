# MCPScout

AI-powered multi-source intelligence platform with MCP (Model Context Protocol) interface.

**Hybrid crawling** + **Stealth browser** + **Social media scraping** + **Anti-bot bypass** - all free, no API keys required.

## Features

- **Hybrid Crawling** - httpx (fast) → Playwright (JS) → Camoufox (stealth) auto-fallback
- **Stealth Browser** - Bypass Cloudflare, Akamai, DataDome (100% free, self-hosted)
- **Parallel Search** - DuckDuckGo, Google, Bing simultaneously
- **Social Media** - Reddit, Twitter/X, YouTube, GitHub (no API keys)
- **Advanced Extraction** - Tables, code blocks, images, JSON-LD
- **Smart Link Filtering** - Heuristic scoring to skip irrelevant links
- **Recursive Crawling** - Deep crawl with depth control
- **Rate Limiting** - Per-domain tracking with adaptive delays
- **MCP Interface** - 22 tools for AI assistants

## MCP Tools

### Unified Tool

```python
# Single tool for everything
scout(action="search", query="AI news")
scout(action="crawl", url="https://example.com", mode="stealth")
scout(action="reddit", query="python", subreddit="learnpython")
scout(action="twitter", query="AI news")
scout(action="youtube", query="python tutorial")
scout(action="github", query="machine learning", sort="stars")
scout(action="github", platform="repo", target="pytorch/pytorch")
```

### All Tools

| Category | Tools |
|----------|-------|
| **Web Search** | `web_search`, `search_and_summarize`, `smart_search`, `deep_search` |
| **Web Crawl** | `hybrid_crawl`, `crawl_url`, `extract_content`, `crawl_recursive` |
| **Reddit** | `search_reddit`, `get_subreddit`, `get_reddit_post` |
| **Twitter/X** | `search_twitter`, `get_user_tweets` |
| **YouTube** | `search_youtube`, `get_youtube_channel`, `get_youtube_content` |
| **GitHub** | `search_github`, `get_github_user`, `get_github_repo`, `get_github_readme` |
| **Unified** | `scout`, `scout_multi` |

## Quick Start

### Install

```bash
# Clone repo
git clone https://github.com/JonusNattapong/MCPScout.git
cd MCPScout

# Install
pip install -e .
playwright install chromium

# Or with dev dependencies
make dev
```

### Run MCP Server

```bash
# Method 1: Module
python -m mcp_server

# Method 2: Makefile
make server
```

### CLI

```bash
mcpscout search -q "AI news"
mcpscout crawl -u "https://example.com"
mcpscout read -u "https://example.com"
```

## MCP Integration

Add to your MCP client config (Claude Desktop, etc.):

```json
{
  "mcpServers": {
    "mcpscout": {
      "command": "python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```

## Architecture

```
URL Input → httpx (fast, ~50ms)
               │
          Blocked? → Playwright (JS rendering)
                        │
                   Blocked? → Camoufox (stealth, auto!)
```

### Rate Limiting

Automatic per-domain rate limiting:
- Adaptive delays between requests
- Block detection and cooldown
- Request tracking per domain

```bash
# Check crawl stats
mcpscout stats  # or use get_crawl_stats tool
```

## Usage Examples

### Web Search + Summarize

```python
# Perplexity-style search and summarize
search_and_summarize(query="Latest AI developments", max_sources=5)
```

### Smart Crawl with Link Filtering

```python
# Only crawl relevant links
smart_search(query="Python async tutorial", max_depth=2, max_pages=15)
```

### Social Media Research

```python
# Cross-platform research
scout_multi(actions=[
    {"action": "search", "query": "LLM agents"},
    {"action": "reddit", "query": "LocalLLaMA"},
    {"action": "github", "query": "langchain", "sort": "stars"},
])
```

## Development

```bash
# Install dev dependencies
make dev

# Run tests
make test
make test-cov

# Lint & format
make lint
make format

# Docker
make docker-build
make docker-run
```

## Version Management

```bash
# Auto-release with changelog
make patch   # 1.0.0 -> 1.0.1
make minor   # 1.0.0 -> 1.1.0
make major   # 1.0.0 -> 2.0.0
```

## Project Structure

```
MCPScout/
├── mcp_server/           # FastMCP server (22 tools)
├── crawler/              # Hybrid + stealth crawling
├── search/               # Multi-engine search
├── social/               # Reddit, Twitter, YouTube, GitHub
├── utils/                # Rate limiter
├── mcpspider/            # Version management
├── scripts/              # Release automation
├── cli.py                # CLI interface
├── Makefile              # Common commands
└── pyproject.toml        # Package config
```

## License

MIT - See [LICENSE](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
