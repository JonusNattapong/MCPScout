"""Unified mcpsearch Tool - Single tool that orchestrates all operations.

This module provides a single unified interface that can:
1. Route to the appropriate sub-tool based on action
2. Chain multiple tools together for complex workflows
3. Auto-select the best tool based on context

All action handlers are delegated to mcp_server.handlers for reuse across
both the standalone API (this module) and the MCP server interface.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp_server import handlers

# Initialize all components ONCE for reuse
def _initialize_components() -> None:
    """Initialize all components for handlers."""
    from crawler.engine import CrawlerEngine
    from crawler.hybrid import HybridCrawler
    from crawler.stealth import MultiBrowserCrawler
    from search.aggregator import SearchAggregator
    from social.reddit import RedditScraper
    from social.twitter import TwitterScraper
    from social.youtube import YouTubeScraper
    from social.github import GitHubScraper

    handlers.set_components(
        crawler=CrawlerEngine(),
        hybrid_crawler=HybridCrawler(),
        multi_crawler=MultiBrowserCrawler(),
        aggregator=SearchAggregator(),
        reddit=RedditScraper(),
        twitter=TwitterScraper(),
        youtube=YouTubeScraper(),
        github=GitHubScraper(),
    )


# Lazy initialization on first use
_initialized = False


def _ensure_initialized() -> None:
    """Ensure components are initialized."""
    global _initialized
    if not _initialized:
        _initialize_components()
        _initialized = True

# =============================================================================
# UNIFIED TOOL
# =============================================================================

async def mcpsearch(
    action: str,
    **kwargs: Any,
) -> str:
    """Execute an mcpsearch action.

    Actions:
    - search: Web search (query, sources, max_results)
    - crawl: Crawl URL (url, mode: hybrid/stealth)
    - reddit: Reddit (query, subreddit, post_id, action_type: search/subreddit/post)
    - twitter: Twitter/X (query, username, action_type: search/user)
    - youtube: YouTube (query, video_id, channel_id, action_type: search/video/channel)
    - github: GitHub (query, owner, repo, username, action_type: search/repo/user/readme)
    """
    _ensure_initialized()
    return await handlers.route_action(action, **kwargs)


# =============================================================================
# MULTI-ACTION ORCHESTRATOR
# =============================================================================

async def mcpsearch_multi(
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
    _ensure_initialized()
    
    tasks = []
    for action_config in actions:
        # Make a copy to avoid modifying the original
        config = action_config.copy()
        action = config.pop("action")
        tasks.append(mcpsearch(action, **config))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output_parts = []
    for i, result in enumerate(results):
        action_name = actions[i].get("action", f"Action {i+1}")
        if isinstance(result, Exception):
            output_parts.append(f"## {action_name} Error\n{str(result)}\n")
        else:
            output_parts.append(f"## {action_name}\n{result}")

    return "\n---\n".join(output_parts)
