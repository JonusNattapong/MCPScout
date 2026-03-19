"""MCPScout Server - AI-powered multi-source intelligence platform."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from crawler.engine import CrawlerEngine
from crawler.smart_crawler import SmartCrawler
from crawler.extractor import ContentExtractor
from crawler.hybrid import HybridCrawler, RenderMethod
from crawler.stealth import StealthBrowser, MultiBrowserCrawler, format_stealth_result
from search.aggregator import SearchAggregator
from summarizer.ai_summarizer import AISummarizer
from social.reddit import RedditScraper, format_posts_markdown
from social.twitter import TwitterScraper, format_tweets
from social.youtube import YouTubeScraper, format_youtube_videos
from social.github import GitHubScraper, format_github_repos, format_github_user

# Initialize FastMCP server
mcp = FastMCP("mcpscout")

# Initialize components
aggregator = SearchAggregator()
summarizer = AISummarizer()
crawler = CrawlerEngine()
smart_crawler = SmartCrawler()
extractor = ContentExtractor()
hybrid_crawler = HybridCrawler()
reddit_scraper = RedditScraper()
twitter_scraper = TwitterScraper()
youtube_scraper = YouTubeScraper()
github_scraper = GitHubScraper()
stealth_browser = StealthBrowser()
multi_crawler = MultiBrowserCrawler()


# =============================================================================
# TOOLS
# =============================================================================


@mcp.tool()
async def web_search(
    query: Annotated[str, "Search query to execute"],
    max_results: Annotated[int, "Maximum number of results"] = 10,
    sources: Annotated[list[str] | None, "Search engines to use"] = None,
) -> str:
    """Search multiple websites in parallel and return results."""
    results = await aggregator.search(query=query, max_results=max_results, sources=sources)
    if not results:
        return f"No results found for: {query}"

    lines = [f"## Search Results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r.get('title', 'No title')}")
        lines.append(f"**URL:** {r.get('url', 'N/A')}")
        if r.get("snippet"):
            lines.append(f"{r['snippet']}")
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
async def crawl_url(
    url: Annotated[str, "URL to crawl"],
    extract_mode: Annotated[str, "Extraction mode: text, markdown, or structured"] = "markdown",
) -> str:
    """Crawl a specific URL and extract its content."""
    return await crawler.crawl(url=url, extract_mode=extract_mode)  # type: ignore


@mcp.tool()
async def extract_content(
    url: Annotated[str, "URL to extract content from"],
    include_tables: Annotated[bool, "Extract tables as markdown"] = True,
    include_code: Annotated[bool, "Extract code blocks"] = True,
    include_images: Annotated[bool, "Extract image metadata"] = True,
) -> str:
    """Advanced content extraction with tables, code blocks, images, and structured data.

    Use this tool when you need to extract specific content types from a webpage:
    - Tables: Financial data, comparison tables, data grids
    - Code: Programming examples, snippets, tutorials
    - Images: Image galleries, diagrams, infographics
    - Structured data: Product info, recipes, events (from JSON-LD)
    """
    import httpx

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url, headers={"User-Agent": "MCPSpider/0.1.0"})
            response.raise_for_status()

            content = extractor.extract(response.text, base_url=url)

            lines = [
                f"# {content.title}\n",
                f"**URL:** {url}",
                f"**Words:** {content.word_count}",
                f"**Reading time:** {content.reading_time_minutes:.1f} min\n",
            ]

            # Metadata
            if content.metadata:
                lines.append("## Metadata\n")
                for key, value in content.metadata.items():
                    if value:
                        lines.append(f"- **{key}:** {value}")
                lines.append("")

            # Tables
            if include_tables and content.tables:
                lines.append(f"## Tables ({len(content.tables)})\n")
                for i, table in enumerate(content.tables, 1):
                    lines.append(f"### Table {i}")
                    lines.append(table.to_markdown())
                    lines.append("")

            # Code blocks
            if include_code and content.code_blocks:
                lines.append(f"## Code Blocks ({len(content.code_blocks)})\n")
                for i, code in enumerate(content.code_blocks, 1):
                    lang = code.language or "code"
                    lines.append(f"### Code Block {i} ({lang})")
                    lines.append(f"```{lang}")
                    lines.append(code.code[:1000])  # Limit length
                    lines.append("```\n")

            # Images
            if include_images and content.images:
                lines.append(f"## Images ({len(content.images)})\n")
                for i, img in enumerate(content.images[:20], 1):  # Limit to 20
                    lines.append(f"{i}. {img.alt or 'No alt'} - `{img.src[:80]}`")
                lines.append("")

            # Main content preview
            lines.append("## Content Preview\n")
            preview = content.text[:2000]
            if len(content.text) > 2000:
                preview += "\n..."
            lines.append(preview)

            return "\n".join(lines)

    except Exception as e:
        return f"Error extracting content from {url}: {str(e)}"


@mcp.tool()
async def hybrid_crawl(
    url: Annotated[str, "URL to crawl with smart routing"],
    force_browser: Annotated[bool, "Force Playwright browser rendering"] = False,
    wait_for_selector: Annotated[str | None, "CSS selector to wait for (enables browser)"] = None,
) -> str:
    """Hybrid crawling with auto-stealth fallback.

    Smart routing with automatic anti-bot bypass:
    1. Tries httpx first (fast, ~50ms)
    2. Auto-detects JS-heavy pages (React, Vue, Angular)
    3. Falls back to Playwright for JS rendering
    4. If blocked by Cloudflare/Akamai/etc → auto-switches to Camoufox stealth

    You don't need to call stealth separately - it activates automatically!
    """
    result = await multi_crawler.crawl_with_fallback(url)
    return format_stealth_result(result)


@mcp.tool()
async def crawl_recursive(
    url: Annotated[str, "Starting URL"],
    max_depth: Annotated[int, "How deep to follow links (1-5)"] = 3,
    max_pages: Annotated[int, "Maximum pages to crawl (1-100)"] = 20,
    same_domain_only: Annotated[bool, "Only crawl same domain"] = True,
) -> str:
    """Recursively crawl a website following all links."""
    result = await crawler.crawl_recursive(
        url=url, max_depth=max_depth, max_pages=max_pages, same_domain_only=same_domain_only,
    )
    lines = [f"# Deep Crawl: {result.seed_url}\n", f"Pages: {result.pages_crawled} | Links: {result.total_links_found}\n---\n"]
    for i, page in enumerate(result.results[:15], 1):
        if not page.error:
            lines.append(f"### {i}. {page.title or 'No title'}")
            lines.append(f"**URL:** {page.url} (depth {page.depth})")
            lines.append(f"{page.content[:200]}...\n")
    return "\n".join(lines)


@mcp.tool()
async def smart_search(
    query: Annotated[str, "Search query for focused deep research"],
    max_depth: Annotated[int, "Crawl depth (1-3)"] = 2,
    max_pages: Annotated[int, "Maximum pages (1-50)"] = 15,
) -> str:
    """Smart search with heuristic link relevance filtering.

    Unlike crawl_recursive which follows ALL links, smart_search evaluates
    which links are relevant to your query before crawling them.

    Scoring is based on:
    - Query words in URL/title/anchor text
    - High-value domains (wiki, docs, tutorial)
    - Penalizes low-value URLs (login, cart, ads)

    100% free, no API required.
    """
    # Search first
    search_results = await aggregator.search(query=query, max_results=5)
    if not search_results:
        return f"No results found for: {query}"

    # Smart crawl from search results
    urls = [r["url"] for r in search_results[:3]]
    result = await smart_crawler.smart_crawl(
        query=query,
        urls=urls,
        max_depth=max_depth,
        max_pages=max_pages,
    )

    lines = [
        f"# Smart Search: {query}\n",
        f"**Pages Crawled:** {result.pages_crawled}",
        f"**Links Evaluated:** {result.links_evaluated}",
        f"**Links Approved:** {result.links_approved}",
        f"**Links Skipped:** {result.pages_skipped}\n",
        "---\n",
        "## Top Relevant Links Found\n",
    ]

    for i, link in enumerate(result.top_links[:10], 1):
        lines.append(f"{i}. **{link.title or link.url}** (score: {link.relevance_score:.2f})")
        lines.append(f"   {link.url}")
        lines.append(f"   *{link.reason}*\n")

    lines.append("\n---\n## Crawled Content\n")

    for i, page in enumerate(result.results[:10], 1):
        if not page.error:
            lines.append(f"### {i}. {page.title or 'No title'}")
            lines.append(f"**URL:** {page.url}")
            lines.append(f"{page.content[:300]}...\n")

    return "\n".join(lines)


@mcp.tool()
async def deep_search(
    query: Annotated[str, "Search query"],
    max_depth: Annotated[int, "Crawl depth"] = 2,
    max_pages: Annotated[int, "Max pages"] = 15,
) -> str:
    """Deep search: search then recursively crawl top results (follows all links)."""
    result = await crawler.deep_search(
        query=query, search_engine=aggregator, max_depth=max_depth, max_pages=max_pages,
    )
    if not result.results:
        return f"No results for: {query}"

    lines = [f"# Deep Search: {query}\n", f"Pages: {result.pages_crawled}\n---\n"]
    for i, page in enumerate(result.results[:15], 1):
        if not page.error:
            lines.append(f"### {i}. {page.title or 'No title'}")
            lines.append(f"**URL:** {page.url}")
            lines.append(f"{page.content[:200]}...\n")
    return "\n".join(lines)


@mcp.tool()
async def search_and_summarize(
    query: Annotated[str, "Search query"],
    max_sources: Annotated[int, "Sources to analyze"] = 5,
    summary_length: Annotated[str, "brief/detailed/comprehensive"] = "detailed",
) -> str:
    """Search, crawl, and AI-summarize (Perplexity-style)."""
    results = await aggregator.search(query=query, max_results=max_sources)
    if not results:
        return f"No results for: {query}"

    urls = [r["url"] for r in results[:max_sources]]
    crawled = await crawler.crawl_multiple(urls=urls)
    summary = await summarizer.summarize(query=query, sources=crawled, length=summary_length)

    lines = [f"# {query}\n", summary, "\n---\n## Sources\n"]
    for i, s in enumerate(crawled[:max_sources], 1):
        lines.append(f"{i}. {s.get('title', s.get('url', 'Unknown'))}")
    return "\n".join(lines)


@mcp.tool()
async def search_reddit(
    query: Annotated[str, "Search query for Reddit"],
    subreddit: Annotated[str | None, "Limit to specific subreddit (e.g., 'python')"] = None,
    sort: Annotated[str, "Sort by: relevance, hot, top, new"] = "relevance",
    limit: Annotated[int, "Number of results (1-50)"] = 10,
) -> str:
    """Search Reddit for posts (free, no API key required).

    Uses Reddit's public JSON endpoints to search for posts.
    Can search all of Reddit or limit to specific subreddits.
    """
    results = await reddit_scraper.search(
        query=query,
        subreddit=subreddit,
        sort=sort,
        limit=limit,
    )
    if not results.posts:
        return f"No Reddit results for: {query}"
    return format_posts_markdown(results.posts, limit=limit)


@mcp.tool()
async def get_subreddit(
    subreddit: Annotated[str, "Subreddit name (without r/)"],
    sort: Annotated[str, "Sort: hot, new, top, rising"] = "hot",
    limit: Annotated[int, "Number of posts (1-50)"] = 10,
) -> str:
    """Get posts from a Reddit subreddit (free, no API key required)."""
    posts = await reddit_scraper.get_subreddit(subreddit=subreddit, sort=sort, limit=limit)
    if not posts:
        return f"Could not fetch r/{subreddit}"
    return format_posts_markdown(posts, limit=limit)


@mcp.tool()
async def search_twitter(
    query: Annotated[str, "Search query for X/Twitter"],
    limit: Annotated[int, "Number of tweets (1-30)"] = 10,
) -> str:
    """Search X/Twitter posts (free, no API key required).

    Uses Nitter (public Twitter frontend) to search tweets without API.
    """
    tweets = await twitter_scraper.search(query=query, limit=limit)
    if not tweets:
        return f"No Twitter results for: {query}"
    return format_tweets(tweets, limit=limit)


@mcp.tool()
async def get_user_tweets(
    username: Annotated[str, "Twitter/X username (without @)"],
    limit: Annotated[int, "Number of tweets (1-30)"] = 10,
) -> str:
    """Get recent tweets from a Twitter/X user (free, no API key required)."""
    tweets = await twitter_scraper.get_user_tweets(username=username, limit=limit)
    if not tweets:
        return f"Could not fetch tweets for @{username}"
    return format_tweets(tweets, limit=limit)


@mcp.tool()
async def search_youtube(
    query: Annotated[str, "Search query for YouTube"],
    limit: Annotated[int, "Number of videos (1-20)"] = 10,
) -> str:
    """Search YouTube videos (free, no API key required).

    Searches YouTube for videos matching the query.
    Returns video titles, channels, views, and thumbnails.
    """
    videos = await youtube_scraper.search(query=query, limit=limit)
    if not videos:
        return f"No YouTube results for: {query}"
    return format_youtube_videos(videos, limit=limit)


@mcp.tool()
async def get_youtube_channel(
    channel_id: Annotated[str, "YouTube channel ID (e.g., UC_x5XG1OV2P6uZZ5FSM9Ttw)"],
    limit: Annotated[int, "Number of videos (1-50)"] = 10,
) -> str:
    """Get recent videos from a YouTube channel via RSS (free, no API key).

    Uses YouTube's RSS feed to get recent videos from a channel.
    Channel ID can be found in the channel URL.
    """
    videos = await youtube_scraper.get_channel_videos(channel_id=channel_id, limit=limit)
    if not videos:
        return f"Could not fetch videos for channel {channel_id}"
    return format_youtube_videos(videos, limit=limit)


@mcp.tool()
async def search_github(
    query: Annotated[str, "Search query for GitHub repositories"],
    sort: Annotated[str, "Sort by: stars, forks, updated"] = "stars",
    limit: Annotated[int, "Number of repos (1-30)"] = 10,
) -> str:
    """Search GitHub repositories (free, no API key required)."""
    repos = await github_scraper.search_repos(query=query, sort=sort, limit=limit)
    if not repos:
        return f"No GitHub results for: {query}"
    return format_github_repos(repos, limit=limit)


@mcp.tool()
async def get_github_user(
    username: Annotated[str, "GitHub username"],
) -> str:
    """Get GitHub user profile with repos (free, no API key)."""
    user = await github_scraper.get_user(username=username)
    if not user:
        return f"GitHub user @{username} not found"

    repos = await github_scraper.get_user_repos(username=username, limit=5)
    result = format_github_user(user)

    if repos:
        result += "\n\n## Recent Repositories\n"
        result += format_github_repos(repos, limit=5)

    return result


@mcp.tool()
async def get_github_repo(
    owner: Annotated[str, "Repository owner"],
    repo: Annotated[str, "Repository name"],
) -> str:
    """Get GitHub repo info with README (free, no API key)."""
    r = await github_scraper.get_repo(owner=owner, repo=repo)
    if not r:
        return f"Repository {owner}/{repo} not found"

    readme = await github_scraper.get_readme(owner=owner, repo=repo)

    lines = [
        f"# {r.full_name}\n",
        f"**URL:** {r.url}",
        f"**Language:** {r.language or 'N/A'}",
        f"**Stars:** {r.stars:,} | **Forks:** {r.forks:,} | **Issues:** {r.open_issues}",
        f"**License:** {r.license or 'N/A'}",
    ]

    if r.description:
        lines.extend(["", r.description])
    if r.topics:
        lines.append(f"\n**Topics:** {', '.join(r.topics)}")
    if readme:
        lines.extend(["\n---\n## README\n", readme[:3000]])

    return "\n".join(lines)


@mcp.tool()
async def get_github_readme(
    owner: Annotated[str, "Repository owner"],
    repo: Annotated[str, "Repository name"],
) -> str:
    """Get GitHub repository README content."""
    readme = await github_scraper.get_readme(owner=owner, repo=repo)
    if not readme:
        return f"No README found for {owner}/{repo}"
    return f"# {owner}/{repo} - README\n\n{readme[:5000]}"


@mcp.tool()
async def get_reddit_post(
    subreddit: Annotated[str, "Subreddit name"],
    post_id: Annotated[str, "Post ID (from URL)"],
) -> str:
    """Get full Reddit post content with top comments."""
    result = await reddit_scraper.get_post_content(post_id=post_id, subreddit=subreddit)

    if not result.get("post"):
        return f"Post not found: r/{subreddit}/comments/{post_id}"

    post = result["post"]
    lines = [
        f"# {post.title}\n",
        f"**r/{post.subreddit}** | u/{post.author} | ⬆️ {post.score} | 💬 {post.num_comments}\n",
        post.selftext if post.selftext else "[No text content]",
    ]

    if result.get("comments"):
        lines.extend(["\n---\n## Top Comments\n"])
        for i, comment in enumerate(result["comments"][:5], 1):
            lines.append(f"### Comment {i} - u/{comment.author} (⬆️ {comment.score})")
            lines.append(f"{comment.body}\n")

    return "\n".join(lines)


@mcp.tool()
async def get_youtube_content(
    video_id: Annotated[str, "YouTube video ID (from URL)"],
) -> str:
    """Get YouTube video details with full description."""
    video = await youtube_scraper.get_video_info(video_id=video_id)
    if not video:
        return f"Video not found: {video_id}"

    lines = [
        f"# {video.title}\n",
        f"**Channel:** {video.channel}",
        f"**Views:** {video.views} | **Duration:** {video.duration}",
        f"**URL:** {video.url}\n",
    ]

    if video.description:
        lines.extend(["## Description\n", video.description])

    return "\n".join(lines)


@mcp.tool()
async def get_crawl_stats() -> str:
    """Get crawling statistics and rate limiter status.

    Shows:
    - Domains crawled and request counts
    - Blocked domains (in cooldown)
    - Rate limit configuration
    """
    stats = crawler.rate_limiter.get_stats()

    lines = [
        "# MCPScout Crawl Statistics\n",
        f"**Total domains crawled:** {stats['total_domains']}",
        f"**Domains in cooldown:** {stats['blocked_domains']}\n",
        "## Rate Limit Settings\n",
        f"- Min delay: {crawler.rate_limiter.config.min_delay}s",
        f"- Max delay: {crawler.rate_limiter.config.max_delay}s",
        f"- Requests per minute: {crawler.rate_limiter.config.requests_per_minute}",
        f"- Max retries: {crawler.rate_limiter.config.max_retries}",
        f"- Block cooldown: {crawler.rate_limiter.config.block_cooldown}s\n",
    ]

    if stats.get("domains"):
        lines.append("## Domain Stats\n")
        for domain, domain_stats in stats["domains"].items():
            status = "BLOCKED" if domain_stats.get("is_blocked") else "OK"
            lines.append(f"- **{domain}**: {domain_stats['requests_made']} requests, {domain_stats['blocked_count']} blocks [{status}]")

    return "\n".join(lines)


@mcp.tool()
async def scout(
    action: Annotated[str, "Action: search, crawl, reddit, twitter, youtube, github, multi"],
    query: Annotated[str | None, "Search query"] = None,
    url: Annotated[str | None, "URL to crawl"] = None,
    mode: Annotated[str | None, "Crawl mode: hybrid, stealth"] = None,
    platform: Annotated[str | None, "Platform action: user, post, channel, repo, readme"] = None,
    target: Annotated[str | None, "Target: username, channel_id, owner/repo, post_id"] = None,
    subreddit: Annotated[str | None, "Subreddit name"] = None,
    sort: Annotated[str, "Sort order: stars, hot, new, relevance"] = "relevance",
    limit: Annotated[int, "Number of results"] = 10,
) -> str:
    """All-in-one intelligence tool - MCPScout unified interface.

    Single tool for everything:
    
    SEARCH: scout(action="search", query="AI news")
    CRAWL: scout(action="crawl", url="https://example.com", mode="stealth")
    
    SOCIAL MEDIA:
    - scout(action="reddit", query="python", subreddit="learnpython")
    - scout(action="reddit", platform="post", target="abc123", subreddit="python")
    - scout(action="twitter", query="AI news")
    - scout(action="twitter", platform="user", target="elonmusk")
    - scout(action="youtube", query="python tutorial")
    - scout(action="youtube", platform="video", target="dQw4w9WgXcQ")
    - scout(action="youtube", platform="channel", target="UC_x5XG1OV2P6uZZ5FSM9Ttw")
    - scout(action="github", query="machine learning", sort="stars")
    - scout(action="github", platform="user", target="torvalds")
    - scout(action="github", platform="repo", target="pytorch/pytorch")
    - scout(action="github", platform="readme", target="facebook/react")
    """
    try:
        if action == "search":
            return await aggregator_search(query or "", limit)

        elif action == "crawl":
            return await crawler_crawl(url or "", mode or "hybrid")

        elif action == "reddit":
            return await reddit_action(platform, query, target, subreddit, limit)

        elif action == "twitter":
            return await twitter_action(platform, query, target, limit)

        elif action == "youtube":
            return await youtube_action(platform, query, target, limit)

        elif action == "github":
            return await github_action(platform, query, target, sort, limit)

        else:
            return f"Unknown action: {action}\nAvailable: search, crawl, reddit, twitter, youtube, github"

    except Exception as e:
        return f"Error: {str(e)}"


async def aggregator_search(query: str, limit: int) -> str:
    """Internal search handler."""
    results = await aggregator.search(query=query, max_results=limit)
    if not results:
        return f"No results for: {query}"
    lines = [f"## Search: {query}\n"]
    for i, r in enumerate(results[:limit], 1):
        lines.append(f"### {i}. {r.get('title', 'No title')}")
        lines.append(f"**URL:** {r.get('url', 'N/A')}")
        if r.get("snippet"):
            lines.append(f"{r['snippet']}\n")
    return "\n".join(lines)


async def crawler_crawl(url: str, mode: str) -> str:
    """Internal crawl handler."""
    if mode == "stealth":
        result = await multi_crawler.crawl_with_fallback(url)
        return format_stealth_result(result)
    result = await hybrid_crawler.crawl(url)
    return str(result)


async def reddit_action(platform: str | None, query: str | None, target: str | None, subreddit: str | None, limit: int) -> str:
    """Internal Reddit handler."""
    if platform == "post" and target and subreddit:
        result = await reddit_scraper.get_post_content(post_id=target, subreddit=subreddit)
        if not result.get("post"):
            return "Post not found"
        post = result["post"]
        lines = [f"# {post.title}\n", f"**r/{post.subreddit}** | ⬆️ {post.score}\n"]
        lines.append(post.selftext or "[No content]")
        if result.get("comments"):
            lines.append("\n## Comments\n")
            for i, c in enumerate(result["comments"][:5], 1):
                lines.append(f"**{i}. u/{c.author}**: {c.body[:200]}\n")
        return "\n".join(lines)

    if platform == "subreddit" and (target or subreddit):
        sub = target or subreddit
        if sub:
            posts = await reddit_scraper.get_subreddit(subreddit=sub, limit=limit)
            return format_posts_markdown(posts)

    results = await reddit_scraper.search(query=query or "", subreddit=subreddit, limit=limit)
    return format_posts_markdown(results.posts)


async def twitter_action(platform: str | None, query: str | None, target: str | None, limit: int) -> str:
    """Internal Twitter handler."""
    if platform == "user" and target:
        tweets = await twitter_scraper.get_user_tweets(username=target, limit=limit)
        return format_tweets(tweets)

    tweets = await twitter_scraper.search(query=query or "", limit=limit)
    return format_tweets(tweets)


async def youtube_action(platform: str | None, query: str | None, target: str | None, limit: int) -> str:
    """Internal YouTube handler."""
    if platform == "video" and target:
        video = await youtube_scraper.get_video_info(video_id=target)
        if not video:
            return "Video not found"
        return f"# {video.title}\n**Channel:** {video.channel}\n**Views:** {video.views}\n**Duration:** {video.duration}\n\n{video.description[:1500]}"

    if platform == "channel" and target:
        videos = await youtube_scraper.get_channel_videos(channel_id=target, limit=limit)
        return format_youtube_videos(videos)

    videos = await youtube_scraper.search(query=query or "", limit=limit)
    return format_youtube_videos(videos)


async def github_action(platform: str | None, query: str | None, target: str | None, sort: str, limit: int) -> str:
    """Internal GitHub handler."""
    if platform == "readme" and target:
        owner, repo = target.split("/")
        readme = await github_scraper.get_readme(owner=owner, repo=repo)
        return f"# {target} README\n\n{readme[:5000]}" if readme else "No README found"

    if platform == "repo" and target:
        owner, repo = target.split("/")
        r = await github_scraper.get_repo(owner=owner, repo=repo)
        if not r:
            return "Repository not found"
        readme = await github_scraper.get_readme(owner=owner, repo=repo)
        lines = [f"# {r.full_name}\n", f"**Stars:** {r.stars:,} | **Forks:** {r.forks:,}", f"**Language:** {r.language}"]
        if readme:
            lines.extend(["\n---\n## README\n", readme[:3000]])
        return "\n".join(lines)

    if platform == "user" and target:
        user = await github_scraper.get_user(username=target)
        if not user:
            return "User not found"
        repos = await github_scraper.get_user_repos(username=target, limit=5)
        result = format_github_user(user)
        if repos:
            result += "\n\n## Recent Repos\n" + format_github_repos(repos)
        return result

    repos = await github_scraper.search_repos(query=query or "", sort=sort, limit=limit)
    return format_github_repos(repos)


@mcp.tool()
async def scout_multi(
    actions: Annotated[str, "JSON array of actions: [{'action':'search','query':'...'}, {'action':'reddit','query':'...'}]"],
) -> str:
    """Execute multiple actions in parallel - research across all platforms at once.

    Example: Research a topic across web, Reddit, GitHub, YouTube
    actions: [{"action":"search","query":"React"},{"action":"reddit","query":"reactjs"},{"action":"github","query":"react"}]
    """
    try:
        action_list = json.loads(actions)
        if not isinstance(action_list, list):
            return "Error: actions must be a JSON array"
    except json.JSONDecodeError:
        return "Error: Invalid JSON format"

    tasks = []
    for action_config in action_list:
        action = action_config.get("action", "")
        kwargs = {k: v for k, v in action_config.items() if k != "action"}

        if action == "search":
            tasks.append(aggregator_search(kwargs.get("query", ""), kwargs.get("limit", 10)))
        elif action == "crawl":
            tasks.append(crawler_crawl(kwargs.get("url", ""), kwargs.get("mode", "hybrid")))
        elif action == "reddit":
            tasks.append(reddit_action(kwargs.get("platform"), kwargs.get("query"), kwargs.get("target"), kwargs.get("subreddit"), kwargs.get("limit", 10)))
        elif action == "twitter":
            tasks.append(twitter_action(kwargs.get("platform"), kwargs.get("query"), kwargs.get("target"), kwargs.get("limit", 10)))
        elif action == "youtube":
            tasks.append(youtube_action(kwargs.get("platform"), kwargs.get("query"), kwargs.get("target"), kwargs.get("limit", 10)))
        elif action == "github":
            tasks.append(github_action(kwargs.get("platform"), kwargs.get("query"), kwargs.get("target"), kwargs.get("sort", "relevance"), kwargs.get("limit", 10)))

    if not tasks:
        return "No valid actions found"

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for i, (action_config, result) in enumerate(zip(action_list, results), 1):
        action = action_config.get("action", "unknown")
        if isinstance(result, Exception):
            output.append(f"## [{action}] Error\n{str(result)}\n")
        else:
            output.append(f"## [{action}]\n{result}\n")

    return "\n---\n".join(output)


@mcp.resource("search://help")
async def get_help() -> str:
    """Get help documentation."""
    return """# MCPSpider Tools

## Search
- web_search: Search multiple engines
- search_and_summarize: Search + AI summary
- smart_search: Smart link filtering (free)
- deep_search: Search + follow all links

## Crawl
- crawl_url: Single URL
- crawl_recursive: Follow all links

## Smart Link Scoring (Heuristic, Free)
+0.3  Query word in URL
+0.2  High-signal (wiki, tutorial, docs)
+0.25 Query word in title/anchor
-0.3  Low-signal (login, cart, ads)
"""


# =============================================================================
# PROMPTS
# =============================================================================


@mcp.prompt()
def smart_research(topic: str) -> str:
    """Smart research using link filtering."""
    return f"""Research: {topic}

Use smart_search for focused deep research:
smart_search(query="{topic}", max_depth=2, max_pages=20)
"""


# =============================================================================
# ENTRY POINT
# =============================================================================


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
