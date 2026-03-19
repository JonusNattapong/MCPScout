"""Async web crawler engine for parallel and recursive web crawling."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from mcpspider.utils.rate_limiter import AdaptiveRateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)

ExtractMode = Literal["text", "markdown", "structured"]


@dataclass
class CrawlResult:
    """Result from crawling a URL."""

    url: str
    depth: int = 0
    title: str = ""
    content: str = ""
    markdown: str = ""
    structured: dict[str, Any] = field(default_factory=dict)
    links: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class RecursiveCrawlResult:
    """Results from recursive crawling."""

    seed_url: str
    pages_crawled: int = 0
    pages_failed: int = 0
    total_links_found: int = 0
    results: list[CrawlResult] = field(default_factory=list)
    visited_urls: set[str] = field(default_factory=set)


class CrawlerEngine:
    """Async web crawler engine with parallel and recursive crawling support."""

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: float = 30.0,
        user_agent: str = "MCPScout/1.0.0",
        rate_limit: RateLimitConfig | None = None,
    ):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.user_agent = user_agent
        self.rate_limiter = AdaptiveRateLimiter(rate_limit)
        self._semaphore: asyncio.Semaphore | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    # =========================================================================
    # SINGLE URL CRAWL
    # =========================================================================

    async def crawl(
        self,
        url: str,
        extract_mode: ExtractMode = "markdown",
        max_depth: int = 1,
    ) -> str:
        """Crawl a single URL and return extracted content."""
        result = await self._crawl_url(url, extract_mode, depth=0, max_depth=max_depth)
        return self._format_result(result, extract_mode)

    async def crawl_multiple(
        self,
        urls: list[str],
        extract_mode: ExtractMode = "markdown",
        max_depth: int = 1,
    ) -> list[dict[str, Any]]:
        """Crawl multiple URLs in parallel."""
        semaphore = self._get_semaphore()

        async def _crawl_with_semaphore(url: str) -> CrawlResult:
            async with semaphore:
                return await self._crawl_url(url, extract_mode, depth=0, max_depth=max_depth)

        tasks = [_crawl_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        formatted = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                formatted.append({
                    "url": url,
                    "title": "Error",
                    "content": str(result),
                    "error": str(result),
                })
            else:
                formatted.append({
                    "url": result.url,
                    "depth": result.depth,
                    "title": result.title,
                    "content": result.content,
                    "markdown": result.markdown,
                    "links": result.links,
                    "metadata": result.metadata,
                })

        return formatted

    # =========================================================================
    # RECURSIVE CRAWL - Follow links deep into a website
    # =========================================================================

    async def crawl_recursive(
        self,
        url: str,
        max_depth: int = 3,
        max_pages: int = 50,
        same_domain_only: bool = True,
        extract_mode: ExtractMode = "markdown",
    ) -> RecursiveCrawlResult:
        """Recursively crawl a website following links up to max_depth.

        Args:
            url: Starting URL (seed)
            max_depth: Maximum crawl depth (follows links up to this depth)
            max_pages: Maximum number of pages to crawl
            same_domain_only: If True, only crawl pages on the same domain
            extract_mode: Content extraction mode

        Returns:
            RecursiveCrawlResult with all crawled pages
        """
        visited: set[str] = set()
        results: list[CrawlResult] = []
        queue: deque[tuple[str, int]] = deque([(url, 0)])  # (url, depth)
        semaphore = self._get_semaphore()
        seed_domain = urlparse(url).netloc
        total_links_found = 0

        async def _crawl_page(page_url: str, depth: int) -> CrawlResult | None:
            async with semaphore:
                result = await self._crawl_url(page_url, extract_mode, depth, max_depth)
                return result

        while queue and len(results) < max_pages:
            # Get batch of URLs to crawl at current depth level
            current_batch: list[tuple[str, int]] = []
            while queue and len(current_batch) < self.max_concurrent:
                page_url, depth = queue.popleft()
                normalized = self._normalize_url(page_url)
                if normalized not in visited and len(results) < max_pages:
                    visited.add(normalized)
                    current_batch.append((page_url, depth))

            if not current_batch:
                continue

            # Crawl batch in parallel
            tasks = [_crawl_page(u, d) for u, d in current_batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for (page_url, depth), result in zip(current_batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error crawling {page_url}: {result}")
                    results.append(CrawlResult(url=page_url, depth=depth, error=str(result)))
                    continue

                if result is None:
                    continue

                results.append(result)

                # Add discovered links to queue if within depth limit
                if depth < max_depth:
                    for link in result.links:
                        normalized_link = self._normalize_url(link)
                        if normalized_link in visited:
                            continue

                        # Check domain filter
                        if same_domain_only:
                            link_domain = urlparse(link).netloc
                            if link_domain != seed_domain:
                                continue

                        queue.append((link, depth + 1))
                        total_links_found += 1

        return RecursiveCrawlResult(
            seed_url=url,
            pages_crawled=len([r for r in results if r.error is None]),
            pages_failed=len([r for r in results if r.error is not None]),
            total_links_found=total_links_found,
            results=results,
            visited_urls=visited,
        )

    async def deep_search(
        self,
        query: str,
        search_engine: Any,  # SearchAggregator instance
        max_depth: int = 2,
        max_pages: int = 20,
        same_domain_only: bool = False,
    ) -> RecursiveCrawlResult:
        """Search and then deep crawl the top results.

        This is the "deep search" feature - search for something,
        then recursively crawl the top results to gather comprehensive info.

        Args:
            query: Search query
            search_engine: SearchAggregator instance
            max_depth: How deep to crawl from each result
            max_pages: Maximum pages to crawl total
            same_domain_only: Whether to stay on same domain after initial page
        """
        # Step 1: Search
        search_results = await search_engine.search(query, max_results=5)

        if not search_results:
            return RecursiveCrawlResult(seed_url=query)

        # Step 2: Recursively crawl each top result
        all_results: list[CrawlResult] = []
        visited: set[str] = set()
        pages_per_result = max_pages // len(search_results)

        for sr in search_results[:3]:  # Top 3 results
            url = sr.get("url", "")
            if not url or url in visited:
                continue

            visited.add(url)
            result = await self.crawl_recursive(
                url=url,
                max_depth=max_depth,
                max_pages=pages_per_result,
                same_domain_only=same_domain_only,
            )
            all_results.extend(result.results)
            visited.update(result.visited_urls)

        return RecursiveCrawlResult(
            seed_url=query,
            pages_crawled=len([r for r in all_results if r.error is None]),
            pages_failed=len([r for r in all_results if r.error is not None]),
            total_links_found=sum(len(r.links) for r in all_results),
            results=all_results,
            visited_urls=visited,
        )

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    async def _crawl_url(
        self,
        url: str,
        extract_mode: ExtractMode,
        depth: int,
        max_depth: int,
    ) -> CrawlResult:
        """Crawl a single URL and return structured result."""
        # Apply rate limiting before request
        await self.rate_limiter.wait(url)

        start_time = time.time()

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Record successful response
                response_time = time.time() - start_time
                self.rate_limiter.record_response(
                    url,
                    response.status_code,
                    response_time,
                    dict(response.headers),
                )

                soup = BeautifulSoup(response.text, "lxml")
                result = CrawlResult(url=url, depth=depth)

                # Extract title
                title_tag = soup.find("title")
                result.title = title_tag.get_text(strip=True) if title_tag else ""

                # Extract content based on mode
                content = self._extract_content(soup, extract_mode)
                result.content = content["text"]
                result.markdown = content["markdown"]
                result.structured = content["structured"]

                # Extract links for further crawling
                result.links = self._extract_links(soup, url)

                # Extract metadata
                result.metadata = self._extract_metadata(soup)

                return result

        except httpx.HTTPStatusError as e:
            # Record blocked/error response
            response_time = time.time() - start_time
            self.rate_limiter.record_response(
                url,
                e.response.status_code,
                response_time,
                dict(e.response.headers) if e.response else None,
            )
            logger.error(f"HTTP error {e.response.status_code} for {url}")
            return CrawlResult(url=url, depth=depth, error=str(e))

        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return CrawlResult(url=url, depth=depth, error=str(e))

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        # Remove fragment, normalize path
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    def _extract_content(self, soup: BeautifulSoup, mode: ExtractMode) -> dict[str, Any]:
        """Extract content from soup based on mode."""
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Find main content area
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if not main:
            main = soup

        text = main.get_text(separator="\n", strip=True)
        markdown = self._text_to_markdown(main)
        structured = self._extract_structured(main)

        return {
            "text": text,
            "markdown": markdown,
            "structured": structured,
        }

    def _text_to_markdown(self, element: Tag) -> str:
        """Convert HTML element to simple markdown."""
        lines: list[str] = []

        for child in element.descendants:
            if not isinstance(child, Tag):
                continue

            name = child.name
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(name[1])
                prefix = "#" * level
                lines.append(f"\n{prefix} {child.get_text(strip=True)}\n")
            elif name == "p":
                lines.append(f"\n{child.get_text(strip=True)}\n")
            elif name == "li":
                lines.append(f"- {child.get_text(strip=True)}")
            elif name == "a":
                href = child.get("href", "")
                text = child.get_text(strip=True)
                if href and text:
                    lines.append(f"[{text}]({href})")

        return "\n".join(lines)

    def _extract_structured(self, element: Tag) -> dict[str, Any]:
        """Extract structured data from HTML."""
        structured: dict[str, Any] = {
            "headings": [],
            "paragraphs": [],
            "links": [],
            "images": [],
        }

        for h in element.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            structured["headings"].append({
                "level": int(h.name[1]),
                "text": h.get_text(strip=True),
            })

        for p in element.find_all("p"):
            text = p.get_text(strip=True)
            if text:
                structured["paragraphs"].append(text)

        for a in element.find_all("a", href=True):
            structured["links"].append({
                "text": a.get_text(strip=True),
                "href": a["href"],
            })

        for img in element.find_all("img", src=True):
            structured["images"].append({
                "src": img["src"],
                "alt": img.get("alt", ""),
            })

        return structured

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract all links from page."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Convert relative URLs to absolute
            absolute = urljoin(base_url, href)
            # Only include http(s) links
            if absolute.startswith(("http://", "https://")):
                links.append(absolute)
        return list(set(links))

    def _extract_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract metadata from page."""
        metadata: dict[str, Any] = {}

        # Meta description
        desc = soup.find("meta", attrs={"name": "description"})
        if desc:
            metadata["description"] = desc.get("content", "")

        # Meta keywords
        keywords = soup.find("meta", attrs={"name": "keywords"})
        if keywords:
            metadata["keywords"] = keywords.get("content", "")

        # Open Graph
        og_title = soup.find("meta", property="og:title")
        if og_title:
            metadata["og_title"] = og_title.get("content", "")

        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            metadata["og_description"] = og_desc.get("content", "")

        return metadata

    def _format_result(self, result: CrawlResult, mode: ExtractMode) -> str:
        """Format crawl result for output."""
        if result.error:
            return f"Error crawling {result.url}: {result.error}"

        if mode == "text":
            return result.content
        elif mode == "structured":
            import json
            return json.dumps(result.structured, indent=2, ensure_ascii=False)
        else:  # markdown
            return f"# {result.title}\n\n**URL:** {result.url}\n\n{result.markdown}"
