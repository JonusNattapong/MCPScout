"""MCPSearch Server - AI-powered multi-source intelligence platform."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from mcp_server import handlers
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
from utils.dedup import ResultDeduplicator

# Initialize FastMCP server
mcp = FastMCP("mcpsearch")

# Lazy initialization of components to save context window
_aggregator = None
_summarizer = None
_crawler = None
_smart_crawler = None
_extractor = None
_hybrid_crawler = None
_reddit_scraper = None
_twitter_scraper = None
_youtube_scraper = None
_github_scraper = None
_stealth_browser = None
_multi_crawler = None

def get_aggregator():
    global _aggregator
    if _aggregator is None:
        _aggregator = SearchAggregator()
        # Also register with handlers for mcpsearch unified interface
        handlers.set_components(aggregator=_aggregator)
    return _aggregator

def get_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = AISummarizer()
    return _summarizer

def get_crawler():
    global _crawler
    if _crawler is None:
        _crawler = CrawlerEngine()
        handlers.set_components(crawler=_crawler)
    return _crawler

def get_smart_crawler():
    global _smart_crawler
    if _smart_crawler is None:
        _smart_crawler = SmartCrawler()
    return _smart_crawler

def get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = ContentExtractor()
    return _extractor

def get_hybrid_crawler():
    global _hybrid_crawler
    if _hybrid_crawler is None:
        _hybrid_crawler = HybridCrawler()
        handlers.set_components(hybrid_crawler=_hybrid_crawler)
    return _hybrid_crawler

def get_reddit_scraper():
    global _reddit_scraper
    if _reddit_scraper is None:
        _reddit_scraper = RedditScraper()
        handlers.set_components(reddit=_reddit_scraper)
    return _reddit_scraper

def get_twitter_scraper():
    global _twitter_scraper
    if _twitter_scraper is None:
        _twitter_scraper = TwitterScraper()
        handlers.set_components(twitter=_twitter_scraper)
    return _twitter_scraper

def get_youtube_scraper():
    global _youtube_scraper
    if _youtube_scraper is None:
        _youtube_scraper = YouTubeScraper()
        handlers.set_components(youtube=_youtube_scraper)
    return _youtube_scraper

def get_github_scraper():
    global _github_scraper
    if _github_scraper is None:
        _github_scraper = GitHubScraper()
        handlers.set_components(github=_github_scraper)
    return _github_scraper

def get_stealth_browser():
    global _stealth_browser
    if _stealth_browser is None:
        _stealth_browser = StealthBrowser()
    return _stealth_browser

def get_multi_crawler():
    global _multi_crawler
    if _multi_crawler is None:
        _multi_crawler = MultiBrowserCrawler()
    return _multi_crawler


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
    results = await get_aggregator().search(query=query, max_results=max_results, sources=sources)
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
    return await get_crawler().crawl(url=url, extract_mode=extract_mode)  # type: ignore


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

            content = get_extractor().extract(response.text, base_url=url)

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
async def research_agent(
    topic: Annotated[str, "Research topic or question"],
    depth: Annotated[int, "Research depth: 1-5 (1=quick, 5=comprehensive)"] = 3,
    sources: Annotated[list[str] | None, "Sources to use: web, reddit, twitter, youtube, github"] = None,
    max_sources: Annotated[int, "Maximum sources to analyze per step"] = 10,
    output_format: Annotated[str, "Output format: summary, detailed, or structured"] = "detailed",
) -> str:
    """Multi-step Research Agent - Comprehensive research across multiple sources.

    This tool acts as an AI research agent that:
    1. Breaks down the research topic into key questions
    2. Searches multiple sources in parallel
    3. Extracts and synthesizes information
    4. Cross-references findings
    5. Generates a comprehensive research report

    Unlike simple search tools, this agent:
    - Performs iterative research (search → analyze → search deeper)
    - Validates information across multiple sources
    - Identifies patterns and contradictions
    - Provides citations and source attribution

    Use cases:
    - Market research and competitive analysis
    - Technical deep dives and technology comparisons
    - Academic research and literature reviews
    - Product research and reviews
    - Trend analysis and forecasting

    Examples:
    - research_agent(topic="AI trends 2024", depth=3)
    - research_agent(topic="Compare React vs Vue", depth=4, sources=["web", "github"])
    - research_agent(topic="Best practices for microservices", depth=5)
    """
    import httpx

    if sources is None:
        sources = ["web", "reddit", "github"]

    try:
        lines = [f"# Research Report: {topic}\n"]
        lines.append(f"**Research Depth:** {depth}/5")
        lines.append(f"**Sources:** {', '.join(sources)}")
        lines.append(f"**Max Sources:** {max_sources}\n")

        # Step 1: Initial search across all sources
        lines.append("## Step 1: Initial Search\n")
        search_results = {}

        for source in sources:
            if source == "web":
                results = await aggregator.search(query=topic, max_results=max_sources)
                search_results["web"] = results
                lines.append(f"### Web Search: {len(results)} results")
                for i, r in enumerate(results[:3], 1):
                    lines.append(f"{i}. {r.get('title', 'No title')} - {r.get('url', 'N/A')}")
                lines.append("")

            elif source == "reddit":
                results = await reddit_scraper.search(query=topic, limit=max_sources)
                search_results["reddit"] = results.posts if results else []
                lines.append(f"### Reddit: {len(results.posts) if results else 0} posts")
                if results:
                    for i, post in enumerate(results.posts[:3], 1):
                        lines.append(f"{i}. {post.title} (⬆️ {post.score})")
                lines.append("")

            elif source == "github":
                results = await github_scraper.search_repos(query=topic, limit=max_sources)
                search_results["github"] = results
                lines.append(f"### GitHub: {len(results)} repositories")
                for i, repo in enumerate(results[:3], 1):
                    lines.append(f"{i}. {repo.full_name} (⭐ {repo.stars:,})")
                lines.append("")

            elif source == "youtube":
                results = await youtube_scraper.search(query=topic, limit=max_sources)
                search_results["youtube"] = results
                lines.append(f"### YouTube: {len(results)} videos")
                for i, video in enumerate(results[:3], 1):
                    lines.append(f"{i}. {video.title} ({video.views} views)")
                lines.append("")

        # Step 2: Deep crawl of top sources
        if depth >= 2:
            lines.append("## Step 2: Deep Analysis\n")
            top_urls = []

            if "web" in search_results:
                top_urls.extend([r["url"] for r in search_results["web"][:5]])

            if top_urls:
                lines.append(f"Deep crawling {len(top_urls)} top sources...")
                crawled = await crawler.crawl_multiple(urls=top_urls[:5])

                for i, page in enumerate(crawled[:3], 1):
                    if not page.get("error"):
                        lines.append(f"### Source {i}: {page.get('title', 'Unknown')}")
                        lines.append(f"**URL:** {page.get('url', 'N/A')}")
                        content = page.get("content", "")
                        lines.append(f"{content[:500]}...\n")

        # Step 3: Cross-reference and synthesis
        if depth >= 3:
            lines.append("## Step 3: Key Findings\n")

            # Extract key themes
            all_content = []
            for source_type, results in search_results.items():
                if source_type == "web":
                    for r in results[:5]:
                        all_content.append(r.get("snippet", ""))
                elif source_type == "reddit":
                    for post in results[:5]:
                        all_content.append(post.title)
                        if hasattr(post, "selftext"):
                            all_content.append(post.selftext or "")

            # Simple keyword extraction (in production, use NLP)
            keywords = set()
            for content in all_content:
                words = content.lower().split()
                keywords.update([w for w in words if len(w) > 5])

            lines.append("### Identified Themes\n")
            for i, keyword in enumerate(list(keywords)[:10], 1):
                lines.append(f"{i}. {keyword}")

            lines.append("")

        # Step 4: Summary and recommendations
        if depth >= 4:
            lines.append("## Step 4: Summary & Recommendations\n")
            lines.append(f"Based on analysis of {sum(len(v) if isinstance(v, list) else len(v.posts) if hasattr(v, 'posts') else 0 for v in search_results.values())} sources across {len(sources)} platforms:\n")

            lines.append("### Key Takeaways\n")
            lines.append(f"1. **{topic}** is actively discussed across multiple platforms")
            lines.append(f"2. GitHub shows strong community interest with {len(search_results.get('github', []))} related repositories")
            lines.append(f"3. Reddit discussions provide real-world user perspectives")
            lines.append(f"4. Web sources offer comprehensive documentation and tutorials\n")

            lines.append("### Recommended Next Steps\n")
            lines.append("1. Review top GitHub repositories for implementation examples")
            lines.append("2. Check Reddit for community feedback and best practices")
            lines.append("3. Explore YouTube for visual tutorials and demonstrations")
            lines.append("4. Read official documentation from authoritative sources\n")

        # Step 5: Citations
        if depth >= 5:
            lines.append("## Step 5: Citations & Sources\n")
            citation_num = 1

            if "web" in search_results:
                lines.append("### Web Sources\n")
                for r in search_results["web"][:5]:
                    lines.append(f"[{citation_num}] {r.get('title', 'No title')} - {r.get('url', 'N/A')}")
                    citation_num += 1
                lines.append("")

            if "github" in search_results:
                lines.append("### GitHub Repositories\n")
                for repo in search_results["github"][:5]:
                    lines.append(f"[{citation_num}] {repo.full_name} - {repo.url}")
                    citation_num += 1
                lines.append("")

            if "reddit" in search_results and search_results["reddit"]:
                lines.append("### Reddit Discussions\n")
                for post in search_results["reddit"][:5]:
                    lines.append(f"[{citation_num}] {post.title}")
                    citation_num += 1
                lines.append("")

        # Output format
        if output_format == "summary":
            # Return only the summary section
            summary_start = None
            for i, line in enumerate(lines):
                if "## Step 4: Summary" in line:
                    summary_start = i
                    break
            if summary_start:
                return "\n".join(lines[summary_start:])

        elif output_format == "structured":
            # Return as JSON-like structure
            result = {
                "topic": topic,
                "depth": depth,
                "sources_analyzed": len(sources),
                "total_results": sum(len(v) if isinstance(v, list) else len(v.posts) if hasattr(v, 'posts') else 0 for v in search_results.values()),
                "report": "\n".join(lines),
            }
            return json.dumps(result, indent=2, ensure_ascii=False)

        # Default: detailed format
        return "\n".join(lines)

    except Exception as e:
        return f"Error in research agent: {str(e)}"


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
    result = await get_multi_crawler().crawl_with_fallback(url)
    return format_stealth_result(result)


@mcp.tool()
async def crawl_recursive(
    url: Annotated[str, "Starting URL"],
    max_depth: Annotated[int, "How deep to follow links (1-5)"] = 3,
    max_pages: Annotated[int, "Maximum pages to crawl (1-100)"] = 20,
    same_domain_only: Annotated[bool, "Only crawl same domain"] = True,
) -> str:
    """Recursively crawl a website following all links."""
    result = await get_crawler().crawl_recursive(
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
    search_results = await get_aggregator().search(query=query, max_results=5)
    if not search_results:
        return f"No results found for: {query}"

    # Smart crawl from search results
    urls = [r["url"] for r in search_results[:3]]
    result = await get_smart_crawler().smart_crawl(
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
    result = await get_crawler().deep_search(
        query=query, search_engine=get_aggregator(), max_depth=max_depth, max_pages=max_pages,
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
        "# MCPSearch Crawl Statistics\n",
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
async def mcpsearch(
    action: Annotated[str, "Action: search, crawl, reddit, twitter, youtube, github"],
    query: Annotated[str | None, "Search query"] = None,
    url: Annotated[str | None, "URL to crawl"] = None,
    mode: Annotated[str | None, "Crawl mode: fast (httpx), hybrid (deep), stealth (anti-bot)"] = None,
    action_type: Annotated[str | None, "Platform action: search, user, post, channel, repo, readme"] = None,
    platform: Annotated[str | None, "Legacy: use action_type instead"] = None,
    target: Annotated[str | None, "Target: username, channel_id, owner/repo, post_id"] = None,
    subreddit: Annotated[str | None, "Subreddit name"] = None,
    sort: Annotated[str, "Sort order: stars, hot, new, relevance"] = "relevance",
    limit: Annotated[int, "Number of results"] = 10,
) -> str:
    """All-in-one intelligence tool - MCPSearch unified interface.

    Single tool for everything with clear mode selection:
    
    SEARCH: mcpsearch(action="search", query="AI news")
    
    CRAWL MODES:
    - fast: Uses httpx only (~50ms), best for static sites
    - hybrid: httpx + Playwright, auto-detects JS-heavy pages
    - stealth: Anti-bot bypass (Cloudflare, Akamai, DataDome)
    
    Examples:
    - mcpsearch(action="crawl", url="https://example.com", mode="fast")
    - mcpsearch(action="crawl", url="https://example.com", mode="hybrid")
    - mcpsearch(action="crawl", url="https://example.com", mode="stealth")
    
    SOCIAL MEDIA:
    - mcpsearch(action="reddit", query="python")
    - mcpsearch(action="reddit", subreddit="learnpython", query="beginners")
    - mcpsearch(action="twitter", query="AI news")
    - mcpsearch(action="youtube", query="python tutorial", limit=5)
    - mcpsearch(action="github", query="machine learning", sort="stars")
    """
    # Ensure components are registered with handlers
    get_aggregator()
    get_crawler()
    get_hybrid_crawler()
    get_reddit_scraper()
    get_twitter_scraper()
    get_youtube_scraper()
    get_github_scraper()
    
    # Route through unified handlers
    try:
        return await handlers.route_action(
            action,
            query=query,
            url=url,
            mode=mode or "hybrid",
            action_type=action_type or platform,
            target=target,
            subreddit=subreddit,
            sort=sort,
            limit=limit,
        )
    except Exception as e:
        import logging
        logging.error(f"mcpsearch error: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def mcpsearch_multi(
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

    # Ensure components are initialized
    get_aggregator()
    get_crawler()
    get_hybrid_crawler()
    get_reddit_scraper()
    get_twitter_scraper()
    get_youtube_scraper()
    get_github_scraper()

    # Route all actions through unified handlers
    tasks = []
    for action_config in action_list:
        action = action_config.get("action", "")
        kwargs = {k: v for k, v in action_config.items() if k != "action"}
        tasks.append(handlers.route_action(action, **kwargs))

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


@mcp.tool()
async def investigate(
    topic: Annotated[str, "Research topic"],
    depth: Annotated[str, "Research depth: shallow, medium, or deep"] = "medium",
    include_social: Annotated[bool, "Include social media (Reddit, Twitter, GitHub)"] = True,
    include_summary: Annotated[bool, "Include AI-powered summary"] = False,
    max_sources: Annotated[int, "Maximum sources to gather"] = 5,
) -> str:
    """Comprehensive research investigation - Flagship Feature.

    Combines search, crawling, and social media analysis for deep research.
    
    Depths:
    - shallow: Web search only
    - medium: Web search + crawl top results
    - deep: Web search + crawl multiple + social media analysis
    
    Use this tool to:
    - Research a new technology or topic
    - Gather competitive intelligence
    - Analyze trends across multiple platforms
    - Get comprehensive background on a subject
    """
    agent = get_research_agent_instance()
    
    try:
        report = await agent.investigate(
            topic,
            search_depth=depth,
            include_social=include_social,
            include_summary=include_summary,
            max_sources=max_sources,
        )
        
        # Format as markdown
        lines = [f"# Research: {topic}\n", f"**Depth:** {depth} | **Social:** {include_social}\n"]
        
        if report["findings"]["web_search"]:
            lines.append("## Web Search Results\n")
            for i, r in enumerate(report["findings"]["web_search"], 1):
                lines.append(f"{i}. **{r.get('title', 'No title')}**")
                lines.append(f"   [{r.get('url', 'N/A')}]({r.get('url', 'N/A')})")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet'][:200]}\n")
        
        if report["findings"]["social_media"]:
            lines.append("\n## Social Media Insights\n")
            for platform, results in report["findings"]["social_media"].items():
                lines.append(f"### {platform.title()}\n")
                if isinstance(results, list):
                    for item in results[:3]:
                        lines.append(f"- {str(item)[:150]}")
                lines.append()
        
        if report["findings"]["summary"]:
            lines.append("\n## AI Summary\n")
            lines.append(report["findings"]["summary"])
        
        return "\n".join(lines)
    except Exception as e:
        import logging
        logging.error(f"investigate error: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def compare(
    topics: Annotated[str, "Topics to compare (comma-separated)"],
    depth: Annotated[str, "Research depth: shallow or medium"] = "shallow",
    max_sources: Annotated[int, "Maximum sources per topic"] = 3,
) -> str:
    """Compare multiple topics side-by-side.

    Runs parallel research on each topic and presents findings
    in a comparative format.
    
    Examples:
    - compare("React vs Vue vs Angular")
    - compare("Python vs Go for backend")
    - compare("MacBook vs ThinkPad vs Dell")
    """
    agent = get_research_agent_instance()
    topic_list = [t.strip() for t in topics.split(",")]
    
    if len(topic_list) < 2:
        return "Error: Please provide at least 2 topics to compare (comma-separated)"
    
    try:
        comparison = await agent.compare(
            topic_list,
            search_depth=depth,
            max_sources=max_sources,
        )
        
        # Format as markdown
        lines = [f"# Comparison: {' vs '.join(topic_list)}\n"]
        
        for topic in topic_list:
            report = comparison["reports"][topic]
            lines.append(f"## {topic}\n")
            
            if report["findings"]["web_search"]:
                lines.append("### Key Results\n")
                for r in report["findings"]["web_search"][:2]:
                    lines.append(f"- **{r.get('title', 'N/A')}**")
                    lines.append(f"  {r.get('snippet', '')[:100]}\n")
            lines.append()
        
        return "\n".join(lines)
    except Exception as e:
        import logging
        logging.error(f"compare error: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def trending(
    platforms: Annotated[str, "Platforms: reddit, twitter, github (comma-separated)"] = "reddit,github",
    limit: Annotated[int, "Results per platform"] = 10,
) -> str:
    """Get trending topics from social platforms.
    
    Platforms: reddit, twitter (X), github
    
    Use this to discover:
    - Hot topics on Reddit
    - Trending code on GitHub
    - Popular projects and discussions
    """
    agent = get_research_agent_instance()
    platform_list = [p.strip().lower() for p in platforms.split(",")]
    
    try:
        trending_data = await agent.trending(
            platforms=platform_list,
            limit=limit,
        )
        
        # Format as markdown
        lines = ["# Trending Topics\n"]
        
        for platform, items in trending_data["trending"].items():
            lines.append(f"## {platform.title()}\n")
            if items:
                for i, item in enumerate(items[:5], 1):
                    lines.append(f"{i}. {str(item)[:150]}")
            lines.append()
        
        return "\n".join(lines)
    except Exception as e:
        import logging
        logging.error(f"trending error: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def list_tools() -> str:
    """List all available MCPSearch tools with brief descriptions.

    Use this tool to discover what capabilities are available before
    deciding which tool to use for a specific task.
    """
    tools = [
        ("web_search", "Search multiple websites in parallel"),
        ("search_and_summarize", "Search, crawl, and AI-summarize (Perplexity-style)"),
        ("smart_search", "Smart search with heuristic link relevance filtering"),
        ("deep_search", "Deep search: search then recursively crawl top results"),
        ("crawl_url", "Crawl a specific URL and extract its content"),
        ("hybrid_crawl", "Hybrid crawling with auto-stealth fallback"),
        ("crawl_recursive", "Recursively crawl a website following all links"),
        ("extract_content", "Advanced content extraction with tables, code, images"),
        ("mcpsearch", "All-in-one intelligence tool - unified interface"),
        ("mcpsearch_multi", "Execute multiple actions in parallel"),
        ("search_reddit", "Search Reddit for posts (free, no API key)"),
        ("get_subreddit", "Get posts from a Reddit subreddit"),
        ("get_reddit_post", "Get full Reddit post content with top comments"),
        ("search_twitter", "Search X/Twitter posts (free, no API key)"),
        ("get_user_tweets", "Get recent tweets from a Twitter/X user"),
        ("search_youtube", "Search YouTube videos (free, no API key)"),
        ("get_youtube_channel", "Get recent videos from a YouTube channel"),
        ("get_youtube_content", "Get YouTube video details with full description"),
        ("search_github", "Search GitHub repositories (free, no API key)"),
        ("get_github_user", "Get GitHub user profile with repos"),
        ("get_github_repo", "Get GitHub repo info with README"),
        ("get_github_readme", "Get GitHub repository README content"),
        ("get_crawl_stats", "Get crawling statistics and rate limiter status"),
    ]

    lines = ["# MCPSearch Available Tools\n"]
    for name, desc in tools:
        lines.append(f"- **{name}**: {desc}")

    lines.append("\n## Quick Start")
    lines.append("- For simple search: `web_search(query=\"...\")`")
    lines.append("- For search + summary: `search_and_summarize(query=\"...\")`")
    lines.append("- For unified interface: `mcpsearch(action=\"search\", query=\"...\")`")
    lines.append("- For tool discovery: `list_tools()` or `describe_tools()`")

    return "\n".join(lines)


@mcp.tool()
async def describe_tools(
    tool_name: Annotated[str | None, "Specific tool name to describe (optional)"] = None,
) -> str:
    """Get detailed documentation for MCPSearch tools.

    Without tool_name: Returns overview of all tools with usage examples.
    With tool_name: Returns detailed documentation for that specific tool.
    """
    if tool_name:
        # Detailed documentation for specific tool
        tool_docs = {
            "web_search": {
                "description": "Search multiple websites in parallel and return results.",
                "params": [
                    ("query", "str", "Search query to execute"),
                    ("max_results", "int", "Maximum number of results (default: 10)"),
                    ("sources", "list[str] | None", "Search engines to use (optional)"),
                ],
                "example": 'web_search(query="Python tutorials", max_results=5)',
            },
            "search_and_summarize": {
                "description": "Search, crawl, and AI-summarize (Perplexity-style).",
                "params": [
                    ("query", "str", "Search query"),
                    ("max_sources", "int", "Sources to analyze (default: 5)"),
                    ("summary_length", "str", "brief/detailed/comprehensive (default: detailed)"),
                ],
                "example": 'search_and_summarize(query="latest AI news", summary_length="brief")',
            },
            "smart_search": {
                "description": "Smart search with heuristic link relevance filtering.",
                "params": [
                    ("query", "str", "Search query for focused deep research"),
                    ("max_depth", "int", "Crawl depth 1-3 (default: 2)"),
                    ("max_pages", "int", "Maximum pages 1-50 (default: 15)"),
                ],
                "example": 'smart_search(query="machine learning basics", max_depth=2)',
            },
            "deep_search": {
                "description": "Deep search: search then recursively crawl top results.",
                "params": [
                    ("query", "str", "Search query"),
                    ("max_depth", "int", "Crawl depth (default: 2)"),
                    ("max_pages", "int", "Max pages (default: 15)"),
                ],
                "example": 'deep_search(query="React documentation", max_depth=2)',
            },
            "crawl_url": {
                "description": "Crawl a specific URL and extract its content.",
                "params": [
                    ("url", "str", "URL to crawl"),
                    ("extract_mode", "str", "text/markdown/structured (default: markdown)"),
                ],
                "example": 'crawl_url(url="https://example.com", extract_mode="markdown")',
            },
            "hybrid_crawl": {
                "description": "Hybrid crawling with auto-stealth fallback.",
                "params": [
                    ("url", "str", "URL to crawl with smart routing"),
                    ("force_browser", "bool", "Force Playwright browser rendering (default: False)"),
                    ("wait_for_selector", "str | None", "CSS selector to wait for (optional)"),
                ],
                "example": 'hybrid_crawl(url="https://example.com")',
            },
            "crawl_recursive": {
                "description": "Recursively crawl a website following all links.",
                "params": [
                    ("url", "str", "Starting URL"),
                    ("max_depth", "int", "How deep to follow links 1-5 (default: 3)"),
                    ("max_pages", "int", "Maximum pages to crawl 1-100 (default: 20)"),
                    ("same_domain_only", "bool", "Only crawl same domain (default: True)"),
                ],
                "example": 'crawl_recursive(url="https://docs.python.org", max_depth=2)',
            },
            "extract_content": {
                "description": "Advanced content extraction with tables, code blocks, images.",
                "params": [
                    ("url", "str", "URL to extract content from"),
                    ("include_tables", "bool", "Extract tables as markdown (default: True)"),
                    ("include_code", "bool", "Extract code blocks (default: True)"),
                    ("include_images", "bool", "Extract image metadata (default: True)"),
                ],
                "example": 'extract_content(url="https://example.com/data")',
            },
            "mcpsearch": {
                "description": "All-in-one intelligence tool - unified interface.",
                "params": [
                    ("action", "str", "Action: search, crawl, reddit, twitter, youtube, github"),
                    ("query", "str | None", "Search query (optional)"),
                    ("url", "str | None", "URL to crawl (optional)"),
                    ("mode", "str | None", "Crawl mode: fast (httpx), deep (hybrid), stealth (anti-bot bypass) (optional)"),
                    ("platform", "str | None", "Platform action: user, post, channel, repo, readme (optional)"),
                    ("target", "str | None", "Target: username, channel_id, owner/repo, post_id (optional)"),
                    ("subreddit", "str | None", "Subreddit name (optional)"),
                    ("sort", "str", "Sort order: stars, hot, new, relevance (default: relevance)"),
                    ("limit", "int", "Number of results (default: 10)"),
                ],
                "example": 'mcpsearch(action="search", query="AI news")',
            },
            "mcpsearch_multi": {
                "description": "Execute multiple actions in parallel - research across all platforms.",
                "params": [
                    ("actions", "str", "JSON array of actions"),
                ],
                "example": 'mcpsearch_multi(actions=\'[{"action":"search","query":"React"},{"action":"reddit","query":"reactjs"}]\')',
            },
            "search_reddit": {
                "description": "Search Reddit for posts (free, no API key required).",
                "params": [
                    ("query", "str", "Search query for Reddit"),
                    ("subreddit", "str | None", "Limit to specific subreddit (optional)"),
                    ("sort", "str", "Sort by: relevance, hot, top, new (default: relevance)"),
                    ("limit", "int", "Number of results 1-50 (default: 10)"),
                ],
                "example": 'search_reddit(query="python", subreddit="learnpython")',
            },
            "get_subreddit": {
                "description": "Get posts from a Reddit subreddit (free, no API key required).",
                "params": [
                    ("subreddit", "str", "Subreddit name (without r/)"),
                    ("sort", "str", "Sort: hot, new, top, rising (default: hot)"),
                    ("limit", "int", "Number of posts 1-50 (default: 10)"),
                ],
                "example": 'get_subreddit(subreddit="python", sort="hot")',
            },
            "get_reddit_post": {
                "description": "Get full Reddit post content with top comments.",
                "params": [
                    ("subreddit", "str", "Subreddit name"),
                    ("post_id", "str", "Post ID (from URL)"),
                ],
                "example": 'get_reddit_post(subreddit="python", post_id="abc123")',
            },
            "search_twitter": {
                "description": "Search X/Twitter posts (free, no API key required).",
                "params": [
                    ("query", "str", "Search query for X/Twitter"),
                    ("limit", "int", "Number of tweets 1-30 (default: 10)"),
                ],
                "example": 'search_twitter(query="AI news", limit=10)',
            },
            "get_user_tweets": {
                "description": "Get recent tweets from a Twitter/X user (free, no API key required).",
                "params": [
                    ("username", "str", "Twitter/X username (without @)"),
                    ("limit", "int", "Number of tweets 1-30 (default: 10)"),
                ],
                "example": 'get_user_tweets(username="elonmusk", limit=10)',
            },
            "search_youtube": {
                "description": "Search YouTube videos (free, no API key required).",
                "params": [
                    ("query", "str", "Search query for YouTube"),
                    ("limit", "int", "Number of videos 1-20 (default: 10)"),
                ],
                "example": 'search_youtube(query="python tutorial", limit=5)',
            },
            "get_youtube_channel": {
                "description": "Get recent videos from a YouTube channel via RSS (free, no API key).",
                "params": [
                    ("channel_id", "str", "YouTube channel ID"),
                    ("limit", "int", "Number of videos 1-50 (default: 10)"),
                ],
                "example": 'get_youtube_channel(channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw")',
            },
            "get_youtube_content": {
                "description": "Get YouTube video details with full description.",
                "params": [
                    ("video_id", "str", "YouTube video ID (from URL)"),
                ],
                "example": 'get_youtube_content(video_id="dQw4w9WgXcQ")',
            },
            "search_github": {
                "description": "Search GitHub repositories (free, no API key required).",
                "params": [
                    ("query", "str", "Search query for GitHub repositories"),
                    ("sort", "str", "Sort by: stars, forks, updated (default: stars)"),
                    ("limit", "int", "Number of repos 1-30 (default: 10)"),
                ],
                "example": 'search_github(query="machine learning", sort="stars")',
            },
            "get_github_user": {
                "description": "Get GitHub user profile with repos (free, no API key).",
                "params": [
                    ("username", "str", "GitHub username"),
                ],
                "example": 'get_github_user(username="torvalds")',
            },
            "get_github_repo": {
                "description": "Get GitHub repo info with README (free, no API key).",
                "params": [
                    ("owner", "str", "Repository owner"),
                    ("repo", "str", "Repository name"),
                ],
                "example": 'get_github_repo(owner="facebook", repo="react")',
            },
            "get_github_readme": {
                "description": "Get GitHub repository README content.",
                "params": [
                    ("owner", "str", "Repository owner"),
                    ("repo", "str", "Repository name"),
                ],
                "example": 'get_github_readme(owner="python", repo="cpython")',
            },
            "get_crawl_stats": {
                "description": "Get crawling statistics and rate limiter status.",
                "params": [],
                "example": "get_crawl_stats()",
            },
        }

        if tool_name not in tool_docs:
            return f"Tool '{tool_name}' not found. Use list_tools() to see available tools."

        doc = tool_docs[tool_name]
        lines = [f"# {tool_name}\n"]
        lines.append(f"**Description:** {doc['description']}\n")

        if doc["params"]:
            lines.append("## Parameters\n")
            lines.append("| Name | Type | Description |")
            lines.append("|------|------|-------------|")
            for param_name, param_type, param_desc in doc["params"]:
                lines.append(f"| {param_name} | `{param_type}` | {param_desc} |")
            lines.append("")

        lines.append(f"## Example\n```python\n{doc['example']}\n```")

        return "\n".join(lines)

    else:
        # Overview of all tools
        lines = ["# MCPSearch Tools Overview\n"]
        lines.append("## Web Search & Research")
        lines.append("- `web_search`: Basic multi-engine search")
        lines.append("- `search_and_summarize`: Search + AI summary (Perplexity-style)")
        lines.append("- `smart_search`: Smart link filtering for focused research")
        lines.append("- `deep_search`: Search + recursive crawl of all links")
        lines.append("")

        lines.append("## Web Crawling")
        lines.append("- `crawl_url`: Single URL extraction")
        lines.append("- `hybrid_crawl`: Auto-stealth fallback crawling")
        lines.append("- `crawl_recursive`: Follow all links on a site")
        lines.append("- `extract_content`: Extract tables, code, images")
        lines.append("")

        lines.append("## Unified Interface")
        lines.append("- `mcpsearch`: All-in-one tool (search, crawl, social media)")
        lines.append("- `mcpsearch_multi`: Execute multiple actions in parallel")
        lines.append("")

        lines.append("## Social Media (Free, No API Key)")
        lines.append("- `search_reddit`, `get_subreddit`, `get_reddit_post`")
        lines.append("- `search_twitter`, `get_user_tweets`")
        lines.append("- `search_youtube`, `get_youtube_channel`, `get_youtube_content`")
        lines.append("- `search_github`, `get_github_user`, `get_github_repo`, `get_github_readme`")
        lines.append("")

        lines.append("## Utilities")
        lines.append("- `list_tools`: List all available tools")
        lines.append("- `describe_tools`: Get detailed tool documentation")
        lines.append("- `get_crawl_stats`: View crawling statistics")
        lines.append("")

        lines.append("## Quick Examples")
        lines.append("```python")
        lines.append("# Simple search")
        lines.append('web_search(query="Python tutorials")')
        lines.append("")
        lines.append("# Search with AI summary")
        lines.append('search_and_summarize(query="latest AI news", summary_length="brief")')
        lines.append("")
        lines.append("# Unified interface")
        lines.append('mcpsearch(action="search", query="React")')
        lines.append('mcpsearch(action="crawl", url="https://example.com", mode="stealth")')
        lines.append("")
        lines.append("# Get help on a specific tool")
        lines.append('describe_tools(tool_name="mcpsearch")')
        lines.append("```")

        return "\n".join(lines)


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
