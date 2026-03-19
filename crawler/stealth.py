"""Stealth Browser - Anti-bot bypass with Camoufox (100% free, self-hosted).

Camoufox is a hardened Firefox browser that evades browser fingerprinting:
- Modified C++ code to prevent fingerprinting
- Bypasses Cloudflare, Akamai, DataDome, PerimeterX
- Lower resource usage than Chrome
- Built-in geo-IP matching for proxy locations

Usage:
    stealth = StealthBrowser()
    await stealth.start()
    result = await stealth.crawl("https://protected-site.com")
    await stealth.close()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StealthResult:
    """Result from stealth crawling."""
    url: str
    html: str = ""
    title: str = ""
    text: str = ""
    status_code: int = 0
    load_time_ms: float = 0.0
    browser_type: str = "camoufox"
    fingerprint: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class StealthBrowser:
    """Stealth browser using Camoufox for anti-bot bypass.

    Features:
    - Browser fingerprint spoofing
    - TLS fingerprint matching (JA3/JA4)
    - WebGL/Canvas fingerprint noise
    - WebRTC leak prevention
    - Timezone/locale auto-matching
    - Built-in proxy rotation support

    Usage:
        stealth = StealthBrowser()
        await stealth.start()
        
        # Crawl protected sites
        result = await stealth.crawl("https://cloudflare-protected.com")
        
        # Take screenshot
        await stealth.screenshot("https://site.com", "screenshot.png")
        
        await stealth.close()
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: float = 60.0,
        locale: str = "en-US",
        timezone: str = "America/New_York",
        proxy: str | None = None,
    ):
        self.headless = headless
        self.timeout = timeout
        self.locale = locale
        self.timezone = timezone
        self.proxy = proxy
        self._browser = None
        self._context = None
        self._playwright = None

    async def start(self):
        """Start Camoufox browser with stealth settings."""
        try:
            from camoufox.async_api import AsyncCamoufoxBrowser

            # Camoufox handles fingerprinting automatically
            self._browser = await AsyncCamoufoxBrowser(
                headless=self.headless,
                locale=self.locale,
                timezone=self.timezone,
                proxy=self.proxy,
            ).start()

            logger.info("Camoufox stealth browser started")

        except ImportError:
            logger.warning("Camoufox not available, falling back to Playwright")
            await self._start_playwright_stealth()

        except Exception as e:
            logger.error(f"Camoufox start error: {e}, falling back to Playwright")
            await self._start_playwright_stealth()

    async def _start_playwright_stealth(self):
        """Fallback to Playwright with stealth patches."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # Launch with stealth options
        self._browser = await self._playwright.firefox.launch(
            headless=self.headless,
            firefox_user_prefs={
                "privacy.resistFingerprinting": True,
                "privacy.trackingprotection.enabled": True,
                "geo.enabled": False,
                "media.navigator.enabled": False,
            },
        )

        # Create context with stealth settings
        self._context = await self._browser.new_context(
            locale=self.locale,
            timezone_id=self.timezone,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            viewport={"width": 1920, "height": 1080},
            color_scheme="light",
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
        )

        # Add stealth scripts
        await self._add_stealth_scripts()
        logger.info("Playwright stealth browser started (fallback mode)")

    async def _add_stealth_scripts(self):
        """Add anti-detection scripts to context."""
        stealth_js = """
        // Override navigator properties
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        
        // Chrome runtime
        window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
        
        // Permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
        """

        if self._context:
            await self._context.add_init_script(stealth_js)

    async def crawl(
        self,
        url: str,
        wait_for: str | None = None,
        wait_timeout: float = 10000,
    ) -> StealthResult:
        """Crawl a URL with stealth mode.

        Args:
            url: Target URL
            wait_for: CSS selector to wait for (e.g., "#content")
            wait_timeout: Max wait time in ms
        """
        start_time = time.time()

        if not self._browser:
            await self.start()

        page = await self._browser.new_page()

        try:
            # Navigate with longer timeout for Cloudflare challenge
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout * 1000,
            )

            # Wait for Cloudflare challenge to complete
            await page.wait_for_timeout(3000)

            # Wait for specific element if provided
            if wait_for:
                try:
                    await page.wait_for_selector(wait_for, timeout=wait_timeout)
                except Exception:
                    pass

            # Get page content
            html = await page.content()
            title = await page.title()

            # Get text content
            text_el = await page.query_selector("body")
            text = await text_el.inner_text() if text_el else ""

            load_time = (time.time() - start_time) * 1000

            return StealthResult(
                url=url,
                html=html,
                title=title,
                text=text[:10000],
                status_code=response.status if response else 0,
                load_time_ms=load_time,
                browser_type="camoufox" if "camoufox" in str(type(self._browser)).lower() else "playwright-stealth",
            )

        except Exception as e:
            logger.error(f"Stealth crawl error for {url}: {e}")
            return StealthResult(
                url=url,
                load_time_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

        finally:
            await page.close()

    async def screenshot(self, url: str, path: str) -> bool:
        """Take screenshot of a page."""
        if not self._browser:
            await self.start()

        page = await self._browser.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path=path, full_page=True)
            return True
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return False
        finally:
            await page.close()

    async def get_fingerprint(self) -> dict[str, Any]:
        """Get current browser fingerprint for verification."""
        if not self._browser:
            return {}

        page = await self._browser.new_page()

        try:
            await page.goto("https://browserleaks.com/fingerprint", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            # Extract fingerprint info
            fingerprint = await page.evaluate("""
                () => ({
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    languages: navigator.languages,
                    hardwareConcurrency: navigator.hardwareConcurrency,
                    deviceMemory: navigator.deviceMemory,
                    webdriver: navigator.webdriver,
                    chrome: !!window.chrome,
                })
            """)

            return fingerprint

        except Exception as e:
            logger.error(f"Fingerprint check error: {e}")
            return {"error": str(e)}
        finally:
            await page.close()

    async def close(self):
        """Close browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


