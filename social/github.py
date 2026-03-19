"""GitHub scraper - No API key required (public data).

Uses GitHub's public API endpoints (unauthenticated):
- Search repositories
- Get user info
- Get repo info
- Get issues/PRs

Rate limit: 60 requests/hour without token (fine for research).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GitHubRepo:
    """A GitHub repository."""
    id: int
    name: str
    full_name: str
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    open_issues: int = 0
    url: str = ""
    clone_url: str = ""
    topics: list[str] = field(default_factory=list)
    license: str = ""
    created_at: str = ""
    updated_at: str = ""
    owner: str = ""


@dataclass
class GitHubUser:
    """GitHub user profile."""
    login: str
    id: int
    name: str = ""
    bio: str = ""
    company: str = ""
    location: str = ""
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    avatar_url: str = ""
    url: str = ""


@dataclass
class GitHubIssue:
    """A GitHub issue or PR."""
    id: int
    number: int
    title: str
    body: str = ""
    state: str = ""
    author: str = ""
    labels: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    comments: int = 0
    url: str = ""
    is_pull_request: bool = False


class GitHubScraper:
    """Free GitHub scraper using public API.

    Usage:
        scraper = GitHubScraper()
        
        # Search repositories
        repos = await scraper.search_repos("machine learning", limit=10)
        
        # Get user info
        user = await scraper.get_user("torvalds")
        
        # Get repo info
        repo = await scraper.get_repo("python", "cpython")
        
        # Get issues
        issues = await scraper.get_issues("pytorch", "pytorch", limit=10)
        
        await scraper.close()
    """

    API_URL = "https://api.github.com"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "MCPScout/1.0.0",
                },
            )
        return self._client

    async def search_repos(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        limit: int = 10,
    ) -> list[GitHubRepo]:
        """Search GitHub repositories.

        Args:
            query: Search query
            sort: stars, forks, updated
            order: desc, asc
            limit: Number of results
        """
        client = await self._get_client()
        url = f"{self.API_URL}/search/repositories"

        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(limit, 100),
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            repos = []
            for item in data.get("items", [])[:limit]:
                repos.append(self._parse_repo(item))

            return repos

        except Exception as e:
            logger.error(f"GitHub search error: {e}")
            return []

    async def get_user(self, username: str) -> GitHubUser | None:
        """Get GitHub user profile."""
        client = await self._get_client()
        url = f"{self.API_URL}/users/{username}"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            return GitHubUser(
                login=data.get("login", ""),
                id=data.get("id", 0),
                name=data.get("name", ""),
                bio=data.get("bio", ""),
                company=data.get("company", ""),
                location=data.get("location", ""),
                public_repos=data.get("public_repos", 0),
                followers=data.get("followers", 0),
                following=data.get("following", 0),
                avatar_url=data.get("avatar_url", ""),
                url=data.get("html_url", ""),
            )

        except Exception as e:
            logger.error(f"GitHub user error: {e}")
            return None

    async def get_repo(self, owner: str, repo: str) -> GitHubRepo | None:
        """Get repository info."""
        client = await self._get_client()
        url = f"{self.API_URL}/repos/{owner}/{repo}"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return self._parse_repo(data)

        except Exception as e:
            logger.error(f"GitHub repo error: {e}")
            return None

    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        limit: int = 10,
    ) -> list[GitHubIssue]:
        """Get issues for a repository."""
        client = await self._get_client()
        url = f"{self.API_URL}/repos/{owner}/{repo}/issues"

        params = {
            "state": state,
            "per_page": min(limit, 100),
            "sort": "updated",
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            issues = []
            for item in data[:limit]:
                issues.append(GitHubIssue(
                    id=item.get("id", 0),
                    number=item.get("number", 0),
                    title=item.get("title", ""),
                    body=(item.get("body", "") or "")[:500],
                    state=item.get("state", ""),
                    author=item.get("user", {}).get("login", ""),
                    labels=[l.get("name", "") for l in item.get("labels", [])],
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                    comments=item.get("comments", 0),
                    url=item.get("html_url", ""),
                    is_pull_request="pull_request" in item,
                ))

            return issues

        except Exception as e:
            logger.error(f"GitHub issues error: {e}")
            return []

    async def get_readme(
        self,
        owner: str,
        repo: str,
    ) -> str:
        """Get repository README content."""
        client = await self._get_client()
        url = f"{self.API_URL}/repos/{owner}/{repo}/readme"

        try:
            response = await client.get(url, headers={"Accept": "application/vnd.github.v3.raw"})
            response.raise_for_status()
            return response.text[:5000]  # Limit size

        except Exception as e:
            logger.error(f"README error: {e}")
            return ""

    async def get_user_repos(
        self,
        username: str,
        sort: str = "updated",
        limit: int = 10,
    ) -> list[GitHubRepo]:
        """Get user's repositories."""
        client = await self._get_client()
        url = f"{self.API_URL}/users/{username}/repos"

        params = {
            "sort": sort,
            "per_page": min(limit, 100),
        }

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            return [self._parse_repo(item) for item in data[:limit]]

        except Exception as e:
            logger.error(f"GitHub user repos error: {e}")
            return []

    def _parse_repo(self, data: dict) -> GitHubRepo:
        """Parse repo data."""
        return GitHubRepo(
            id=data.get("id", 0),
            name=data.get("name", ""),
            full_name=data.get("full_name", ""),
            description=data.get("description", "") or "",
            language=data.get("language", "") or "",
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            watchers=data.get("watchers_count", 0),
            open_issues=data.get("open_issues_count", 0),
            url=data.get("html_url", ""),
            clone_url=data.get("clone_url", ""),
            topics=data.get("topics", []),
            license=data.get("license", {}).get("spdx_id", "") if data.get("license") else "",
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            owner=data.get("owner", {}).get("login", ""),
        )

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()


def format_github_repos(repos: list[GitHubRepo], limit: int = 10) -> str:
    """Format repos as markdown."""
    if not repos:
        return "No repositories found."

    lines = []
    for i, repo in enumerate(repos[:limit], 1):
        lines.append(f"### {i}. [{repo.full_name}]({repo.url})")
        lines.append(f"⭐ {repo.stars:,} | 🍴 {repo.forks:,} | 💻 {repo.language or 'N/A'}")

        if repo.description:
            lines.append(f"\n{repo.description[:200]}")

        if repo.topics:
            lines.append(f"\n**Topics:** {', '.join(repo.topics[:5])}")

        if repo.license:
            lines.append(f"**License:** {repo.license}")

        lines.append("")

    return "\n".join(lines)


def format_github_user(user: GitHubUser) -> str:
    """Format user profile as markdown."""
    lines = [
        f"# {user.name or user.login}\n",
        f"**Username:** @{user.login}",
        f"**Profile:** {user.url}",
        f"**Repos:** {user.public_repos} | **Followers:** {user.followers:,} | **Following:** {user.following:,}",
    ]

    if user.bio:
        lines.extend(["", user.bio])

    if user.company:
        lines.append(f"\n**Company:** {user.company}")

    if user.location:
        lines.append(f"**Location:** {user.location}")

    return "\n".join(lines)
