"""Tests for shared async HTTP client helpers."""

from __future__ import annotations

import httpx

from utils.http_client import AsyncHttpClientConfig, build_async_client


class FakeCacheOptions:
    """Minimal CacheOptions test double."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeSpecificationPolicy:
    """Minimal SpecificationPolicy test double."""

    def __init__(self, cache_options):
        self.cache_options = cache_options


class FakeAsyncCacheClient(httpx.AsyncClient):
    """Test double for Hishel AsyncCacheClient."""

    def __init__(self, *args, **kwargs):
        self.policy = kwargs.get("policy")
        super().__init__(*args, **{k: v for k, v in kwargs.items() if k != "policy"})


def test_build_async_client_falls_back_without_hishel(monkeypatch):
    """Build plain HTTPX client when Hishel is unavailable."""
    monkeypatch.setattr("utils.http_client._load_hishel_components", lambda: None)

    client = build_async_client(
        AsyncHttpClientConfig(enable_cache=True, cache_ttl=123)
    )

    assert isinstance(client, httpx.AsyncClient)
    assert client.__class__ is httpx.AsyncClient


def test_build_async_client_uses_hishel_when_available(monkeypatch):
    """Build Hishel-backed client when cache components are available."""
    monkeypatch.setattr(
        "utils.http_client._load_hishel_components",
        lambda: (FakeCacheOptions, FakeSpecificationPolicy, FakeAsyncCacheClient),
    )

    client = build_async_client(
        AsyncHttpClientConfig(
            enable_cache=True,
            cache_ttl=321,
            always_cache=True,
            refresh_on_hit=False,
        )
    )

    assert isinstance(client, FakeAsyncCacheClient)
    assert client.policy is not None
    assert client.policy.cache_options.kwargs["ttl"] == 321
    assert client.policy.cache_options.kwargs["always_cache"] is True
    assert client.policy.cache_options.kwargs["refresh_on_hit"] is False
