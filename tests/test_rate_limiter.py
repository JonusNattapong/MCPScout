"""Tests for rate limiter."""

from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import patch

from utils.rate_limiter import (
    AdaptiveRateLimiter,
    DomainStats,
    RateLimitConfig,
    RateLimiter,
)


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.min_delay == 1.0
        assert config.max_delay == 3.0
        assert config.requests_per_minute == 30
        assert config.max_retries == 3
        assert config.backoff_multiplier == 2.0
        assert config.block_cooldown == 60.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            min_delay=0.5,
            max_delay=2.0,
            requests_per_minute=60,
            max_retries=5,
        )
        assert config.min_delay == 0.5
        assert config.max_delay == 2.0
        assert config.requests_per_minute == 60
        assert config.max_retries == 5


class TestDomainStats:
    """Test domain statistics."""

    def test_default_values(self):
        """Test default values."""
        stats = DomainStats()
        assert stats.requests_made == 0
        assert stats.last_request_time == 0.0
        assert stats.total_wait_time == 0.0
        assert stats.blocked_count == 0


class TestRateLimiter:
    """Test rate limiter."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter instance."""
        config = RateLimitConfig(min_delay=0.1, max_delay=0.2)
        return RateLimiter(config)

    def test_init(self, limiter):
        """Test initialization."""
        assert limiter.config.min_delay == 0.1
        assert limiter.config.max_delay == 0.2
        assert len(limiter._domain_stats) == 0
        assert len(limiter._blacklist) == 0

    def test_get_domain(self, limiter):
        """Test domain extraction."""
        assert limiter._get_domain("https://example.com/path") == "example.com"
        assert limiter._get_domain("http://sub.example.com") == "sub.example.com"
        assert limiter._get_domain("https://example.com:8080") == "example.com:8080"

    @pytest.mark.asyncio
    async def test_wait_basic(self, limiter):
        """Test basic wait functionality."""
        start = time.time()
        await limiter.wait("https://example.com")
        elapsed = time.time() - start

        # Should have waited at least min_delay
        assert elapsed >= 0.1
        assert limiter._domain_stats["example.com"].requests_made == 1

    @pytest.mark.asyncio
    async def test_wait_respects_delay(self, limiter):
        """Test that wait respects delay between requests."""
        await limiter.wait("https://example.com")
        
        start = time.time()
        await limiter.wait("https://example.com")
        elapsed = time.time() - start

        # Should have waited min_delay
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_wait_different_domains(self, limiter):
        """Test wait for different domains."""
        await limiter.wait("https://example1.com")
        await limiter.wait("https://example2.com")

        assert limiter._domain_stats["example1.com"].requests_made == 1
        assert limiter._domain_stats["example2.com"].requests_made == 1

    def test_report_blocked(self, limiter):
        """Test reporting blocked domain."""
        limiter.report_blocked("https://example.com")
        
        assert limiter._domain_stats["example.com"].blocked_count == 1
        assert limiter.is_blocked("example.com") is True

    def test_report_blocked_exponential_backoff(self, limiter):
        """Test exponential backoff on multiple blocks."""
        limiter.report_blocked("https://example.com")
        limiter.report_blocked("https://example.com")
        
        stats = limiter._domain_stats["example.com"]
        assert stats.blocked_count == 2
        
        # Cooldown should be doubled
        cooldown = limiter.config.block_cooldown * (2 ** (2 - 1))
        assert limiter._blacklist["example.com"] > time.time()

    def test_report_success(self, limiter):
        """Test reporting success."""
        limiter.report_blocked("https://example.com")
        limiter.report_success("https://example.com")
        
        stats = limiter._domain_stats["example.com"]
        assert stats.blocked_count == 0

    def test_is_blocked(self, limiter):
        """Test blocked check."""
        assert limiter.is_blocked("example.com") is False
        
        limiter.report_blocked("https://example.com")
        assert limiter.is_blocked("example.com") is True

    def test_is_blocked_expired(self, limiter):
        """Test blocked check with expired cooldown."""
        limiter._blacklist["example.com"] = time.time() - 10  # Expired 10s ago
        assert limiter.is_blocked("example.com") is False

    def test_get_stats_single_domain(self, limiter):
        """Test getting stats for single domain."""
        limiter.report_blocked("https://example.com")
        stats = limiter.get_stats("example.com")
        
        assert stats["domain"] == "example.com"
        assert stats["blocked_count"] == 1
        assert stats["is_blocked"] is True

    def test_get_stats_all_domains(self, limiter):
        """Test getting stats for all domains."""
        limiter.report_blocked("https://example1.com")
        limiter.report_blocked("https://example2.com")
        
        stats = limiter.get_stats()
        assert stats["total_domains"] == 2
        assert stats["blocked_domains"] == 2

    def test_reset_domain(self, limiter):
        """Test resetting single domain."""
        limiter.report_blocked("https://example.com")
        limiter.reset("example.com")
        
        assert "example.com" not in limiter._domain_stats
        assert "example.com" not in limiter._blacklist

    def test_reset_all(self, limiter):
        """Test resetting all domains."""
        limiter.report_blocked("https://example1.com")
        limiter.report_blocked("https://example2.com")
        limiter.reset()
        
        assert len(limiter._domain_stats) == 0
        assert len(limiter._blacklist) == 0


