"""X/Twitter scraper - No API key required.

Uses Nitter instances (public Twitter frontend) and alternative methods
to scrape Twitter/X data without API access.

Methods:
1. Nitter instances - Public frontends that mirror Twitter
2. Syndication API - Twitter's public embed API
3. RSS feeds - via Nitter RSS

Based on Twint approach but using modern HTTP scraping.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Tweet:
    """A tweet/post."""
    id: str
    text: str
    username: str
    name: str = ""
    timestamp: str = ""
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    has_media: bool = False
    media_urls: list[str] = field(default_factory=list)
    quoted_tweet_id: str = ""
    url: str = ""


@dataclass
class TwitterUser:
    """Twitter/X user profile."""
    username: str
    name: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    tweets_count: int = 0
    verified: bool = False
    avatar_url: str = ""
    join_date: str = ""


# Known working Nitter instances (update as needed)
NITTER_INSTANCES = [
    "nitter.privacydev.net",
    "nitter.poast.org",
    "nitter.woodland.cafe",
    "xcancel.com",
]


class TwitterScraper:
    """Twitter/X scraper using Nitter and alternative methods.

    Usage:
        scraper = TwitterScraper()
        
        # Search tweets
        tweets = await scraper.search("python programming", limit=20)
        
        # Get user tweets
        tweets = await scraper.get_user_tweets("elonmusk", limit=20)
        
        # Get user profile
        profile = await scraper.get_user_profile("elonmusk")
        
        await scraper.close()
    """

    def __init__(
        self,
        nitter_instance: str | None = None,
        timeout: float = 30.0,
    ):
        self.nitter_instance = nitter_instance or NITTER_INSTANCES[0]
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
        return self._client

    async def _try_instances(self, path: str) -> str | None:
        """Try multiple Nitter instances until one works."""
        instances = [self.nitter_instance] + [i for i in NITTER_INSTANCES if i != self.nitter_instance]

        for instance in instances:
            url = f"https://{instance}{path}"
            try:
                client = await self._get_client()
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    self.nitter_instance = instance
                    return response.text
            except Exception:
                continue

        return None

    async def search(
        self,
        query: str,
        limit: int = 20,
        search_type: str = "top",
    ) -> list[Tweet]:
        """Search tweets using Nitter.

        Args:
            query: Search query
            limit: Number of tweets
            search_type: top, latest, media
        """
        path = f"/search?f=tweets&q={quote_plus(query)}&since=&until=&near="
        if search_type == "latest":
            path += "&scroll=down"

        html = await self._try_instances(path)
        if not html:
            logger.error("All Nitter instances failed")
            return []

        return self._parse_tweets(html, limit)

    async def get_user_tweets(
        self,
        username: str,
        limit: int = 20,
    ) -> list[Tweet]:
        """Get tweets from a specific user."""
        path = f"/{username}"
        html = await self._try_instances(path)

        if not html:
            return []

        return self._parse_tweets(html, limit)

    async def get_user_profile(self, username: str) -> TwitterUser | None:
        """Get user profile information."""
        path = f"/{username}"
        html = await self._try_instances(path)

        if not html:
            return None

        return self._parse_user_profile(html, username)

    def _parse_tweets(self, html: str, limit: int) -> list[Tweet]:
        """Parse tweets from HTML."""
        soup = BeautifulSoup(html, "lxml")
        tweets = []

        for item in soup.select(".timeline-item")[:limit]:
            try:
                tweet = self._parse_tweet(item)
                if tweet:
                    tweets.append(tweet)
            except Exception as e:
                logger.debug(f"Tweet parse error: {e}")
                continue

        return tweets

    def _parse_tweet(self, item) -> Tweet | None:
        """Parse a single tweet element."""
        # Get tweet link for ID
        link = item.select_one(".tweet-link")
        if not link:
            return None

        href = link.get("href", "")
        tweet_id = href.split("/")[-1] if "/" in href else ""

        # Get tweet content
        content_el = item.select_one(".tweet-content")
        text = content_el.get_text(strip=True) if content_el else ""

        # Get user info
        username_el = item.select_one(".username")
        username = username_el.get_text(strip=True).lstrip("@") if username_el else ""

        fullname_el = item.select_one(".fullname")
        name = fullname_el.get_text(strip=True) if fullname_el else ""

        # Get timestamp
        date_el = item.select_one(".tweet-date a")
        timestamp = date_el.get("title", "") if date_el else ""

        # Get engagement stats
        stats = item.select(".tweet-stat")
        likes = self._parse_stat(stats[0]) if len(stats) > 0 else 0
        retweets = self._parse_stat(stats[1]) if len(stats) > 1 else 0
        replies = self._parse_stat(stats[2]) if len(stats) > 2 else 0

        # Get media
        media_els = item.select(".attachment.image, .attachment.video")
        media_urls = []
        for media in media_els:
            img = media.select_one("img")
            if img and img.get("src"):
                media_urls.append(img["src"])

        return Tweet(
            id=tweet_id,
            text=text,
            username=username,
            name=name,
            timestamp=timestamp,
            likes=likes,
            retweets=retweets,
            replies=replies,
            has_media=len(media_urls) > 0,
            media_urls=media_urls[:3],
            url=f"https://twitter.com/{username}/status/{tweet_id}",
        )

    def _parse_stat(self, el) -> int:
        """Parse stat element for count."""
        if not el:
            return 0
        text = el.get_text(strip=True)
        if not text or text == "-":
            return 0
        return self._parse_count(text)

    def _parse_count(self, text: str) -> int:
        """Parse count text like '1.2K' to integer."""
        text = text.strip().upper().replace(",", "")
        if 'K' in text:
            return int(float(text.replace('K', '')) * 1000)
        elif 'M' in text:
            return int(float(text.replace('M', '')) * 1000000)
        try:
            return int(text)
        except ValueError:
            return 0

    def _parse_user_profile(self, html: str, username: str) -> TwitterUser:
        """Parse user profile from HTML."""
        soup = BeautifulSoup(html, "lxml")

        # Get profile info
        name_el = soup.select_one(".profile-card-fullname")
        name = name_el.get_text(strip=True) if name_el else username

        bio_el = soup.select_one(".profile-bio p")
        bio = bio_el.get_text(strip=True) if bio_el else ""

        # Get stats
        stats = soup.select(".profile-card-extra .profile-card-stat")
        followers = self._parse_stat(stats[0]) if len(stats) > 0 else 0
        following = self._parse_stat(stats[1]) if len(stats) > 1 else 0
        tweets_count = self._parse_stat(stats[2]) if len(stats) > 2 else 0

        # Get avatar
        avatar_el = soup.select_one(".profile-card-avatar img")
        avatar_url = ""
        if avatar_el:
            avatar_url = avatar_el.get("src", "")
            if avatar_url.startswith("/"):
                avatar_url = f"https://{self.nitter_instance}{avatar_url}"

        return TwitterUser(
            username=username,
            name=name,
            bio=bio,
            followers=followers,
            following=following,
            tweets_count=tweets_count,
            avatar_url=avatar_url,
        )

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


def format_tweets(tweets: list[Tweet], limit: int = 10) -> str:
    """Format tweets as markdown."""
    if not tweets:
        return "No tweets found."

    lines = []
    for i, tweet in enumerate(tweets[:limit], 1):
        lines.append(f"### {i}. @{tweet.username}")
        if tweet.name:
            lines.append(f"**{tweet.name}**")

        lines.append(f"\n{tweet.text}\n")

        stats = []
        if tweet.likes:
            stats.append(f"❤️ {tweet.likes}")
        if tweet.retweets:
            stats.append(f"🔄 {tweet.retweets}")
        if tweet.replies:
            stats.append(f"💬 {tweet.replies}")

        if stats:
            lines.append(" | ".join(stats))

        if tweet.url:
            lines.append(f"\n🔗 {tweet.url}")

        lines.append("")

    return "\n".join(lines)
