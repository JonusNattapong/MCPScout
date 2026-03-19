# MCPScout

AI-powered multi-source intelligence platform with MCP (Model Context Protocol) interface.

**Hybrid crawling** + **Stealth browser** + **Social media scraping** + **Anti-bot bypass** - all free, no API keys required.

## Features

- **Hybrid Crawling** - httpx (fast) → Playwright (JS) → Camoufox (stealth) auto-fallback
- **Stealth Browser** - Bypass Cloudflare, Akamai, DataDome (100% free, self-hosted)
- **Parallel Search** - DuckDuckGo, Google, Bing
- **Social Media** - Reddit, Twitter/X, YouTube, GitHub (no API keys)
- **Advanced Extraction** - Tables, code blocks, images, JSON-LD
- **Smart Link Filtering** - Heuristic scoring to skip irrelevant links
- **Recursive Crawling** - Deep crawl with depth control
- **MCP Interface** - 21 tools for AI assistants

## MCP Tools (21 Tools)

| Category | Tools |
|----------|-------|
| **Web Search** | `web_search`, `search_and_summarize`, `smart_search`, `deep_search` |
| **Web Crawl** | `hybrid_crawl`, `crawl_url`, `extract_content`, `crawl_recursive` |
| **Reddit** | `search_reddit`, `get_subreddit`, `get_reddit_post` |
| **Twitter/X** | `search_twitter`, `get_user_tweets` |
| **YouTube** | `search_youtube`, `get_youtube_channel`, `get_youtube_content` |
| **GitHub** | `search_github`, `get_github_user`, `get_github_repo`, `get_github_readme` |

## Quick Start

```bash
# Install
pip install -e .
playwright install chromium

# Run MCP server
python -m mcpspider server

# CLI
mcpspider search -q "AI news"
mcpspider crawl -u "https://example.com"
mcpspider read -u "https://example.com"
```

## MCP Integration

```json
{
  "mcpServers": {
    "mcpscout": {
      "command": "python",
      "args": ["-m", "mcpspider", "server"]
    }
  }
}
```

## Hybrid Crawling Strategy

```
URL Input → httpx (fast, ~50ms)
               │
          Blocked? → Playwright (JS rendering)
                        │
                   Blocked? → Camoufox (stealth, auto!)
```

## Docker

```bash
docker build -t mcpscout .
docker run -it mcpscout server
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## License

MIT
