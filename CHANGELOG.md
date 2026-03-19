# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-20

### Added
- Hybrid crawling with httpx, Playwright, and Camoufox auto-stealth fallback
- Rate limiter with per-domain tracking and adaptive delays
- Multi-source search aggregator (DuckDuckGo, Google, Bing)
- Social media scrapers:
  - Reddit (public JSON API, no key required)
  - Twitter/X (via Nitter, no key required)
  - YouTube (via RSS, no key required)
  - GitHub (public API, no key required)
- Advanced content extraction (tables, code blocks, images, JSON-LD)
- Smart link filtering with heuristic scoring
- Recursive crawling with depth control
- 21 MCP tools for AI assistants
- Unified `scout` tool interface
- Docker support with compose
- CLI interface with multiple commands
- AI summarization support (optional OpenAI)

### Architecture
- Python 3.11+ with async/await throughout
- FastMCP for MCP protocol implementation
- httpx for HTTP client
- Playwright for JS rendering
- Camoufox for stealth browsing
- BeautifulSoup for HTML parsing
