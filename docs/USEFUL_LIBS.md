# Useful Libraries and Practical Tricks for MCPSearch

This note collects libraries and implementation ideas that fit the current MCPSearch architecture well. The goal is not to add dependencies for the sake of it, but to highlight options that can remove real bottlenecks in `search`, `crawler`, `social`, and MCP delivery.

## Adopted libraries and next bets

### 1. `selectolax`

Best use cases:

- faster HTML parsing in [`search/aggregator.py`](../search/aggregator.py)
- hot extraction paths in [`crawler/extractor.py`](../crawler/extractor.py)
- social scrapers where parsing speed matters more than full DOM fidelity

Current status:

- adopted on hot search parsing paths in [`search/aggregator.py`](../search/aggregator.py)
- BeautifulSoup fallback remains in place for compatibility

Why it helps:

- MCPSearch currently leans on BeautifulSoup and `lxml`
- `selectolax` gives very fast CSS-selector-based parsing and can reduce parse overhead on large result pages

Validation:

- benchmark with [`scripts/benchmark_search_and_crawl.py`](../scripts/benchmark_search_and_crawl.py)
- parser fallback tests live in [`tests/test_search_parsers.py`](../tests/test_search_parsers.py)

Source:

- GitHub: https://github.com/rushter/selectolax

## 2. `trafilatura`

Best use cases:

- article-heavy pages where your own extraction is noisy
- summary-oriented workflows in `search_and_summarize` and `investigate`
- fallback extraction after regular HTML parsing

Why it helps:

- MCPSearch already extracts content, but article cleanup is a hard problem
- `trafilatura` is strong at turning messy pages into cleaner text and markdown-like content

Good adoption pattern:

- treat it as a fallback path, not a replacement for everything
- use it when extracted text density is poor or boilerplate ratio is high

Source:

- Docs: https://trafilatura.readthedocs.io/en/latest/

## 3. `extruct`

Best use cases:

- extracting JSON-LD, Microdata, RDFa, Open Graph metadata
- improving product, article, recipe, event, and organization extraction
- enriching `extract_content` and research citations

Current status:

- adopted in [`crawler/extractor.py`](../crawler/extractor.py) for JSON-LD, Microdata, RDFa, Open Graph, and Dublin Core extraction
- manual JSON-LD fallback remains in place when extraction fails

Why it helps:

- pages often expose higher-quality structured data than visible body text
- this is especially useful for search result ranking, metadata attribution, and better summaries

Validation:

- extraction tests live in [`tests/test_extractor.py`](../tests/test_extractor.py)

Source:

- PyPI: https://pypi.org/project/extruct/

## 4. `hishel`

Best use cases:

- repeated HTTPX requests to the same domains
- GitHub/YouTube/documentation lookups
- crawl retries and repeated research runs

Current status:

- partially integrated now through [`utils/http_client.py`](../utils/http_client.py)
- wired into [`search/aggregator.py`](../search/aggregator.py)
- wired into [`social/github.py`](../social/github.py)

Why it helps:

- MCPSearch already uses `httpx` heavily
- `hishel` gives HTTP caching for HTTPX and can be used as a drop-in client or transport
- practical value is lower latency, lower bandwidth, and less load on target sites

Good adoption pattern:

- start with search aggregation and read-heavy endpoints
- use TTL-based caching for sources that change slowly
- keep cache bypass available for fresh investigative runs

Source:

- Docs: https://hishel.com/1.0/integrations/httpx/

## 5. `aiometer`

Best use cases:

- unified concurrency limits across search, crawl, and social tasks
- per-second throttling on top of semaphores
- cleaner orchestration inside `research_agent`

Why it helps:

- MCPSearch already does concurrent work with `asyncio.gather()`
- `aiometer` can make concurrency and request-rate control more explicit

Good adoption pattern:

- use it first in multi-source fan-out flows
- keep existing semaphore-based logic where it is already simple and stable

Source:

- GitHub: https://github.com/florimondmanca/aiometer

## Practical tricks worth using now

### Playwright request blocking

For crawl paths where screenshots and full visual fidelity are not needed, block non-essential resources:

- images
- fonts
- media
- analytics scripts

This usually improves crawl speed and reduces bandwidth dramatically on JS-heavy pages.

Best fit:

- [`crawler/hybrid.py`](../crawler/hybrid.py)
- stealth fallback when content extraction is the only goal

Current status:

- adopted in [`crawler/hybrid.py`](../crawler/hybrid.py)
- request blocking tests live in [`tests/test_hybrid.py`](../tests/test_hybrid.py)
- live benchmark support exists in [`scripts/benchmark_search_and_crawl.py`](../scripts/benchmark_search_and_crawl.py)

Source:

- Playwright network docs: https://playwright.dev/python/docs/network

### Tighten HTTPX client limits explicitly

MCPSearch uses async HTTP heavily. Explicitly setting connection limits can prevent accidental overload and make concurrency more predictable.

Best fit:

- [`search/aggregator.py`](../search/aggregator.py)
- crawler clients shared across tasks

Source:

- HTTPX resource limits: https://www.python-httpx.org/advanced/resource-limits/

### Add HTTP caching before adding more sources

Before adding more providers, make repeated runs cheaper and more respectful:

- cache search engine result pages where feasible
- cache GitHub README fetches
- cache documentation pages used in repeated research jobs

This is one of the highest-leverage changes for MCPSearch right now.

### Treat structured metadata as a first-class signal

Do not rely only on visible body text for ranking and summarization. Prefer these signals when available:

- JSON-LD `headline`, `description`, `datePublished`
- Open Graph title and description
- canonical URL
- author / organization metadata

This will noticeably improve `investigate` output quality.

### Consider remote MCP delivery as a future transport

Today the repo is centered on stdio MCP. If you later want hosted or team-shared deployments, Streamable HTTP is the main transport direction to watch in the MCP ecosystem.

Best fit:

- future deployment layer, not an immediate code dependency

Source:

- MCP transport roadmap blog: https://blog.modelcontextprotocol.io/posts/2025-12-19-mcp-transport-future/

## Suggested adoption order

1. Add HTTP caching with `hishel`
2. Add `selectolax` to the hottest parsing paths
3. Add `extruct` to structured extraction
4. Add resource blocking to Playwright crawl paths
5. Evaluate `trafilatura` as extraction fallback
6. Refactor heavy fan-out flows with `aiometer`

## What to avoid right now

- adding many new search providers before caching and normalization improve
- replacing every parser at once
- introducing a vector database before citation, ranking, and extraction quality are stable
- adding remote MCP transport before current stdio workflows are fully documented and tested