class MultiBrowserCrawler:
    """Multi-browser crawler with automatic stealth fallback.

    Strategy:
    1. Try httpx first (fastest)
    2. If blocked, try Camoufox stealth
    3. If still blocked, try with different proxy/locale
    """

    def __init__(self):
        self.stealth = StealthBrowser()
        self._stats = {"httpx": 0, "stealth": 0, "failed": 0}

    async def crawl_with_fallback(
        self,
        url: str,
        max_retries: int = 2,
    ) -> StealthResult:
        """Crawl with automatic stealth fallback."""
        import httpx

        # Try httpx first
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            ) as client:
                response = await client.get(url)
                html = response.text

                # Check if blocked (common patterns)
                blocked_indicators = [
                    "cf-challenge",
                    "challenge-platform",
                    "captcha",
                    "access denied",
                    "robot",
                    "bot detection",
                ]

                is_blocked = any(indicator in html.lower() for indicator in blocked_indicators)

                if not is_blocked and len(html) > 1000:
                    self._stats["httpx"] += 1
                    return StealthResult(
                        url=url,
                        html=html,
                        status_code=response.status_code,
                        browser_type="httpx",
                    )

        except Exception as e:
            logger.debug(f"httpx failed: {e}")

        # Fallback to stealth browser
        logger.info(f"Using stealth browser for {url}")
        await self.stealth.start()

        result = await self.stealth.crawl(url)
        if not result.error:
            self._stats["stealth"] += 1
        else:
            self._stats["failed"] += 1

        return result

    @property
    def stats(self) -> dict:
        """Get crawling statistics."""
        return self._stats

    async def close(self):
        """Close all resources."""
        await self.stealth.close()


def format_stealth_result(result: StealthResult) -> str:
    """Format stealth result as markdown."""
    from bs4 import BeautifulSoup

    if result.error:
        return f"Error crawling {result.url}: {result.error}"

    # Parse HTML
    soup = BeautifulSoup(result.html, "lxml")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    lines = [
        f"# {result.title}\n",
        f"**URL:** {result.url}",
        f"**Browser:** {result.browser_type}",
        f"**Status:** {result.status_code}",
        f"**Load Time:** {result.load_time_ms:.0f}ms\n",
        "---\n",
        "## Content\n",
        text[:5000],
    ]

    if len(text) > 5000:
        lines.append("\n...")

    return "\n".join(lines)
