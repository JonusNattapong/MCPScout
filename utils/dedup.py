"""Result deduplication and relevance ranking.

Features:
- URL-based deduplication
- Content similarity detection
- Relevance scoring based on query matching
- Configurable ranking weights
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class RankedResult:
    """A result with relevance score."""
    url: str
    title: str = ""
    content: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ResultDeduplicator:
    """Deduplicate and rank search/crawl results.

    Usage:
        dedup = ResultDeduplicator()
        
        # Add results
        dedup.add_result({"url": "https://example.com", "title": "Example", "content": "..."})
        dedup.add_result({"url": "https://example.com/page", "title": "Page", "content": "..."})
        
        # Get deduplicated results
        unique_results = dedup.get_unique_results()
        
        # Get ranked results by query
        ranked = dedup.rank_by_query("python tutorial")
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        max_results: int = 100,
    ):
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results
        self._results: list[dict[str, Any]] = []
        self._seen_urls: set[str] = set()
        self._content_hashes: set[str] = set()

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        parsed = urlparse(url)
        # Remove fragment, normalize path
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        # Remove common tracking parameters
        return normalized.lower()

    def _hash_content(self, content: str) -> str:
        """Create hash of content for similarity detection."""
        # Normalize content: lowercase, remove extra whitespace
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using Jaccard similarity."""
        if not text1 or not text2:
            return 0.0
        
        # Tokenize
        words1 = set(re.findall(r'\w+', text1.lower()))
        words2 = set(re.findall(r'\w+', text2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def add_result(self, result: dict[str, Any]) -> bool:
        """Add a result. Returns True if added (not duplicate)."""
        url = result.get("url", "")
        content = result.get("content", "")
        
        if not url:
            return False
        
        # Normalize URL
        normalized_url = self._normalize_url(url)
        
        # Check URL duplicate
        if normalized_url in self._seen_urls:
            logger.debug(f"Duplicate URL: {url}")
            return False
        
        # Check content duplicate
        content_hash = self._hash_content(content)
        if content_hash in self._content_hashes:
            logger.debug(f"Duplicate content: {url}")
            return False
        
        # Check content similarity with existing results
        for existing in self._results:
            existing_content = existing.get("content", "")
            similarity = self._calculate_similarity(content, existing_content)
            if similarity >= self.similarity_threshold:
                logger.debug(f"Similar content ({similarity:.2f}): {url}")
                return False
        
        # Add result
        self._seen_urls.add(normalized_url)
        self._content_hashes.add(content_hash)
        self._results.append(result)
        
        return True

    def add_results(self, results: list[dict[str, Any]]) -> int:
        """Add multiple results. Returns number of unique results added."""
        added = 0
        for result in results:
            if self.add_result(result):
                added += 1
        return added

    def get_unique_results(self) -> list[dict[str, Any]]:
        """Get deduplicated results."""
        return self._results[:self.max_results]

    def rank_by_query(
        self,
        query: str,
        results: list[dict[str, Any]] | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[RankedResult]:
        """Rank results by relevance to query.

        Args:
            query: Search query
            results: Results to rank (uses internal results if None)
            weights: Scoring weights for different fields
        """
        if results is None:
            results = self._results
        
        if not weights:
            weights = {
                "title": 3.0,
                "content": 1.0,
                "url": 0.5,
            }
        
        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return [
                RankedResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    content=r.get("content", ""),
                    score=0.0,
                    metadata=r.get("metadata", {}),
                )
                for r in results
            ]
        
        ranked = []
        for result in results:
            score = 0.0
            
            # Score title
            title = result.get("title", "").lower()
            title_words = set(re.findall(r'\w+', title))
            title_matches = len(query_words & title_words)
            score += title_matches * weights.get("title", 3.0)
            
            # Score content
            content = result.get("content", "").lower()
            content_words = set(re.findall(r'\w+', content))
            content_matches = len(query_words & content_words)
            score += content_matches * weights.get("content", 1.0)
            
            # Score URL
            url = result.get("url", "").lower()
            url_words = set(re.findall(r'\w+', url))
            url_matches = len(query_words & url_words)
            score += url_matches * weights.get("url", 0.5)
            
            # Normalize by query length
            score = score / len(query_words) if query_words else 0.0
            
            ranked.append(RankedResult(
                url=result.get("url", ""),
                title=result.get("title", ""),
                content=result.get("content", "")[:500],  # Truncate for display
                score=round(score, 3),
                metadata=result.get("metadata", {}),
            ))
        
        # Sort by score descending
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        return ranked[:self.max_results]

    def rank_by_relevance(
        self,
        results: list[dict[str, Any]] | None = None,
    ) -> list[RankedResult]:
        """Rank results by general relevance (content quality).

        Factors:
        - Content length
        - Title presence
        - URL quality (shorter, cleaner URLs)
        """
        if results is None:
            results = self._results
        
        ranked = []
        for result in results:
            score = 0.0
            
            # Content length score (longer = more content)
            content = result.get("content", "")
            content_length = len(content)
            score += min(content_length / 1000, 5.0)  # Max 5 points
            
            # Title presence
            title = result.get("title", "")
            if title:
                score += 2.0
            
            # URL quality (shorter URLs are often better)
            url = result.get("url", "")
            url_length = len(url)
            if url_length < 100:
                score += 1.0
            elif url_length < 200:
                score += 0.5
            
            # Penalize very short content
            if content_length < 100:
                score *= 0.5
            
            ranked.append(RankedResult(
                url=result.get("url", ""),
                title=title,
                content=content[:500],
                score=round(score, 3),
                metadata=result.get("metadata", {}),
            ))
        
        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked[:self.max_results]

    def get_stats(self) -> dict[str, Any]:
        """Get deduplication statistics."""
        return {
            "total_results": len(self._results),
            "unique_urls": len(self._seen_urls),
            "unique_content": len(self._content_hashes),
            "max_results": self.max_results,
            "similarity_threshold": self.similarity_threshold,
        }

    def clear(self) -> None:
        """Clear all results."""
        self._results.clear()
        self._seen_urls.clear()
        self._content_hashes.clear()


class SearchDeduplicator(ResultDeduplicator):
    """Specialized deduplicator for search results.

    Adds search-specific ranking based on:
    - Search engine source
    - Result position
    - Snippet quality
    """

    def rank_search_results(
        self,
        query: str,
        results: list[dict[str, Any]] | None = None,
        source_weights: dict[str, float] | None = None,
    ) -> list[RankedResult]:
        """Rank search results with source weighting.

        Args:
            query: Search query
            results: Search results to rank
            source_weights: Weights for different search engines
        """
        if results is None:
            results = self._results
        
        if not source_weights:
            source_weights = {
                "google": 1.0,
                "bing": 0.9,
                "duckduckgo": 0.8,
                "brave": 0.85,
            }
        
        query_words = set(re.findall(r'\w+', query.lower()))
        
        ranked = []
        for result in results:
            score = 0.0
            
            # Base relevance score
            title = result.get("title", "").lower()
            title_words = set(re.findall(r'\w+', title))
            title_matches = len(query_words & title_words)
            score += title_matches * 3.0
            
            # Content/snipnet score
            snippet = result.get("snippet", result.get("content", "")).lower()
            snippet_words = set(re.findall(r'\w+', snippet))
            snippet_matches = len(query_words & snippet_words)
            score += snippet_matches * 1.5
            
            # Source weight
            source = result.get("source", "").lower()
            source_weight = source_weights.get(source, 0.7)
            score *= source_weight
            
            # Position bonus (earlier results are better)
            position = result.get("position", 10)
            position_bonus = max(0, 5 - position * 0.5)
            score += position_bonus
            
            # Normalize
            score = score / len(query_words) if query_words else 0.0
            
            ranked.append(RankedResult(
                url=result.get("url", ""),
                title=result.get("title", ""),
                content=snippet[:500],
                score=round(score, 3),
                metadata={
                    "source": source,
                    "position": position,
                    **result.get("metadata", {}),
                },
            ))
        
        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked[:self.max_results]


# Global instances
result_deduplicator = ResultDeduplicator()
search_deduplicator = SearchDeduplicator()
