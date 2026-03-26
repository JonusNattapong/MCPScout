"""Helpers for building shared async HTTP clients.

Supports optional Hishel-backed HTTP caching while preserving a plain HTTPX
fallback when the caching dependency is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AsyncHttpClientConfig:
    """Configuration for async HTTP clients."""

    timeout: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True
    max_connections: int = 10
    max_keepalive_connections: int = 5
    enable_cache: bool = False
    cache_ttl: int = 900
    always_cache: bool = False
    refresh_on_hit: bool = True


def _load_hishel_components() -> tuple[Any, Any, Any] | None:
    """Load Hishel components lazily.

    Returns:
        Tuple of (CacheOptions, SpecificationPolicy, AsyncCacheClient)
        or None if Hishel is unavailable.
    """
    try:
        from hishel import CacheOptions, SpecificationPolicy
        from hishel.httpx import AsyncCacheClient
    except ImportError:
        return None

    return CacheOptions, SpecificationPolicy, AsyncCacheClient


def build_async_client(config: AsyncHttpClientConfig) -> httpx.AsyncClient:
    """Build an async HTTP client with optional caching."""
    limits = httpx.Limits(
        max_connections=config.max_connections,
        max_keepalive_connections=config.max_keepalive_connections,
    )

    client_kwargs = {
        "timeout": httpx.Timeout(config.timeout),
        "headers": config.headers,
        "follow_redirects": config.follow_redirects,
        "limits": limits,
    }

    if config.enable_cache:
        hishel_components = _load_hishel_components()
        if hishel_components is None:
            logger.info("Hishel not available; falling back to standard HTTPX client")
        else:
            CacheOptions, SpecificationPolicy, AsyncCacheClient = hishel_components
            return AsyncCacheClient(
                policy=SpecificationPolicy(
                    cache_options=CacheOptions(
                        ttl=config.cache_ttl,
                        always_cache=config.always_cache,
                        refresh_on_hit=config.refresh_on_hit,
                    )
                ),
                **client_kwargs,
            )

    return httpx.AsyncClient(**client_kwargs)
