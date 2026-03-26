"""Reddit scraper - Free, no API key required.

Uses Reddit's public JSON endpoints (like old Reddit) to scrape:
- Subreddit posts
- User posts/comments
- Search results
- Post comments

No authentication required for public data.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urlencode

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class RedditPost:
    """A Reddit post."""
    id: str
    title: str
    selftext: str = ""
    author: str = ""
    subreddit: str = ""
    score: int = 0
    upvote_ratio: float = 0.0
    num_comments: int = 0
    url: str = ""
    permalink: str = ""
    created_utc: float = 0.0
    is_self: bool = True
    link_flair_text: str = ""
    awards: int = 0


@dataclass
class RedditComment:
    """A Reddit comment."""
    id: str
    author: str
    body: str
    score: int = 0
    created_utc: float = 0.0
    permalink: str = ""
    replies: list[RedditComment] = field(default_factory=list)


@dataclass
class RedditSearchResult:
    """Search results from Reddit."""
    query: str
    posts: list[RedditPost] = field(default_factory=list)
    after: str = ""
    before: str = ""


class RedditScraper:
    """Free Reddit scraper using public JSON endpoints.

    Usage:
        scraper = RedditScraper()
        
        # Search Reddit
        results = await scraper.search("python programming", limit=10)
        
        # Get subreddit posts
        posts = await scraper.get_subreddit("python", sort="hot", limit=25)
        
        # Get user posts
        posts = await scraper.get_user_posts("spez", limit=10)
        
        # Get post comments
        comments = await scraper.get_comments("abc123", subreddit="python")
    """

    BASE_URL = "https://www.reddit.com"
    JSON_URL = "https://www.reddit.com"

    def __init__(
        self,
        user_agent: str = "MCPSearch/1.0.0 (Research Bot)",
        timeout: float = 30.0,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                },
            )
        return self._client

    async def search(
        self,
        query: str,
        subreddit: str | None = None,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = 25,
    ) -> RedditSearchResult:
        """Search Reddit for posts.

        Args:
            query: Search query
            subreddit: Limit to specific subreddit (optional)
            sort: relevance, hot, top, new, comments
            time_filter: hour, day, week, month, year, all
            limit: Number of results (max 100)
        """
        client = await self._get_client()

        # Build search URL
        if subreddit:
            url = f"{self.JSON_URL}/r/{subreddit}/search.json"
        else:
            url = f"{self.JSON_URL}/search.json"

        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
            "restrict_sr": "1" if subreddit else "0",
            "raw_json": "1",
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            posts = []
            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                posts.append(self._parse_post(post_data))

            return RedditSearchResult(
                query=query,
                posts=posts,
                after=data.get("data", {}).get("after", ""),
                before=data.get("data", {}).get("before", ""),
            )

        except Exception as e:
            logger.error(f"Reddit search error: {e}")
            return RedditSearchResult(query=query)

    async def get_subreddit(
        self,
        subreddit: str,
        sort: str = "hot",
        time_filter: str = "day",
        limit: int = 25,
    ) -> list[RedditPost]:
        """Get posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/)
            sort: hot, new, top, rising
            time_filter: hour, day, week, month, year, all
            limit: Number of posts (max 100)
        """
        client = await self._get_client()
        url = f"{self.JSON_URL}/r/{subreddit}/{sort}.json"

        params = {
            "limit": min(limit, 100),
            "t": time_filter,
            "raw_json": "1",
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            posts = []
            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                if not post_data.get("stickied"):  # Skip stickied posts
                    posts.append(self._parse_post(post_data))

            return posts

        except Exception as e:
            logger.error(f"Subreddit fetch error: {e}")
            return []

    async def get_user_posts(
        self,
        username: str,
        sort: str = "new",
        limit: int = 25,
    ) -> list[RedditPost]:
        """Get posts from a specific user."""
        client = await self._get_client()
        url = f"{self.JSON_URL}/user/{username}/submitted.json"

        params = {
            "limit": min(limit, 100),
            "sort": sort,
            "raw_json": "1",
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            posts = []
            for child in data.get("data", {}).get("children", []):
                post_data = child.get("data", {})
                posts.append(self._parse_post(post_data))

            return posts

        except Exception as e:
            logger.error(f"User posts fetch error: {e}")
            return []

    async def get_post_content(
        self,
        post_id: str,
        subreddit: str,
    ) -> dict:
        """Get full post content with top comments."""
        client = await self._get_client()
        url = f"{self.JSON_URL}/r/{subreddit}/comments/{post_id}.json"

        try:
            response = await client.get(url, params={"raw_json": "1"})
            response.raise_for_status()
            data = response.json()

            result = {"post": None, "comments": []}

            # Get post data
            if data and len(data) > 0:
                post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})
                result["post"] = self._parse_post(post_data)

            # Get comments
            if len(data) > 1:
                comments_data = data[1].get("data", {}).get("children", [])
                result["comments"] = self._parse_comments(comments_data)[:10]

            return result

        except Exception as e:
            logger.error(f"Post content error: {e}")
            return {"post": None, "comments": []}

    async def get_comments(
        self,
        post_id: str,
        subreddit: str,
        sort: str = "best",
        limit: int = 100,
    ) -> list[RedditComment]:
        """Get comments for a specific post."""
        client = await self._get_client()
        url = f"{self.JSON_URL}/r/{subreddit}/comments/{post_id}.json"

        params = {
            "sort": sort,
            "limit": min(limit, 100),
            "raw_json": "1",
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Comments are in the second element
            if len(data) > 1:
                comments_data = data[1].get("data", {}).get("children", [])
                return self._parse_comments(comments_data)

            return []

        except Exception as e:
            logger.error(f"Comments fetch error: {e}")
            return []

    def _parse_post(self, data: dict) -> RedditPost:
        """Parse post data into RedditPost."""
        return RedditPost(
            id=data.get("id", ""),
            title=data.get("title", ""),
            selftext=data.get("selftext", "")[:2000],  # Limit length
            author=data.get("author", "[deleted]"),
            subreddit=data.get("subreddit", ""),
            score=data.get("score", 0),
            upvote_ratio=data.get("upvote_ratio", 0.0),
            num_comments=data.get("num_comments", 0),
            url=data.get("url", ""),
            permalink=f"https://reddit.com{data.get('permalink', '')}",
            created_utc=data.get("created_utc", 0.0),
            is_self=data.get("is_self", True),
            link_flair_text=data.get("link_flair_text", ""),
            awards=data.get("total_awards_received", 0),
        )

    def _parse_comments(self, children: list[dict]) -> list[RedditComment]:
        """Parse comment data recursively."""
        comments = []
        for child in children:
            if child.get("kind") != "t1":
                continue

            data = child.get("data", {})
            comment = RedditComment(
                id=data.get("id", ""),
                author=data.get("author", "[deleted]"),
                body=data.get("body", "")[:1000],
                score=data.get("score", 0),
                created_utc=data.get("created_utc", 0.0),
                permalink=f"https://reddit.com{data.get('permalink', '')}",
            )

            # Parse replies
            replies_data = data.get("replies", "")
            if isinstance(replies_data, dict):
                reply_children = replies_data.get("data", {}).get("children", [])
                comment.replies = self._parse_comments(reply_children)

            comments.append(comment)

        return comments

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


def format_posts_markdown(posts: list[RedditPost], limit: int = 10) -> str:
    """Format Reddit posts as markdown."""
    if not posts:
        return "No posts found."

    lines = []
    for i, post in enumerate(posts[:limit], 1):
        lines.append(f"### {i}. {post.title}")
        lines.append(f"**r/{post.subreddit}** | u/{post.author} | ⬆️ {post.score} | 💬 {post.num_comments}")
        lines.append(f"**URL:** {post.permalink}")

        if post.selftext:
            preview = post.selftext[:300] + "..." if len(post.selftext) > 300 else post.selftext
            lines.append(f"\n{preview}")

        lines.append("")

    return "\n".join(lines)
