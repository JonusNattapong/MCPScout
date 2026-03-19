"""Search aggregator that queries multiple search engines in parallel."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result."""

    title: str
    url: str
    snippet: str = ""
    source: str = ""  # Which search engine returned this
    rank: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class SearchEngine:
    """Base class for search engines."""

    name: str = "base"
    base_url: str = ""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        raise NotImplementedError


class DuckDuckGoEngine(SearchEngine):
    """DuckDuckGo search engine."""

    name = "duckduckgo"
    base_url = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        try:
            response = await self.client.post(
                self.base_url,
                data={"q": query, "b": ""},
                timeout=15.0,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            results = []

            for i, result in enumerate(soup.select(".result__body"), 1):
                if i > max_results:
                    break

                title_tag = result.select_one(".result__title a")
                snippet_tag = result.select_one(".result__snippet")

                if title_tag:
                    results.append(SearchResult(
                        title=title_tag.get_text(strip=True),
                        url=self._clean_url(title_tag.get("href", "")),
                        snippet=snippet_tag.get_text(strip=True) if snippet_tag else "",
                        source=self.name,
                        rank=i,
                    ))

            return results

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    def _clean_url(self, url: str) -> str:
        """Extract actual URL from DuckDuckGo redirect."""
        # DuckDuckGo uses redirect URLs
        match = re.search(r"uddg=([^&]+)", url)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))
        return url


class GoogleEngine(SearchEngine):
    """Google search engine (using lite endpoint)."""

    name = "google"
    base_url = "https://www.google.com/search"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        try:
            response = await self.client.get(
                self.base_url,
                params={"q": query, "num": max_results, "hl": "en"},
                timeout=15.0,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            results = []

            for i, div in enumerate(soup.select("div.g"), 1):
                if i > max_results:
                    break

                link = div.select_one("a")
                title = div.select_one("h3")
                snippet = div.select_one("div.VwiC3b")

                if link and title:
                    results.append(SearchResult(
                        title=title.get_text(strip=True),
                        url=link.get("href", ""),
                        snippet=snippet.get_text(strip=True) if snippet else "",
                        source=self.name,
                        rank=i,
                    ))

            return results

        except Exception as e:
            logger.error(f"Google search error: {e}")
            return []


class BingEngine(SearchEngine):
    """Bing search engine."""

    name = "bing"
    base_url = "https://www.bing.com/search"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        try:
            response = await self.client.get(
                self.base_url,
                params={"q": query, "count": max_results},
                timeout=15.0,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            results = []

            for i, li in enumerate(soup.select("li.b_algo"), 1):
                if i > max_results:
                    break

                link = li.select_one("h2 a")
                snippet = li.select_one("div.b_caption p")

                if link:
                    results.append(SearchResult(
                        title=link.get_text(strip=True),
                        url=link.get("href", ""),
                        snippet=snippet.get_text(strip=True) if snippet else "",
                        source=self.name,
                        rank=i,
                    ))

            return results

        except Exception as e:
            logger.error(f"Bing search error: {e}")
            return []


class SearchAggregator:
    """Aggregates search results from multiple engines."""

    def __init__(
        self,
        engines: list[str] | None = None,
        max_concurrent: int = 5,
    ):
        self.engine_names = engines or ["duckduckgo", "google", "bing"]
        self.max_concurrent = max_concurrent
        self._client: httpx.AsyncClient | None = None

    def _get_engines(self) -> list[SearchEngine]:
        """Initialize search engines."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                follow_redirects=True,
            )

        engine_classes = {
            "duckduckgo": DuckDuckGoEngine,
            "google": GoogleEngine,
            "bing": BingEngine,
        }

        engines = []
        for name in self.engine_names:
            if name in engine_classes:
                engines.append(engine_classes[name](self._client))

        return engines

    async def search(
        self,
        query: str,
        max_results: int = 10,
        sources: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search across multiple engines in parallel."""
        engines = self._get_engines()

        if sources:
            engines = [e for e in engines if e.name in sources]

        # Search in parallel
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _search_with_semaphore(engine: SearchEngine) -> list[SearchResult]:
            async with semaphore:
                return await engine.search(query, max_results)

        tasks = [_search_with_semaphore(engine) for engine in engines]
        results_by_engine = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge and deduplicate results
        all_results: dict[str, SearchResult] = {}
        for engine_results in results_by_engine:
            if isinstance(engine_results, Exception):
                logger.error(f"Search error: {engine_results}")
                continue
            for result in engine_results:
                # Deduplicate by URL
                if result.url not in all_results:
                    all_results[result.url] = result

        # Sort by relevance (combine ranks from different engines)
        merged = sorted(all_results.values(), key=lambda r: r.rank)[:max_results]

        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source,
                "rank": r.rank,
            }
            for r in merged
        ]

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
