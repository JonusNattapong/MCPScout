"""Unified Scout Tool - Single tool that orchestrates all operations.

This module provides a single unified interface that can:
1. Route to the appropriate sub-tool based on action
2. Chain multiple tools together for complex workflows
3. Auto-select the best tool based on context
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

# Import all scrapers
from crawler.engine import CrawlerEngine
from crawler.hybrid import HybridCrawler
from crawler.stealth import MultiBrowserCrawler, format_stealth_result
from search.aggregator import SearchAggregator
from social.reddit import RedditScraper, format_posts_markdown
from social.twitter import TwitterScraper, format_tweets
from social.youtube import YouTubeScraper, format_youtube_videos
from social.github import GitHubScraper, format_github_repos, format_github_user

# Initialize all components
crawler = CrawlerEngine()
hybrid = HybridCrawler()
multi_crawler = MultiBrowserCrawler()
aggregator = SearchAggregator()
reddit = RedditScraper()
twitter = TwitterScraper()
youtube = YouTubeScraper()
github = GitHubScraper()


# =============================================================================
# ACTION HANDLERS
# =============================================================================

async def action_search(args: dict) -> str:
    """Handle search actions."""
    query = args.get("query", "")
    sources = args.get("sources")
    max_results = args.get("max_results", 10)

    results = await aggregator.search(query=query, max_results=max_results, sources=sources)
    if not results:
        return f"No results for: {query}"

    lines = [f"## Search Results: {query}\n"]
    for i, r in enumerate(results[:max_results], 1):
        lines.append(f"### {i}. {r.get('title', 'No title')}")
        lines.append(f"**URL:** {r.get('url', 'N/A')}")
        if r.get("snippet"):
            lines.append(f"{r['snippet']}\n")
    return "\n".join(lines)


async def action_crawl(args: dict) -> str:
    """Handle crawl actions."""
    url = args.get("url", "")
    mode = args.get("mode", "hybrid")

    if mode == "stealth":
        result = await multi_crawler.crawl_with_fallback(url)
        return format_stealth_result(result)
    elif mode == "hybrid":
        result = await hybrid.crawl(url)
        return result
    else:
        return await crawler.crawl(url)


async def action_reddit(args: dict) -> str:
    """Handle Reddit actions."""
    action = args.get("action_type", "search")
    query = args.get("query", "")
    subreddit = args.get("subreddit")
    post_id = args.get("post_id")

    if action == "post" and post_id and subreddit:
        result = await reddit.get_post_content(post_id=post_id, subreddit=subreddit)
        if not result.get("post"):
            return "Post not found"
        post = result["post"]
        lines = [f"# {post.title}\n", f"**r/{post.subreddit}** | ⬆️ {post.score}\n"]
        lines.append(post.selftext or "[No content]")
        if result.get("comments"):
            lines.append("\n## Top Comments\n")
            for i, c in enumerate(result["comments"][:5], 1):
                lines.append(f"**{i}. u/{c.author}**: {c.body[:200]}\n")
        return "\n".join(lines)

    if action == "subreddit" and subreddit:
        posts = await reddit.get_subreddit(subreddit=subreddit, limit=args.get("limit", 10))
        return format_posts_markdown(posts)

    results = await reddit.search(query=query, subreddit=subreddit, limit=args.get("limit", 10))
    return format_posts_markdown(results.posts)


async def action_twitter(args: dict) -> str:
    """Handle Twitter actions."""
    action = args.get("action_type", "search")
    username = args.get("username")
    query = args.get("query", "")

    if action == "user" and username:
        tweets = await twitter.get_user_tweets(username=username, limit=args.get("limit", 10))
        return format_tweets(tweets)

    tweets = await twitter.search(query=query, limit=args.get("limit", 10))
    return format_tweets(tweets)


async def action_youtube(args: dict) -> str:
    """Handle YouTube actions."""
    action = args.get("action_type", "search")
    video_id = args.get("video_id")
    channel_id = args.get("channel_id")
    query = args.get("query", "")

    if action == "video" and video_id:
        video = await youtube.get_video_info(video_id=video_id)
        if not video:
            return "Video not found"
        return f"# {video.title}\n**Channel:** {video.channel}\n**Views:** {video.views}\n**Duration:** {video.duration}\n\n{video.description[:1000]}"

    if action == "channel" and channel_id:
        videos = await youtube.get_channel_videos(channel_id=channel_id, limit=args.get("limit", 10))
        return format_youtube_videos(videos)

    videos = await youtube.search(query=query, limit=args.get("limit", 10))
    return format_youtube_videos(videos)


async def action_github(args: dict) -> str:
    """Handle GitHub actions."""
    action = args.get("action_type", "search")
    query = args.get("query", "")
    owner = args.get("owner")
    repo = args.get("repo")
    username = args.get("username")

    if action == "readme" and owner and repo:
        readme = await github.get_readme(owner=owner, repo=repo)
        return f"# {owner}/{repo} README\n\n{readme[:5000]}" if readme else "No README found"

    if action == "repo" and owner and repo:
        r = await github.get_repo(owner=owner, repo=repo)
        if not r:
            return "Repository not found"
        readme = await github.get_readme(owner=owner, repo=repo)
        lines = [f"# {r.full_name}\n", f"**Stars:** {r.stars:,} | **Forks:** {r.forks:,}", f"**Language:** {r.language}"]
        if readme:
            lines.extend(["\n---\n## README\n", readme[:3000]])
        return "\n".join(lines)

    if action == "user" and username:
        user = await github.get_user(username=username)
        if not user:
            return "User not found"
        repos = await github.get_user_repos(username=username, limit=5)
        result = format_github_user(user)
        if repos:
            result += "\n\n## Recent Repos\n" + format_github_repos(repos)
        return result

    repos = await github.search_repos(query=query, limit=args.get("limit", 10))
    return format_github_repos(repos)


# =============================================================================
# UNIFIED TOOL
# =============================================================================

# Action routing map
ACTION_HANDLERS = {
    "search": action_search,
    "crawl": action_crawl,
    "reddit": action_reddit,
    "twitter": action_twitter,
    "youtube": action_youtube,
    "github": action_github,
}


async def scout(
    action: str,
    **kwargs: Any,
) -> str:
    """Execute a scouting action.

    Actions:
    - search: Web search (query, sources, max_results)
    - crawl: Crawl URL (url, mode: hybrid/stealth)
    - reddit: Reddit (query, subreddit, post_id, action_type: search/subreddit/post)
    - twitter: Twitter/X (query, username, action_type: search/user)
    - youtube: YouTube (query, video_id, channel_id, action_type: search/video/channel)
    - github: GitHub (query, owner, repo, username, action_type: search/repo/user/readme)
    """
    handler = ACTION_HANDLERS.get(action)
    if not handler:
        return f"Unknown action: {action}. Available: {', '.join(ACTION_HANDLERS.keys())}"

    return await handler(kwargs)


# =============================================================================
# MULTI-ACTION ORCHESTRATOR
# =============================================================================

async def scout_multi(
    actions: list[dict[str, Any]],
) -> str:
    """Execute multiple actions in parallel and combine results.

    Example:
        actions = [
            {"action": "search", "query": "AI news"},
            {"action": "reddit", "query": "artificialintelligence"},
            {"action": "twitter", "query": "AI news"},
        ]
    """
    tasks = []
    for action_config in actions:
        action = action_config.pop("action")
        tasks.append(scout(action, **action_config))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output_parts = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            output_parts.append(f"## Action {i+1} Error\n{str(result)}\n")
        else:
            output_parts.append(result)

    return "\n---\n".join(output_parts)
