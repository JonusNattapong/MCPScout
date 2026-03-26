"""Core MCPSearch action handlers - Single source of truth for tool logic.

This module contains the core handlers for all MCPSearch actions.
Both server.py (MCP interface) and unified.py (standalone API) use these handlers.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Component Factory Functions
# ============================================================================
# These getters allow lazy initialization of components while keeping
# the handlers independent of how they're initialized

_components = {}


def set_components(**components: Any) -> None:
    """Set component singletons for use by handlers."""
    _components.update(components)


def get_component(name: str) -> Any:
    """Get a component by name."""
    if name not in _components:
        raise RuntimeError(f"Component {name} not initialized. Call set_components() first.")
    return _components[name]


# ============================================================================
# ACTION HANDLERS
# ============================================================================

async def handle_search(args: dict[str, Any]) -> str:
    """Handle search action."""
    query = args.get("query", "")
    max_results = args.get("max_results", args.get("limit", 10))
    
    if not query:
        return "Error: query parameter is required for search action"
    
    try:
        aggregator = get_component("aggregator")
        results = await aggregator.search(query=query, max_results=max_results)
        
        if not results:
            return f"No results found for: {query}"
        
        lines = [f"## Search Results: {query}\n"]
        for i, r in enumerate(results[:max_results], 1):
            lines.append(f"### {i}. {r.get('title', 'No title')}")
            lines.append(f"**URL:** {r.get('url', 'N/A')}")
            if r.get("snippet"):
                lines.append(f"{r['snippet']}\n")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"Error in search: {str(e)}"


async def handle_crawl(args: dict[str, Any]) -> str:
    """Handle crawl action."""
    url = args.get("url", "")
    mode = args.get("mode", "hybrid")
    
    if not url:
        return "Error: url parameter is required for crawl action"
    
    try:
        from crawler.stealth import format_stealth_result
        
        if mode == "stealth":
            multi_crawler = get_component("multi_crawler")
            result = await multi_crawler.crawl_with_fallback(url)
            return format_stealth_result(result)
        elif mode == "deep" or mode == "hybrid":
            hybrid_crawler = get_component("hybrid_crawler")
            result = await hybrid_crawler.crawl(url)
            return str(result)
        else:  # fast mode
            crawler = get_component("crawler")
            result = await crawler.crawl(url)
            return str(result)
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        return f"Error in crawl: {str(e)}"


async def handle_reddit(args: dict[str, Any]) -> str:
    """Handle Reddit action."""
    action_type = args.get("action_type", "search")
    query = args.get("query", "")
    subreddit = args.get("subreddit")
    post_id = args.get("post_id")
    limit = args.get("limit", 10)
    
    try:
        from social.reddit import format_posts_markdown
        reddit = get_component("reddit")
        
        if action_type == "post" and post_id and subreddit:
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
        
        if action_type == "subreddit" and subreddit:
            posts = await reddit.get_subreddit(subreddit=subreddit, limit=limit)
            return format_posts_markdown(posts)
        
        results = await reddit.search(query=query, subreddit=subreddit, limit=limit)
        return format_posts_markdown(results.posts if results else [])
    except Exception as e:
        logger.error(f"Reddit error: {e}")
        return f"Error in Reddit action: {str(e)}"


async def handle_twitter(args: dict[str, Any]) -> str:
    """Handle Twitter action."""
    action_type = args.get("action_type", "search")
    username = args.get("username")
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    try:
        from social.twitter import format_tweets
        twitter = get_component("twitter")
        
        if action_type == "user" and username:
            tweets = await twitter.get_user_tweets(username=username, limit=limit)
            return format_tweets(tweets)
        
        tweets = await twitter.search(query=query, limit=limit)
        return format_tweets(tweets)
    except Exception as e:
        logger.error(f"Twitter error: {e}")
        return f"Error in Twitter action: {str(e)}"


async def handle_youtube(args: dict[str, Any]) -> str:
    """Handle YouTube action."""
    action_type = args.get("action_type", "search")
    video_id = args.get("video_id")
    channel_id = args.get("channel_id")
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    try:
        from social.youtube import format_youtube_videos
        youtube = get_component("youtube")
        
        if action_type == "video" and video_id:
            video = await youtube.get_video_info(video_id=video_id)
            if not video:
                return "Video not found"
            return f"# {video.title}\n**Channel:** {video.channel}\n**Views:** {video.views}\n**Duration:** {video.duration}\n\n{video.description[:1000]}"
        
        if action_type == "channel" and channel_id:
            videos = await youtube.get_channel_videos(channel_id=channel_id, limit=limit)
            return format_youtube_videos(videos)
        
        videos = await youtube.search(query=query, limit=limit)
        return format_youtube_videos(videos)
    except Exception as e:
        logger.error(f"YouTube error: {e}")
        return f"Error in YouTube action: {str(e)}"


async def handle_github(args: dict[str, Any]) -> str:
    """Handle GitHub action."""
    action_type = args.get("action_type", "search")
    query = args.get("query", "")
    owner = args.get("owner")
    repo = args.get("repo")
    username = args.get("username")
    sort = args.get("sort", "stars")
    limit = args.get("limit", 10)
    
    try:
        from social.github import format_github_repos, format_github_user
        github = get_component("github")
        
        if action_type == "readme" and owner and repo:
            readme = await github.get_readme(owner=owner, repo=repo)
            return f"# {owner}/{repo} README\n\n{readme[:5000]}" if readme else "No README found"
        
        if action_type == "repo" and owner and repo:
            r = await github.get_repo(owner=owner, repo=repo)
            if not r:
                return "Repository not found"
            readme = await github.get_readme(owner=owner, repo=repo)
            lines = [f"# {r.full_name}\n", f"**Stars:** {r.stars:,} | **Forks:** {r.forks:,}", f"**Language:** {r.language}"]
            if readme:
                lines.extend(["\n---\n## README\n", readme[:3000]])
            return "\n".join(lines)
        
        if action_type == "user" and username:
            user = await github.get_user(username=username)
            if not user:
                return "User not found"
            repos = await github.get_user_repos(username=username, limit=5)
            result = format_github_user(user)
            if repos:
                result += "\n\n## Recent Repos\n" + format_github_repos(repos)
            return result
        
        repos = await github.search_repos(query=query, sort=sort, limit=limit)
        return format_github_repos(repos)
    except Exception as e:
        logger.error(f"GitHub error: {e}")
        return f"Error in GitHub action: {str(e)}"


async def handle_research(args: dict[str, Any]) -> str:
    """Handle research action - comprehensive multi-source research."""
    topic = args.get("topic", args.get("query", ""))
    depth = args.get("depth", "medium")
    include_social = args.get("include_social", True)
    include_summary = args.get("include_summary", True)
    max_sources = args.get("max_sources", 5)
    export_format = args.get("export_format", "markdown")
    
    if not topic:
        return "Error: topic parameter is required for research action"
    
    try:
        from agents.research_agent import get_research_agent
        agent = get_research_agent()
        
        result = await agent.investigate(
            topic=topic,
            search_depth=depth,
            include_social=include_social,
            include_summary=include_summary,
            max_sources=max_sources,
            export_format=export_format,
        )
        
        return result
    except Exception as e:
        logger.error(f"Research error: {e}")
        return f"Error in research: {str(e)}"


# ============================================================================
# ACTION ROUTER
# ============================================================================

ACTION_HANDLERS = {
    "search": handle_search,
    "crawl": handle_crawl,
    "reddit": handle_reddit,
    "twitter": handle_twitter,
    "youtube": handle_youtube,
    "github": handle_github,
    "research": handle_research,
}


async def route_action(action: str, **kwargs: Any) -> str:
    """Route an action to the appropriate handler."""
    handler = ACTION_HANDLERS.get(action)
    if not handler:
        return f"Unknown action: {action}\nAvailable: {', '.join(ACTION_HANDLERS.keys())}"
    
    try:
        return await handler(kwargs)
    except Exception as e:
        logger.error(f"Error in action {action}: {e}")
        return f"Error in {action}: {str(e)}"
