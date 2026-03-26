"""Tests for search parser selection and fallback behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from search.aggregator import DuckDuckGoEngine


class DummyResponse:
    """Minimal HTTP response double."""

    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        """Pretend the response is successful."""


@pytest.mark.asyncio
async def test_duckduckgo_uses_selectolax_when_available(monkeypatch):
    """Engine should prefer selectolax parser when available."""
    client = AsyncMock()
    client.post.return_value = DummyResponse("<html></html>")
    engine = DuckDuckGoEngine(client)

    selectolax_called = False
    bs4_called = False

    def fake_selectolax(html: str, max_results: int):
        nonlocal selectolax_called
        selectolax_called = True
        return []

    def fake_bs4(html: str, max_results: int):
        nonlocal bs4_called
        bs4_called = True
        return []

    monkeypatch.setattr("search.aggregator.HAS_SELECTOLAX", True)
    monkeypatch.setattr(engine, "_parse_selectolax", fake_selectolax)
    monkeypatch.setattr(engine, "_parse_beautifulsoup", fake_bs4)

    await engine.search("test", max_results=5)

    assert selectolax_called is True
    assert bs4_called is False


@pytest.mark.asyncio
async def test_duckduckgo_falls_back_to_beautifulsoup(monkeypatch):
    """Engine should use BeautifulSoup parser when selectolax is disabled."""
    client = AsyncMock()
    client.post.return_value = DummyResponse("<html></html>")
    engine = DuckDuckGoEngine(client)

    selectolax_called = False
    bs4_called = False

    def fake_selectolax(html: str, max_results: int):
        nonlocal selectolax_called
        selectolax_called = True
        return []

    def fake_bs4(html: str, max_results: int):
        nonlocal bs4_called
        bs4_called = True
        return []

    monkeypatch.setattr("search.aggregator.HAS_SELECTOLAX", False)
    monkeypatch.setattr(engine, "_parse_selectolax", fake_selectolax)
    monkeypatch.setattr(engine, "_parse_beautifulsoup", fake_bs4)

    await engine.search("test", max_results=5)

    assert selectolax_called is False
    assert bs4_called is True
