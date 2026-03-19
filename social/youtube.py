"""YouTube scraper - No API key required.

Scrapes YouTube using:
1. YouTube RSS feeds (channel videos)
2. YouTube search (via web scraping)
3. Video metadata extraction

No API key needed for public data.
"""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class YouTubeVideo:
    """A YouTube video."""
    id: str
    title: str
    description: str = ""
    channel: str = ""
    channel_id: str = ""
    published: str = ""
    views: str = ""
    likes: str = ""
    comments: int = 0
    duration: str = ""
    thumbnail: str = ""
    url: str = ""


@dataclass
class YouTubeChannel:
    """YouTube channel info."""
    id: str
    name: str
    subscribers: str = ""
    description: str = ""
    video_count: int = 0
    videos: list[YouTubeVideo] = field(default_factory=list)


class YouTubeScraper:
    """Free YouTube scraper using RSS feeds and web scraping.

    Usage:
        scraper = YouTubeScraper()
        
        # Get channel videos via RSS
        videos = await scraper.get_channel_videos("UC_x5XG1OV2P6uZZ5FSM9Ttw")  # Google Developers
        
        # Search YouTube
        results = await scraper.search("python tutorial", limit=10)
        
        # Get video info
        video = await scraper.get_video_info("dQw4w9WgXcQ")
        
        await scraper.close()
    """

    RSS_URL = "https://www.youtube.com/feeds/videos.xml"
    SEARCH_URL = "https://www.youtube.com/results"
    WATCH_URL = "https://www.youtube.com/watch"

    def __init__(self, timeout: float = 30.0):
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
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        return self._client

    async def get_channel_videos(
        self,
        channel_id: str,
        limit: int = 20,
    ) -> list[YouTubeVideo]:
        """Get videos from channel via RSS feed.

        Args:
            channel_id: YouTube channel ID (e.g., UC_x5XG1OV2P6uZZ5FSM9Ttw)
            limit: Number of videos to return

        RSS feed URL: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
        """
        client = await self._get_client()
        url = f"{self.RSS_URL}?channel_id={channel_id}"

        try:
            response = await client.get(url)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.text)
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "media": "http://search.yahoo.com/mrss/",
                "yt": "http://www.youtube.com/xml/schemas/2015",
            }

            videos = []
            for entry in root.findall("atom:entry", ns)[:limit]:
                video_id = entry.find("yt:videoId", ns)
                title = entry.find("atom:title", ns)
                published = entry.find("atom:published", ns)
                author = entry.find("atom:author/atom:name", ns)
                thumbnail = entry.find("media:group/media:thumbnail", ns)
                description = entry.find("media:group/media:description", ns)

                if video_id is not None:
                    vid = video_id.text or ""
                    videos.append(YouTubeVideo(
                        id=vid,
                        title=title.text if title is not None else "",
                        description=(description.text[:500] if description is not None else ""),
                        channel=author.text if author is not None else "",
                        channel_id=channel_id,
                        published=published.text if published is not None else "",
                        thumbnail=thumbnail.get("url", "") if thumbnail is not None else "",
                        url=f"https://www.youtube.com/watch?v={vid}",
                    ))

            return videos

        except Exception as e:
            logger.error(f"YouTube RSS error: {e}")
            return []

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[YouTubeVideo]:
        """Search YouTube videos.

        Args:
            query: Search query
            limit: Number of results
        """
        client = await self._get_client()
        url = self.SEARCH_URL
        params = {"search_query": query}

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()

            # Extract video data from JavaScript
            videos = []
            html = response.text

            # Find video IDs in the response
            video_ids = re.findall(r'"videoId":"([^"]+)"', html)
            titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}', html)
            channels = re.findall(r'"ownerChannelName":"([^"]+)"', html)

            seen_ids = set()
            for i, vid in enumerate(video_ids):
                if vid in seen_ids or len(videos) >= limit:
                    continue
                seen_ids.add(vid)

                title = titles[i] if i < len(titles) else ""
                channel = channels[i] if i < len(channels) else ""

                videos.append(YouTubeVideo(
                    id=vid,
                    title=title,
                    channel=channel,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    thumbnail=f"https://img.youtube.com/vi/{vid}/default.jpg",
                ))

            return videos

        except Exception as e:
            logger.error(f"YouTube search error: {e}")
            return []

    async def get_video_info(self, video_id: str) -> YouTubeVideo | None:
        """Get detailed video information with full description.

        Args:
            video_id: YouTube video ID
        """
        client = await self._get_client()
        url = f"{self.WATCH_URL}?v={video_id}"

        try:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

            # Extract info from page
            title_match = re.search(r'"title":"([^"]+)"', html)
            channel_match = re.search(r'"ownerChannelName":"([^"]+)"', html)
            views_match = re.search(r'"viewCount":"(\d+)"', html)
            likes_match = re.search(r'"label":"([\d,]+) likes"', html)
            comments_match = re.search(r'"commentCount":"(\d+)"', html)
            duration_match = re.search(r'"lengthSeconds":"(\d+)"', html)
            desc_match = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', html)

            # Parse duration
            duration = ""
            if duration_match:
                secs = int(duration_match.group(1))
                mins, secs = divmod(secs, 60)
                hrs, mins = divmod(mins, 60)
                duration = f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"

            return YouTubeVideo(
                id=video_id,
                title=title_match.group(1) if title_match else "",
                channel=channel_match.group(1) if channel_match else "",
                views=views_match.group(1) if views_match else "",
                likes=likes_match.group(1) if likes_match else "",
                comments=int(comments_match.group(1)) if comments_match else 0,
                duration=duration,
                description=desc_match.group(1)[:2000] if desc_match else "",
                url=f"https://www.youtube.com/watch?v={video_id}",
                thumbnail=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            )

        except Exception as e:
            logger.error(f"Video info error: {e}")
            return None

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


def format_youtube_videos(videos: list[YouTubeVideo], limit: int = 10) -> str:
    """Format YouTube videos as markdown."""
    if not videos:
        return "No videos found."

    lines = []
    for i, video in enumerate(videos[:limit], 1):
        lines.append(f"### {i}. {video.title}")
        lines.append(f"**Channel:** {video.channel}")

        if video.views:
            lines.append(f"**Views:** {video.views}")

        if video.published:
            lines.append(f"**Published:** {video.published[:10]}")

        lines.append(f"**URL:** {video.url}")

        if video.thumbnail:
            lines.append(f"![thumbnail]({video.thumbnail})")

        if video.description:
            preview = video.description[:200].replace("\n", " ")
            lines.append(f"\n{preview}...")

        lines.append("")

    return "\n".join(lines)