class TestAdaptiveRateLimiter:
    """Test adaptive rate limiter."""

    @pytest.fixture
    def limiter(self):
        """Create an adaptive rate limiter instance."""
        config = RateLimitConfig(min_delay=0.1, max_delay=0.2)
        return AdaptiveRateLimiter(config)

    def test_init(self, limiter):
        """Test initialization."""
        assert isinstance(limiter, RateLimiter)
        assert len(limiter._response_times) == 0

    def test_record_response_success(self, limiter):
        """Test recording successful response."""
        limiter.record_response("https://example.com", 200, 0.5)
        
        assert len(limiter._response_times["example.com"]) == 1
        assert limiter._response_times["example.com"][0] == 0.5

    def test_record_response_429(self, limiter):
        """Test recording 429 response."""
        limiter.record_response("https://example.com", 429, 0.5)
        
        assert limiter.is_blocked("example.com") is True

    def test_record_response_403(self, limiter):
        """Test recording 403 response."""
        limiter.record_response("https://example.com", 403, 0.5)
        
        assert limiter.is_blocked("example.com") is True

    def test_record_response_500(self, limiter):
        """Test recording 500 response."""
        limiter.record_response("https://example.com", 500, 0.5)
        
        # Should apply temporary backoff
        assert limiter.is_blocked("example.com") is True

    def test_record_response_retry_after_header(self, limiter):
        """Test Retry-After header handling."""
        limiter.record_response(
            "https://example.com",
            429,
            0.5,
            headers={"Retry-After": "30"},
        )
        
        assert limiter.is_blocked("example.com") is True

    def test_get_adaptive_delay_slow_responses(self, limiter):
        """Test adaptive delay for slow responses."""
        # Record slow responses
        for _ in range(5):
            limiter.record_response("https://example.com", 200, 3.0)
        
        delay = limiter.get_adaptive_delay("example.com")
        assert delay > limiter.config.min_delay

    def test_get_adaptive_delay_fast_responses(self, limiter):
        """Test adaptive delay for fast responses."""
        # Record fast responses
        for _ in range(5):
            limiter.record_response("https://example.com", 200, 0.1)
        
        delay = limiter.get_adaptive_delay("example.com")
        assert delay == limiter.config.min_delay

    def test_get_adaptive_delay_no_history(self, limiter):
        """Test adaptive delay with no history."""
        delay = limiter.get_adaptive_delay("example.com")
        assert delay == limiter.config.min_delay

    def test_response_times_limit(self, limiter):
        """Test that response times are limited to 10 entries."""
        for i in range(15):
            limiter.record_response("https://example.com", 200, float(i))
        
        assert len(limiter._response_times["example.com"]) == 10
