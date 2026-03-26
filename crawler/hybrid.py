"""Hybrid crawler combining httpx (fast) + Playwright (JS rendering).

Architecture (2026 production pattern):
1. Try httpx first (fast, low resource)
2. Detect JS-heavy pages (empty containers, framework markers)
3. Fallback to Playwright for rendering
4. Smart routing based on page analysis

This gives you:
- Speed: httpx for 80-90% static pages
- JS Support: Playwright for dynamic content
- Anti-bot: Playwright with stealth mode
- Resource efficiency: Browser only when needed
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from utils.cache import CrawlCache, CacheConfig

logger = logging.getLogger(__name__)


class RenderMethod(Enum):
    """Rendering method used."""
    HTTPX = "httpx"  # Fast, static
    PLAYWRIGHT = "playwright"  # JS rendering


@dataclass
class HybridResult:
    """Result from hybrid crawling."""
    url: str
    html: str = ""
    text: str = ""
    title: str = ""
    render_method: RenderMethod = RenderMethod.HTTPX
    load_time_ms: float = 0.0
    js_detected: bool = False
    js_framework: str = ""
    content_length: int = 0
    status_code: int = 0
    error: str | None = None


# JS framework detection patterns
JS_FRAMEWORK_MARKERS = {
    "react": ['id="root"', 'id="__next"', 'data-reactroot', '_reactRootContainer'],
    "vue": ['id="app"', 'data-v-', '__vue__', 'v-for=', 'v-if='],
    "angular": ['ng-app', 'ng-controller', 'data-ng-', 'ng-version'],
    "svelte": ['__svelte', 'svelte-', 'data-svelte'],
    "nextjs": ['id="__next"', '_next/static', 'next/head'],
    "nuxt": ['__NUXT__', '_nuxt/', 'nuxt.js'],
    "spa_indicators": ['window.__INITIAL_STATE__', 'window.__PRELOADED_STATE__', 'data-state='],
}


class JSPageDetector:
    """Detect if a page requires JavaScript rendering."""

    # Empty container patterns (SPA shells)
    EMPTY_CONTAINER_PATTERNS = [
        r'<div\s+id="app"\s*>\s*</div>',
        r'<div\s+id="root"\s*>\s*</div>',
        r'<div\s+id="__next"\s*>\s*</div>',
        r'<div\s+id="app"\s*/>',
        r'<div\s+id="root"\s*/>',
    ]

    # Scripts that indicate JS-heavy page
    JS_INDICATORS = [
        'src="/static/js/',
        'src="/assets/js/',
        '.bundle.js',
        '.chunk.js',
        'webpack',
        'react.production',
        'vue.runtime',
        'angular.cli',
    ]

    @classmethod
    def analyze(cls, html: str) -> dict[str, Any]:
        """Analyze HTML to determine if JS rendering is needed."""
        result = {
            "needs_js": False,
            "confidence": 0.0,
            "framework": "",
            "reasons": [],
        }

        # Check for empty containers (strong signal)
        for pattern in cls.EMPTY_CONTAINER_PATTERNS:
            if re.search(pattern, html, re.IGNORECASE):
                result["needs_js"] = True
                result["confidence"] = 0.9
                result["reasons"].append("empty_js_container")
                break

        # Check for JS framework markers
        for framework, markers in JS_FRAMEWORK_MARKERS.items():
            for marker in markers:
                if marker in html:
                    result["needs_js"] = True
                    result["confidence"] = max(result["confidence"], 0.7)
                    result["framework"] = framework
                    result["reasons"].append(f"framework:{framework}")
                    break

        # Check for JS indicators in script tags
        for indicator in cls.JS_INDICATORS:
            if indicator in html.lower():
                result["confidence"] = max(result["confidence"], 0.4)
                result["reasons"].append(f"js_indicator:{indicator}")

        # Check content ratio (text vs total size)
        soup = BeautifulSoup(html, "lxml")
        text_length = len(soup.get_text(strip=True))
        total_length = len(html)

        if total_length > 0:
            text_ratio = text_length / total_length
            if text_ratio < 0.1 and total_length > 5000:
                result["confidence"] = max(result["confidence"], 0.5)
                result["reasons"].append("low_text_ratio")

        # Final decision
        if result["confidence"] >= 0.6:
            result["needs_js"] = True

        return result


class PlaywrightRenderer:
    """Render pages using Playwright."""

    # Resource types to block for faster crawling
    BLOCKED_RESOURCE_TYPES = {
        "image",
        "font",
        "media",
        "stylesheet",
    }

    # URL patterns to block (analytics, ads, tracking)
    BLOCKED_URL_PATTERNS = [
        r"google-analytics\.com",
        r"googletagmanager\.com",
        r"doubleclick\.net",
        r"facebook\.net",
        r"hotjar\.com",
        r"mixpanel\.com",
        r"segment\.io",
        r"amplitude\.com",
    ]

    def __init__(
        self,
        headless: bool = True,
        timeout: float = 30.0,
        wait_for_selector: str | None = None,
        block_resources: bool = True,
    ):
        self.headless = headless
        self.timeout = timeout
        self.wait_for_selector = wait_for_selector
        self.block_resources = block_resources
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        """Lazy initialize browser."""
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ],
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1920, "height": 1080},
            )

            # Setup request blocking for faster crawling
            if self.block_resources:
                await self._context.route("**/*", self._route_handler)

    async def _route_handler(self, route) -> None:
        """Block unnecessary resources to speed up page loading."""
        resource_type = route.request.resource_type
        url = route.request.url

        # Block by resource type
        if resource_type in self.BLOCKED_RESOURCE_TYPES:
            await route.abort()
            return

        # Block by URL pattern (analytics, ads, tracking)
        for pattern in self.BLOCKED_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                await route.abort()
                return

        # Allow all other requests
        await route.continue_()

    async def render(self, url: str) -> HybridResult:
        """Render a URL using Playwright."""
        await self._ensure_browser()

        start_time = time.time()

        try:
            page = await self._context.new_page()

            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=self.timeout * 1000,
            )

            # Wait for content if specified
            if self.wait_for_selector:
                try:
                    await page.wait_for_selector(
                        self.wait_for_selector,
                        timeout=10000,
                    )
                except Exception:
                    pass  # Continue even if selector not found

            # Get rendered HTML
            html = await page.content()

            # Get title
            title = await page.title()

            await page.close()

            load_time = (time.time() - start_time) * 1000

            return HybridResult(
                url=url,
                html=html,
                title=title,
                render_method=RenderMethod.PLAYWRIGHT,
                load_time_ms=load_time,
                content_length=len(html),
                status_code=response.status if response else 0,
            )

        except Exception as e:
            logger.error(f"Playwright render error for {url}: {e}")
            return HybridResult(
                url=url,
                render_method=RenderMethod.PLAYWRIGHT,
                load_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    async def close(self):
        """Close browser resources."""
        if self._browser:
            await self._browser.close()
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()


class HybridCrawler:
    """Hybrid crawler with smart routing between httpx and Playwright.

    Usage:
        crawler = HybridCrawler()
        result = await crawler.crawl("https://example.com")
        # Automatically uses httpx or Playwright based on page analysis

        # Force Playwright for known JS-heavy sites
        result = await crawler.crawl("https://spa-site.com", force_browser=True)

        # Batch crawl with smart routing
        results = await crawler.crawl_batch(["https://static.com", "https://spa.com"])
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        timeout: float = 30.0,
        headless: bool = True,
        auto_detect_js: bool = True,
        force_browser_domains: list[str] | None = None,
        enable_cache: bool = True,
        cache_config: CacheConfig | None = None,
        block_resources: bool = True,
    ):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.headless = headless
        self.auto_detect_js = auto_detect_js
        self.force_browser_domains = force_browser_domains or []
        self.enable_cache = enable_cache
        self.block_resources = block_resources

        self._httpx_client: httpx.AsyncClient | None = None
        self._playwright_renderer: PlaywrightRenderer | None = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._cache: CrawlCache | None = None
        
        if enable_cache:
            self._cache = CrawlCache(cache_config)

    async def _get_httpx_client(self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
        return self._httpx_client

    def _get_playwright_renderer(self) -> PlaywrightRenderer:
        """Get or create Playwright renderer."""
        if self._playwright_renderer is None:
            self._playwright_renderer = PlaywrightRenderer(
                headless=self.headless,
                timeout=self.timeout,
                block_resources=self.block_resources,
            )
        return self._playwright_renderer

    def _should_force_browser(self, url: str) -> bool:
        """Check if URL should always use browser."""
        domain = urlparse(url).netloc.lower()
        for forced_domain in self.force_browser_domains:
            if domain.endswith(forced_domain.lower()):
                return True
        return False

    async def crawl(
        self,
        url: str,
        force_browser: bool = False,
        wait_for_selector: str | None = None,
        use_cache: bool = True,
    ) -> HybridResult:
        """Crawl a URL with smart routing.

        Args:
            url: URL to crawl
            force_browser: Force Playwright rendering
            wait_for_selector: CSS selector to wait for (forces browser)
            use_cache: Whether to use cache (default: True)
        """
        # Check cache first
        if use_cache and self.enable_cache and self._cache:
            cached = self._cache.get(url)
            if cached:
                logger.debug(f"Cache hit for {url}")
                return HybridResult(
                    url=url,
                    html=cached["content"],
                    title=cached["metadata"].get("title", ""),
                    render_method=RenderMethod(cached["metadata"].get("render_method", "httpx")),
                    load_time_ms=0,
                    content_length=len(cached["content"]),
                    status_code=cached["metadata"].get("status_code", 200),
                )

        async with self._semaphore:
            # Force browser if requested
            if force_browser or wait_for_selector or self._should_force_browser(url):
                renderer = self._get_playwright_renderer()
                if wait_for_selector:
                    renderer.wait_for_selector = wait_for_selector
                result = await renderer.render(url)
                
                # Cache the result
                if use_cache and self.enable_cache and self._cache and not result.error:
                    self._cache.set(
                        url,
                        result.html,
                        metadata={
                            "title": result.title,
                            "render_method": result.render_method.value,
                            "status_code": result.status_code,
                        },
                    )
                
                return result

            # Step 1: Try httpx first (fast)
            start_time = time.time()
            client = await self._get_httpx_client()

            try:
                response = await client.get(url)
                html = response.text
                load_time = (time.time() - start_time) * 1000

                # Parse HTML
                soup = BeautifulSoup(html, "lxml")
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else ""

                result = HybridResult(
                    url=url,
                    html=html,
                    text=soup.get_text(strip=True)[:5000],
                    title=title,
                    render_method=RenderMethod.HTTPX,
                    load_time_ms=load_time,
                    content_length=len(html),
                    status_code=response.status_code,
                )

                # Step 2: Analyze if JS rendering is needed
                if self.auto_detect_js:
                    analysis = JSPageDetector.analyze(html)
                    result.js_detected = analysis["needs_js"]
                    result.js_framework = analysis["framework"]

                    if analysis["needs_js"]:
                        logger.info(f"JS detected for {url}, switching to Playwright")

                        # Re-crawl with Playwright
                        renderer = self._get_playwright_renderer()
                        browser_result = await renderer.render(url)

                        if not browser_result.error:
                            # Use Playwright result
                            browser_result.js_detected = True
                            browser_result.js_framework = analysis["framework"]
                            
                            # Cache the result
                            if use_cache and self.enable_cache and self._cache:
                                self._cache.set(
                                    url,
                                    browser_result.html,
                                    metadata={
                                        "title": browser_result.title,
                                        "render_method": browser_result.render_method.value,
                                        "status_code": browser_result.status_code,
                                    },
                                )
                            
                            return browser_result

                # Cache the httpx result
                if use_cache and self.enable_cache and self._cache:
                    self._cache.set(
                        url,
                        result.html,
                        metadata={
                            "title": result.title,
                            "render_method": result.render_method.value,
                            "status_code": result.status_code,
                        },
                    )

                return result

            except Exception as e:
                logger.error(f"httpx crawl error for {url}: {e}")

                # Fallback to Playwright on httpx error
                logger.info(f"Falling back to Playwright for {url}")
                renderer = self._get_playwright_renderer()
                result = await renderer.render(url)
                
                # Cache the result
                if use_cache and self.enable_cache and self._cache and not result.error:
                    self._cache.set(
                        url,
                        result.html,
                        metadata={
                            "title": result.title,
                            "render_method": result.render_method.value,
                            "status_code": result.status_code,
                        },
                    )
                
                return result

    async def crawl_batch(
        self,
        urls: list[str],
        force_browser: bool = False,
        use_cache: bool = True,
    ) -> list[HybridResult]:
        """Crawl multiple URLs with smart routing."""
        tasks = [self.crawl(url, force_browser=force_browser, use_cache=use_cache) for url in urls]
        return await asyncio.gather(*tasks)

    async def close(self):
        """Close all resources."""
        if self._httpx_client:
            await self._httpx_client.aclose()
        if self._playwright_renderer:
            await self._playwright_renderer.close()
    
    def get_cache_stats(self) -> dict[str, Any] | None:
        """Get cache statistics if caching is enabled."""
        if self._cache:
            return self._cache.get_stats()
        return None
    
    def clear_cache(self) -> int:
        """Clear cache if caching is enabled."""
        if self._cache:
            return self._cache.clear()
        return 0


class HybridCrawlResult:
    """Aggregated results from hybrid crawling."""

    def __init__(self):
        self.results: list[HybridResult] = []
        self.httpx_count: int = 0
        self.playwright_count: int = 0
        self.total_time_ms: float = 0.0

    def add(self, result: HybridResult):
        """Add a result."""
        self.results.append(result)
        if result.render_method == RenderMethod.HTTPX:
            self.httpx_count += 1
        else:
            self.playwright_count += 1
        self.total_time_ms += result.load_time_ms

    @property
    def stats(self) -> dict:
        """Get statistics."""
        return {
            "total_pages": len(self.results),
            "httpx_pages": self.httpx_count,
            "playwright_pages": self.playwright_count,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.total_time_ms / len(self.results) if self.results else 0,
            "js_detected": sum(1 for r in self.results if r.js_detected),
        }
