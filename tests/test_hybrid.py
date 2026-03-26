"""Tests for hybrid crawler."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.hybrid import (
    HybridCrawler,
    HybridResult,
    JSPageDetector,
    PlaywrightRenderer,
    RenderMethod,
)


class TestJSPageDetector:
    """Test JS page detection."""

    def test_detects_empty_container(self):
        """Test detection of empty JS containers."""
        html = '<div id="app"></div>'
        result = JSPageDetector.analyze(html)
        assert result["needs_js"] is True
        assert result["confidence"] >= 0.9

    def test_detects_react_framework(self):
        """Test React framework detection."""
        html = '<div id="root" data-reactroot></div>'
        result = JSPageDetector.analyze(html)
        assert result["needs_js"] is True
        assert "react" in result["framework"].lower() or result["confidence"] >= 0.7

    def test_detects_vue_framework(self):
        """Test Vue framework detection."""
        html = '<div id="app" data-v-123></div>'
        result = JSPageDetector.analyze(html)
        assert result["needs_js"] is True

    def test_static_page_no_js(self):
        """Test static page doesn't trigger JS detection."""
        html = """
        <html>
            <head><title>Static Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>This is a static page with plenty of content.</p>
            </body>
        </html>
        """
        result = JSPageDetector.analyze(html)
        assert result["needs_js"] is False

    def test_low_text_ratio(self):
        """Test low text ratio detection."""
        # Create HTML with lots of markup but little text
        html = "<div>" + "<span></span>" * 1000 + "</div>"
        result = JSPageDetector.analyze(html)
        # Should detect low text ratio
        assert "low_text_ratio" in result["reasons"] or result["confidence"] > 0


class TestHybridCrawler:
    """Test hybrid crawler."""

    @pytest.fixture
    def crawler(self):
        """Create a crawler instance."""
        return HybridCrawler(
            max_concurrent=2,
            timeout=10.0,
            enable_cache=False,  # Disable cache for testing
        )

    def test_init(self, crawler):
        """Test crawler initialization."""
        assert crawler.max_concurrent == 2
        assert crawler.timeout == 10.0
        assert crawler.enable_cache is False
        assert crawler._cache is None

    def test_init_with_cache(self):
        """Test crawler initialization with cache enabled."""
        crawler = HybridCrawler(enable_cache=True)
        assert crawler.enable_cache is True
        assert crawler._cache is not None

    def test_should_force_browser(self, crawler):
        """Test force browser domain detection."""
        crawler.force_browser_domains = ["example.com"]
        assert crawler._should_force_browser("https://example.com/page") is True
        assert crawler._should_force_browser("https://other.com/page") is False

    @pytest.mark.asyncio
    async def test_crawl_with_httpx(self, crawler):
        """Test crawling with httpx."""
        mock_response = MagicMock()
        mock_response.text = "<html><head><title>Test</title></head><body>Content</body></html>"
        mock_response.status_code = 200

        with patch("crawler.hybrid.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await crawler.crawl("https://example.com")

            assert result.url == "https://example.com"
            assert result.title == "Test"
            assert result.status_code == 200
            assert result.render_method == RenderMethod.HTTPX

    @pytest.mark.asyncio
    async def test_crawl_with_force_browser(self, crawler):
        """Test crawling with forced browser rendering."""
        mock_renderer = AsyncMock()
        mock_renderer.render.return_value = HybridResult(
            url="https://example.com",
            html="<html>Rendered</html>",
            title="Rendered",
            render_method=RenderMethod.PLAYWRIGHT,
            status_code=200,
        )

        crawler._playwright_renderer = mock_renderer

        result = await crawler.crawl("https://example.com", force_browser=True)

        assert result.render_method == RenderMethod.PLAYWRIGHT
        mock_renderer.render.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_batch(self, crawler):
        """Test batch crawling."""
        mock_response = MagicMock()
        mock_response.text = "<html><title>Test</title></html>"
        mock_response.status_code = 200

        with patch("crawler.hybrid.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            urls = ["https://example1.com", "https://example2.com"]
            results = await crawler.crawl_batch(urls)

            assert len(results) == 2
            assert all(r.status_code == 200 for r in results)

    @pytest.mark.asyncio
    async def test_crawl_error_handling(self, crawler):
        """Test error handling in crawl."""
        with patch("crawler.hybrid.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock Playwright renderer for fallback
            mock_renderer = AsyncMock()
            mock_renderer.render.return_value = HybridResult(
                url="https://example.com",
                html="<html>Fallback</html>",
                render_method=RenderMethod.PLAYWRIGHT,
                status_code=200,
            )
            crawler._playwright_renderer = mock_renderer

            result = await crawler.crawl("https://example.com")

            # Should fallback to Playwright
            assert result.render_method == RenderMethod.PLAYWRIGHT


class FakeRouteRequest:
    """Minimal Playwright request double."""

    def __init__(self, resource_type: str, url: str):
        self.resource_type = resource_type
        self.url = url


class FakeRoute:
    """Minimal Playwright route double."""

    def __init__(self, resource_type: str, url: str):
        self.request = FakeRouteRequest(resource_type, url)
        self.aborted = False
        self.continued = False

    async def abort(self):
        self.aborted = True

    async def continue_(self):
        self.continued = True


class TestPlaywrightRequestBlocking:
    """Test resource blocking rules in Playwright renderer."""

    @pytest.mark.asyncio
    async def test_blocks_unnecessary_resource_types(self):
        """Image/font/media/stylesheet requests should be blocked."""
        renderer = PlaywrightRenderer(block_resources=True)
        route = FakeRoute("image", "https://example.com/logo.png")

        await renderer._route_handler(route)

        assert route.aborted is True
        assert route.continued is False

    @pytest.mark.asyncio
    async def test_blocks_tracking_urls(self):
        """Tracking and analytics URLs should be blocked."""
        renderer = PlaywrightRenderer(block_resources=True)
        route = FakeRoute("script", "https://www.google-analytics.com/analytics.js")

        await renderer._route_handler(route)

        assert route.aborted is True
        assert route.continued is False

    @pytest.mark.asyncio
    async def test_allows_document_requests(self):
        """Primary document requests should continue."""
        renderer = PlaywrightRenderer(block_resources=True)
        route = FakeRoute("document", "https://example.com/")

        await renderer._route_handler(route)

        assert route.aborted is False
        assert route.continued is True


class TestHybridResult:
    """Test HybridResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = HybridResult(url="https://example.com")
        assert result.url == "https://example.com"
        assert result.html == ""
        assert result.title == ""
        assert result.render_method == RenderMethod.HTTPX
        assert result.load_time_ms == 0.0
        assert result.js_detected is False
        assert result.error is None

    def test_custom_values(self):
        """Test custom values."""
        result = HybridResult(
            url="https://example.com",
            html="<html>Test</html>",
            title="Test Page",
            render_method=RenderMethod.PLAYWRIGHT,
            load_time_ms=150.5,
            status_code=200,
        )
        assert result.html == "<html>Test</html>"
        assert result.title == "Test Page"
        assert result.render_method == RenderMethod.PLAYWRIGHT
        assert result.load_time_ms == 150.5
        assert result.status_code == 200
