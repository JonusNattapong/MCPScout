"""Facebook public page scraper.

Scrapes public data from Facebook pages using browser automation.
Requires Playwright for JS rendering (Facebook is JS-heavy).

Limitations:
- Only public page data (posts, about, reviews)
- No login required for public pages
- May be blocked by Facebook's anti-bot measures
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class FacebookPost:
    """A Facebook page post."""
    id: str
    text: str
    timestamp: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    image_url: str = ""
    link_url: str = ""
    is_shared: bool = False


@dataclass
class FacebookPage:
    """Facebook page info."""
    name: str
    url: str
    about: str = ""
    category: str = ""
    followers: str = ""
    rating: float = 0.0
    posts: list[FacebookPost] = field(default_factory=list)


class FacebookScraper:
    """Facebook public page scraper using Playwright.

    Usage:
        scraper = FacebookScraper()
        await scraper.start()
        
        page = await scraper.scrape_page("https://facebook.com/somepage")
        
        await scraper.close()
    """

    def __init__(self, headless: bool = True, timeout: float = 60.0):
        self.headless = headless
        self.timeout = timeout
        self._browser = None
        self._context = None
        self._playwright = None

    async def start(self):
        """Start browser."""
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled'],
        )
        self._context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

    async def scrape_page(
        self,
        url: str,
        max_posts: int = 10,
    ) -> FacebookPage:
        """Scrape a Facebook public page.

        Args:
            url: Facebook page URL
            max_posts: Maximum posts to scrape
        """
        if not self._browser:
            await self.start()

        page = await self._context.new_page()

        try:
            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)

            # Wait for content to load
            await page.wait_for_timeout(3000)

            # Get page info
            info = await self._extract_page_info(page)

            # Scroll and get posts
            posts = await self._extract_posts(page, max_posts)

            return FacebookPage(
                name=info.get("name", ""),
                url=url,
                about=info.get("about", ""),
                category=info.get("category", ""),
                followers=info.get("followers", ""),
                rating=info.get("rating", 0.0),
                posts=posts,
            )

        except Exception as e:
            logger.error(f"Facebook scrape error: {e}")
            return FacebookPage(name="", url=url)

        finally:
            await page.close()

    async def _extract_page_info(self, page) -> dict:
        """Extract page information."""
        info = {}

        try:
            # Get page name
            name_el = await page.query_selector("h1")
            if name_el:
                info["name"] = await name_el.text_content() or ""

            # Get about section
            about_el = await page.query_selector('[data-testid="page-about-section"]')
            if about_el:
                info["about"] = await about_el.text_content() or ""

            # Get category
            category_el = await page.query_selector('[data-testid="page-category"]')
            if category_el:
                info["category"] = await category_el.text_content() or ""

            # Get followers
            followers_el = await page.query_selector('a[href*="followers"]')
            if followers_el:
                info["followers"] = await followers_el.text_content() or ""

        except Exception as e:
            logger.debug(f"Info extraction error: {e}")

        return info

    async def _extract_posts(self, page, max_posts: int) -> list[FacebookPost]:
        """Extract posts from page."""
        posts = []

        try:
            # Scroll to load posts
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

            # Get post elements
            post_elements = await page.query_selector_all('[data-testid="post-container"]')

            for i, post_el in enumerate(post_elements[:max_posts]):
                try:
                    post = await self._parse_post(post_el, i)
                    if post:
                        posts.append(post)
                except Exception as e:
                    logger.debug(f"Post parse error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Posts extraction error: {e}")

        return posts

    async def _parse_post(self, post_el, index: int) -> FacebookPost | None:
        """Parse a single post element."""
        try:
            # Get text content
            text_el = await post_el.query_selector('[data-testid="post-message"]')
            text = await text_el.text_content() if text_el else ""

            # Get engagement
            likes = await self._extract_count(post_el, "like")
            comments = await self._extract_count(post_el, "comment")
            shares = await self._extract_count(post_el, "share")

            # Get image
            img_el = await post_el.query_selector("img")
            image_url = await img_el.get_attribute("src") if img_el else ""

            # Get link
            link_el = await post_el.query_selector('a[href^="http"]')
            link_url = await link_el.get_attribute("href") if link_el else ""

            return FacebookPost(
                id=f"post_{index}",
                text=text[:1000] if text else "",
                likes=likes,
                comments=comments,
                shares=shares,
                image_url=image_url or "",
                link_url=link_url or "",
            )

        except Exception as e:
            logger.debug(f"Post parse error: {e}")
            return None

    async def _extract_count(self, post_el, type: str) -> int:
        """Extract engagement count."""
        try:
            el = await post_el.query_selector(f'[aria-label*="{type}"]')
            if el:
                text = await el.text_content() or ""
                # Extract number from text like "1.2K" or "156"
                numbers = re.findall(r'[\d.]+[KMB]?', text)
                if numbers:
                    return self._parse_count(numbers[0])
        except Exception:
            pass
        return 0

    def _parse_count(self, text: str) -> int:
        """Parse count text like '1.2K' to integer."""
        text = text.strip().upper()
        if 'K' in text:
            return int(float(text.replace('K', '')) * 1000)
        elif 'M' in text:
            return int(float(text.replace('M', '')) * 1000000)
        elif 'B' in text:
            return int(float(text.replace('B', '')) * 1000000000)
        try:
            return int(text)
        except ValueError:
            return 0

    async def close(self):
        """Close browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


def format_facebook_page(page: FacebookPage) -> str:
    """Format Facebook page as markdown."""
    lines = [
        f"# {page.name}\n",
        f"**URL:** {page.url}",
        f"**Category:** {page.category}",
        f"**Followers:** {page.followers}",
        f"**Rating:** {page.rating}\n",
    ]

    if page.about:
        lines.extend(["## About", page.about[:500], ""])

    if page.posts:
        lines.append("## Recent Posts\n")
        for i, post in enumerate(page.posts[:10], 1):
            lines.append(f"### Post {i}")
            if post.text:
                lines.append(post.text[:300])
            lines.append(f"👍 {post.likes} | 💬 {post.comments} | ↗️ {post.shares}")
            if post.link_url:
                lines.append(f"**Link:** {post.link_url}")
            lines.append("")

    return "\n".join(lines)
