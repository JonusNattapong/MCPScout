"""Smart crawler with heuristic-based link relevance filtering.

Uses rule-based scoring to evaluate which links are relevant to the search query
before crawling, making deep searches more efficient. 100% free, no API needed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from mcpspider.crawler.engine import CrawlerEngine, CrawlResult

logger = logging.getLogger(__name__)


@dataclass
class LinkScore:
    """A link with its relevance score."""

    url: str
    title: str = ""
    anchor_text: str = ""
    relevance_score: float = 0.0  # 0.0 to 1.0
    reason: str = ""


@dataclass
class SmartCrawlResult:
    """Result from smart guided crawling."""

    query: str
    pages_crawled: int = 0
    pages_skipped: int = 0
    links_evaluated: int = 0
    links_approved: int = 0
    results: list[CrawlResult] = field(default_factory=list)
    top_links: list[LinkScore] = field(default_factory=list)


class LinkRelevanceScorer:
    """Rule-based link relevance scoring (free, no API needed)."""

    RELEVANCE_SIGNALS = {
        "high": ["wiki", "documentation", "tutorial", "guide", "learn", "how-to", "example", "reference"],
        "medium": ["blog", "article", "post", "news", "research", "paper", "docs"],
        "low": ["login", "signup", "cart", "checkout", "ad", "promo", "subscribe", "donate", "buy"],
    }

    def score_links(
        self,
        query: str,
        links: list[dict[str, str]],
        max_select: int = 10,
    ) -> list[LinkScore]:
        """Score links by relevance using heuristics."""
        query_words = set(query.lower().split())
        scored: list[LinkScore] = []

        for link in links:
            url = link.get("url", "")
            title = link.get("title", "")
            anchor = link.get("anchor", "")

            score = self._calculate_relevance(query_words, url, title, anchor)

            scored.append(LinkScore(
                url=url,
                title=title,
                anchor_text=anchor,
                relevance_score=score["score"],
                reason=score["reason"],
            ))

        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored[:max_select]

    def _calculate_relevance(
        self,
        query_words: set[str],
        url: str,
        title: str,
        anchor: str,
    ) -> dict[str, Any]:
        """Calculate relevance score for a link."""
        score = 0.0
        reasons = []

        url_lower = url.lower()
        url_path = urlparse(url).path.lower()

        # Query words in URL path
        for word in query_words:
            if word in url_path:
                score += 0.3
                reasons.append(f"query '{word}' in URL")

        # High-relevance signals
        for signal in self.RELEVANCE_SIGNALS["high"]:
            if signal in url_lower:
                score += 0.2
                reasons.append(f"high-signal: {signal}")
                break

        # Low-relevance signals (negative)
        for signal in self.RELEVANCE_SIGNALS["low"]:
            if signal in url_lower:
                score -= 0.3
                reasons.append(f"low-signal: {signal}")
                break

        # Check title/anchor text
        text = f"{title} {anchor}".lower()
        for word in query_words:
            if word in text:
                score += 0.25
                reasons.append(f"query '{word}' in title/anchor")

        # Bonus for exact phrase match
        query_phrase = " ".join(query_words)
        if query_phrase in text:
            score += 0.3
            reasons.append("exact phrase match")

        score = max(0.0, min(1.0, score))

        return {
            "score": score,
            "reason": "; ".join(reasons) if reasons else "no signals",
        }


class SmartCrawler(CrawlerEngine):
    """Smart crawler that filters links by relevance before following them."""

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout: float = 30.0,
        user_agent: str = "MCPScout/1.0.0",
        relevance_threshold: float = 0.4,
    ):
        super().__init__(max_concurrent, timeout, user_agent)
        self.scorer = LinkRelevanceScorer()
        self.relevance_threshold = relevance_threshold

    async def smart_crawl(
        self,
        query: str,
        urls: list[str],
        max_depth: int = 2,
        max_pages: int = 20,
    ) -> SmartCrawlResult:
        """Smart crawl: filter links by relevance before following them."""
        visited: set[str] = set()
        results: list[CrawlResult] = []
        top_links: list[LinkScore] = []
        queue: list[tuple[str, int]] = [(url, 0) for url in urls]
        links_evaluated = 0
        links_approved = 0
        links_skipped = 0

        for depth in range(max_depth + 1):
            if len(results) >= max_pages:
                break

            current_batch = [(u, d) for u, d in queue if d == depth]
            if not current_batch:
                continue

            queue = [(u, d) for u, d in queue if d != depth]

            semaphore = self._get_semaphore()

            async def _crawl_and_filter(url: str, d: int) -> CrawlResult | None:
                nonlocal links_evaluated, links_approved, links_skipped

                async with semaphore:
                    normalized = self._normalize_url(url)
                    if normalized in visited:
                        return None
                    visited.add(normalized)

                    result = await self._crawl_url(url, "markdown", d, max_depth)
                    if result.error:
                        return result

                    # Score links
                    link_dicts = [
                        {"url": link, "title": "", "anchor": ""}
                        for link in result.links[:30]
                    ]
                    scored = self.scorer.score_links(query, link_dicts, max_select=10)

                    # Add relevant links to queue
                    for link_score in scored:
                        links_evaluated += 1
                        if link_score.relevance_score >= self.relevance_threshold:
                            links_approved += 1
                            link_normalized = self._normalize_url(link_score.url)
                            if link_normalized not in visited:
                                queue.append((link_score.url, depth + 1))
                                top_links.append(link_score)
                        else:
                            links_skipped += 1

                    return result

            tasks = [_crawl_and_filter(u, d) for u, d in current_batch[:self.max_concurrent]]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    continue
                if result:
                    results.append(result)

        return SmartCrawlResult(
            query=query,
            pages_crawled=len([r for r in results if r.error is None]),
            pages_skipped=links_skipped,
            links_evaluated=links_evaluated,
            links_approved=links_approved,
            results=results,
            top_links=sorted(top_links, key=lambda x: x.relevance_score, reverse=True)[:20],
        )
