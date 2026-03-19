"""Rate limiter and anti-block protection for web crawling.

Features:
- Per-domain rate limiting
- Request delay control
- Retry with exponential backoff
- Domain blacklisting
- Request quota tracking
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class DomainStats:
    """Statistics for a domain."""
    requests_made: int = 0
    last_request_time: float = 0.0
    total_wait_time: float = 0.0
    blocked_count: int = 0


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    min_delay: float = 1.0  # Minimum delay between requests (seconds)
    max_delay: float = 3.0  # Maximum delay (with jitter)
    requests_per_minute: int = 30  # Max requests per minute per domain
    max_retries: int = 3  # Max retry attempts
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    block_cooldown: float = 60.0  # Cooldown after being blocked (seconds)


class RateLimiter:
    """Rate limiter with per-domain tracking and anti-block protection.

    Usage:
        limiter = RateLimiter()
        
        # Before each request
        await limiter.wait("example.com")
        
        # If blocked
        limiter.report_blocked("example.com")
        
        # Check if domain is blocked
        if limiter.is_blocked("example.com"):
            print("Domain is in cooldown")
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._domain_stats: dict[str, DomainStats] = defaultdict(DomainStats)
        self._domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_lock = asyncio.Lock()
        self._blacklist: dict[str, float] = {}  # domain -> unblock_time

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()

    async def wait(self, url: str) -> None:
        """Wait appropriate time before making request to URL."""
        domain = self._get_domain(url)

        async with self._domain_locks[domain]:
            # Check blacklist
            if self.is_blocked(domain):
                remaining = self._blacklist[domain] - time.time()
                if remaining > 0:
                    logger.warning(f"Domain {domain} is blocked. Waiting {remaining:.1f}s")
                    await asyncio.sleep(remaining)
                    del self._blacklist[domain]

            stats = self._domain_stats[domain]
            now = time.time()

            # Calculate delay since last request
            if stats.last_request_time > 0:
                elapsed = now - stats.last_request_time
                min_delay = self._get_delay_with_jitter()

                if elapsed < min_delay:
                    wait_time = min_delay - elapsed
                    logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {domain}")
                    await asyncio.sleep(wait_time)

            # Check requests per minute
            if stats.requests_made >= self.config.requests_per_minute:
                wait_time = 60.0 - (time.time() - stats.last_request_time)
                if wait_time > 0:
                    logger.warning(f"Rate limit: {domain} hit {self.config.requests_per_minute}/min limit, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    stats.requests_made = 0

            # Update stats
            stats.last_request_time = time.time()
            stats.requests_made += 1

    def _get_delay_with_jitter(self) -> float:
        """Get delay with random jitter to appear more human-like."""
        base_delay = self.config.min_delay
        jitter = random.uniform(0, self.config.max_delay - self.config.min_delay)
        return base_delay + jitter

    def report_blocked(self, url: str) -> None:
        """Report that a request was blocked (403, 429, challenge, etc.)."""
        domain = self._get_domain(url)
        stats = self._domain_stats[domain]
        stats.blocked_count += 1

        # Apply cooldown with exponential backoff
        cooldown = self.config.block_cooldown * (2 ** (stats.blocked_count - 1))
        self._blacklist[domain] = time.time() + cooldown

        logger.warning(
            f"Domain {domain} blocked! Cooldown: {cooldown}s "
            f"(block #{stats.blocked_count})"
        )

    def report_success(self, url: str) -> None:
        """Report successful request (resets block counter after success)."""
        domain = self._get_domain(url)
        stats = self._domain_stats[domain]

        # Gradually reduce blocked count on success
        if stats.blocked_count > 0:
            stats.blocked_count = max(0, stats.blocked_count - 1)

    def is_blocked(self, domain: str) -> bool:
        """Check if domain is currently in cooldown."""
        if domain in self._blacklist:
            if time.time() < self._blacklist[domain]:
                return True
            else:
                del self._blacklist[domain]
        return False

    def get_stats(self, domain: str | None = None) -> dict[str, Any]:
        """Get statistics for a domain or all domains."""
        if domain:
            stats = self._domain_stats[domain]
            return {
                "domain": domain,
                "requests_made": stats.requests_made,
                "blocked_count": stats.blocked_count,
                "is_blocked": self.is_blocked(domain),
            }

        return {
            "total_domains": len(self._domain_stats),
            "blocked_domains": len(self._blacklist),
            "domains": {
                domain: self.get_stats(domain)
                for domain in self._domain_stats
            },
        }

    def reset(self, domain: str | None = None) -> None:
        """Reset rate limiter state."""
        if domain:
            if domain in self._domain_stats:
                del self._domain_stats[domain]
            if domain in self._blacklist:
                del self._blacklist[domain]
            if domain in self._domain_locks:
                del self._domain_locks[domain]
        else:
            self._domain_stats.clear()
            self._blacklist.clear()
            self._domain_locks.clear()


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on server responses.

    Automatically adjusts delay based on:
    - Response times
    - HTTP status codes (429, 403, etc.)
    - Server headers (Retry-After)
    """

    def __init__(self, config: RateLimitConfig | None = None):
        super().__init__(config)
        self._response_times: dict[str, list[float]] = defaultdict(list)

    def record_response(
        self,
        url: str,
        status_code: int,
        response_time: float,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Record response details for adaptive rate limiting."""
        domain = self._get_domain(url)

        # Track response times
        self._response_times[domain].append(response_time)
        if len(self._response_times[domain]) > 10:
            self._response_times[domain].pop(0)

        # Check for rate limit headers
        if headers:
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
            if retry_after:
                try:
                    wait_time = float(retry_after)
                    self._blacklist[domain] = time.time() + wait_time
                    logger.info(f"Retry-After header: {domain} cooldown {wait_time}s")
                except ValueError:
                    pass

        # Handle status codes
        if status_code == 429:  # Too Many Requests
            self.report_blocked(url)
        elif status_code == 403:  # Forbidden (possible bot detection)
            self.report_blocked(url)
        elif 200 <= status_code < 300:
            self.report_success(url)
        elif status_code >= 500:  # Server errors
            # Temporary backoff for server errors
            self._blacklist[domain] = time.time() + 10

    def get_adaptive_delay(self, domain: str) -> float:
        """Get adaptive delay based on response history."""
        times = self._response_times.get(domain, [])

        if not times:
            return self.config.min_delay

        avg_response = sum(times) / len(times)

        # If responses are slow, increase delay
        if avg_response > 2.0:
            return min(self.config.max_delay, self.config.min_delay * 2)
        elif avg_response > 1.0:
            return self.config.min_delay * 1.5

        return self.config.min_delay


# Global rate limiter instance
rate_limiter = AdaptiveRateLimiter()
