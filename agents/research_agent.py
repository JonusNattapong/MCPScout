"""Research Agent - Flagship Orchestration Tool

Combines search, crawl, and analysis for comprehensive research workflows.
Elevates MCPSearch from simple tools to an intelligent research platform.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from search.aggregator import SearchAggregator
from crawler.hybrid import HybridCrawler
from crawler.stealth import MultiBrowserCrawler
from social.reddit import RedditScraper
from social.twitter import TwitterScraper
from social.youtube import YouTubeScraper
from social.github import GitHubScraper
from summarizer.ai_summarizer import AISummarizer
from utils.dedup import ResultDeduplicator, RankedResult

logger = logging.getLogger(__name__)


@dataclass
class SourceAttribution:
    """Attribution for a source with confidence scoring."""
    url: str
    title: str
    source_type: str  # web, reddit, twitter, youtube, github
    confidence: float = 0.0
    relevance_score: float = 0.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "relevance_score": self.relevance_score,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ResearchFinding:
    """A single research finding with source attribution."""
    content: str
    source: SourceAttribution
    key_points: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "source": self.source.to_dict(),
            "key_points": self.key_points,
            "confidence": self.confidence,
        }


@dataclass
class ResearchReport:
    """Structured research report with findings and metadata."""
    topic: str
    timestamp: str
    search_depth: str
    findings: list[ResearchFinding] = field(default_factory=list)
    summary: str | None = None
    key_themes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "topic": self.topic,
            "timestamp": self.timestamp,
            "search_depth": self.search_depth,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "key_themes": self.key_themes,
            "recommendations": self.recommendations,
            "statistics": self.statistics,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export as JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Export as Markdown."""
        lines = [
            f"# Research Report: {self.topic}",
            f"",
            f"**Generated:** {self.timestamp}",
            f"**Search Depth:** {self.search_depth}",
            f"**Total Findings:** {len(self.findings)}",
            f"",
        ]

        # Summary section
        if self.summary:
            lines.append("## Executive Summary")
            lines.append("")
            lines.append(self.summary)
            lines.append("")

        # Key themes
        if self.key_themes:
            lines.append("## Key Themes")
            lines.append("")
            for i, theme in enumerate(self.key_themes, 1):
                lines.append(f"{i}. {theme}")
            lines.append("")

        # Findings by source type
        source_types = {}
        for finding in self.findings:
            source_type = finding.source.source_type
            if source_type not in source_types:
                source_types[source_type] = []
            source_types[source_type].append(finding)

        for source_type, findings in source_types.items():
            lines.append(f"## {source_type.title()} Sources")
            lines.append("")

            for i, finding in enumerate(findings, 1):
                lines.append(f"### Finding {i}: {finding.source.title}")
                lines.append(f"")
                lines.append(f"**Source:** [{finding.source.url}]({finding.source.url})")
                lines.append(f"**Confidence:** {finding.confidence:.2f}")
                lines.append(f"**Relevance:** {finding.source.relevance_score:.2f}")
                lines.append(f"")
                lines.append(finding.content[:500])
                if len(finding.content) > 500:
                    lines.append("...")
                lines.append("")

                if finding.key_points:
                    lines.append("**Key Points:**")
                    for point in finding.key_points:
                        lines.append(f"- {point}")
                    lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Statistics
        if self.statistics:
            lines.append("## Statistics")
            lines.append("")
            for key, value in self.statistics.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        return "\n".join(lines)


class ResearchAgent:
    """Flagship research orchestrator for comprehensive investigations."""

    def __init__(self):
        """Initialize research agent with all capabilities."""
        self.aggregator = SearchAggregator()
        self.hybrid_crawler = HybridCrawler()
        self.multi_crawler = MultiBrowserCrawler()
        self.reddit = RedditScraper()
        self.twitter = TwitterScraper()
        self.youtube = YouTubeScraper()
        self.github = GitHubScraper()
        self.summarizer = AISummarizer()
        self.deduplicator = ResultDeduplicator(similarity_threshold=0.75)

    def _calculate_confidence(
        self,
        source_type: str,
        content_length: int,
        has_title: bool,
        relevance_score: float,
    ) -> float:
        """Calculate confidence score for a finding.

        Factors:
        - Source type reliability
        - Content length
        - Title presence
        - Relevance score
        """
        # Base confidence by source type
        source_confidence = {
            "web": 0.7,
            "reddit": 0.6,
            "twitter": 0.5,
            "youtube": 0.6,
            "github": 0.8,
        }
        base = source_confidence.get(source_type, 0.5)

        # Content length bonus
        if content_length > 1000:
            base += 0.1
        elif content_length > 500:
            base += 0.05

        # Title bonus
        if has_title:
            base += 0.05

        # Relevance bonus
        base += relevance_score * 0.2

        return min(base, 1.0)

    def _extract_key_points(self, content: str, max_points: int = 5) -> list[str]:
        """Extract key points from content.

        Simple extraction based on sentence structure.
        """
        # Split by sentences
        sentences = content.replace("\n", " ").split(". ")
        # Filter short sentences
        key_points = [s.strip() for s in sentences if len(s) > 30 and len(s) < 200]
        return key_points[:max_points]

    async def investigate(
        self,
        topic: str,
        *,
        search_depth: Literal["shallow", "medium", "deep"] = "medium",
        include_social: bool = True,
        include_summary: bool = False,
        max_sources: int = 5,
        export_format: Literal["json", "markdown", "dict"] = "dict",
    ) -> dict[str, Any] | str:
        """Run comprehensive research investigation.

        Args:
            topic: Research topic
            search_depth: How deep to investigate
                - shallow: Search only
                - medium: Search + top result crawl
                - deep: Search + crawl multiple + social media
            include_social: Include social media (Reddit, Twitter, GitHub)
            include_summary: Include AI summary of findings
            max_sources: Max sources per category
            export_format: Output format (json, markdown, dict)

        Returns:
            Comprehensive research report with structured findings
        """
        logger.info(f"Starting research investigation: {topic}")

        # Clear deduplicator for new investigation
        self.deduplicator.clear()

        report = ResearchReport(
            topic=topic,
            timestamp=datetime.now().isoformat(),
            search_depth=search_depth,
        )

        # Phase 1: Web Search
        try:
            logger.info("Phase 1: Web Search")
            search_results = await self.aggregator.search(
                query=topic,
                max_results=max_sources * 2,
            )

            # Deduplicate search results
            self.deduplicator.add_results(search_results)
            unique_results = self.deduplicator.get_unique_results()

            # Rank by relevance
            ranked_results = self.deduplicator.rank_by_query(topic, unique_results)

            for ranked in ranked_results[:max_sources]:
                finding = ResearchFinding(
                    content=ranked.content or ranked.title,
                    source=SourceAttribution(
                        url=ranked.url,
                        title=ranked.title,
                        source_type="web",
                        relevance_score=ranked.score,
                        timestamp=datetime.now().isoformat(),
                        metadata=ranked.metadata,
                    ),
                    key_points=self._extract_key_points(ranked.content or ranked.title),
                    confidence=self._calculate_confidence(
                        "web",
                        len(ranked.content or ""),
                        bool(ranked.title),
                        ranked.score,
                    ),
                )
                report.findings.append(finding)

        except Exception as e:
            logger.error(f"Search error: {e}")

        # Phase 2: Content Crawling (based on depth)
        if search_depth in ("medium", "deep"):
            try:
                logger.info(f"Phase 2: Crawling content ({search_depth} mode)")
                crawl_tasks = []
                urls_to_crawl = []

                for finding in report.findings[:3]:
                    url = finding.source.url
                    if url:
                        urls_to_crawl.append(url)
                        if search_depth == "deep":
                            task = self.multi_crawler.crawl_with_fallback(url)
                        else:
                            task = self.hybrid_crawler.crawl(url)
                        crawl_tasks.append(task)

                if crawl_tasks:
                    crawl_results = await asyncio.gather(
                        *crawl_tasks,
                        return_exceptions=True,
                    )

                    for url, result in zip(urls_to_crawl, crawl_results):
                        if not isinstance(result, Exception):
                            # Extract content from crawl result
                            content = ""
                            if hasattr(result, "text"):
                                content = result.text
                            elif hasattr(result, "content"):
                                content = result.content
                            elif isinstance(result, dict):
                                content = result.get("content", "")

                            if content:
                                finding = ResearchFinding(
                                    content=content[:1000],
                                    source=SourceAttribution(
                                        url=url,
                                        title=getattr(result, "title", "") or "",
                                        source_type="web_crawled",
                                        relevance_score=0.8,
                                        timestamp=datetime.now().isoformat(),
                                    ),
                                    key_points=self._extract_key_points(content),
                                    confidence=self._calculate_confidence(
                                        "web",
                                        len(content),
                                        bool(getattr(result, "title", None)),
                                        0.8,
                                    ),
                                )
                                report.findings.append(finding)

            except Exception as e:
                logger.error(f"Crawl error: {e}")

        # Phase 3: Social Media Research
        if include_social:
            try:
                logger.info("Phase 3: Social Media Research")
                social_tasks = []

                # Reddit
                try:
                    reddit_results = await self.reddit.search(
                        query=topic,
                        limit=max_sources,
                    )
                    social_tasks.append(("reddit", reddit_results))
                except Exception as e:
                    logger.warning(f"Reddit search failed: {e}")

                # Twitter
                try:
                    twitter_results = await self.twitter.search(
                        query=topic,
                        limit=max_sources,
                    )
                    social_tasks.append(("twitter", twitter_results))
                except Exception as e:
                    logger.warning(f"Twitter search failed: {e}")

                # YouTube
                try:
                    youtube_results = await self.youtube.search(
                        query=topic,
                        limit=max_sources,
                    )
                    social_tasks.append(("youtube", youtube_results))
                except Exception as e:
                    logger.warning(f"YouTube search failed: {e}")

                # GitHub
                try:
                    github_results = await self.github.search_repos(
                        query=topic,
                        limit=max_sources,
                    )
                    social_tasks.append(("github", github_results))
                except Exception as e:
                    logger.warning(f"GitHub search failed: {e}")

                for platform, results in social_tasks:
                    if results:
                        # Handle different result formats
                        items = []
                        if hasattr(results, "posts"):
                            items = results.posts
                        elif hasattr(results, "tweets"):
                            items = results.tweets
                        elif hasattr(results, "videos"):
                            items = results.videos
                        elif isinstance(results, list):
                            items = results

                        for item in items[:max_sources]:
                            # Extract content based on platform
                            content = ""
                            title = ""
                            url = ""

                            if platform == "reddit":
                                title = getattr(item, "title", "")
                                content = getattr(item, "selftext", "") or title
                                url = f"https://reddit.com{getattr(item, 'permalink', '')}"
                            elif platform == "twitter":
                                content = getattr(item, "text", "")
                                title = content[:100]
                                url = getattr(item, "url", "")
                            elif platform == "youtube":
                                title = getattr(item, "title", "")
                                content = getattr(item, "description", "") or title
                                url = f"https://youtube.com/watch?v={getattr(item, 'video_id', '')}"
                            elif platform == "github":
                                title = getattr(item, "full_name", "")
                                content = getattr(item, "description", "") or title
                                url = getattr(item, "html_url", "")

                            if content:
                                finding = ResearchFinding(
                                    content=content[:500],
                                    source=SourceAttribution(
                                        url=url,
                                        title=title,
                                        source_type=platform,
                                        relevance_score=0.7,
                                        timestamp=datetime.now().isoformat(),
                                    ),
                                    key_points=self._extract_key_points(content),
                                    confidence=self._calculate_confidence(
                                        platform,
                                        len(content),
                                        bool(title),
                                        0.7,
                                    ),
                                )
                                report.findings.append(finding)

            except Exception as e:
                logger.error(f"Social media research error: {e}")

        # Phase 4: AI Summarization (optional)
        if include_summary:
            try:
                logger.info("Phase 4: AI Summarization")
                # Prepare content for summarization
                content_to_summarize = "\n\n".join([
                    f"Source: {f.source.title}\n{f.content[:300]}"
                    for f in report.findings[:10]
                ])

                summary = await self.summarizer.summarize(content_to_summarize)
                report.summary = summary
            except Exception as e:
                logger.warning(f"Summarization error: {e}")

        # Extract key themes from all findings
        all_content = " ".join([f.content for f in report.findings])
        words = all_content.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 5:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get top themes
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        report.key_themes = [word for word, _ in sorted_words[:10]]

        # Generate recommendations
        report.recommendations = [
            f"Review top findings from {len(report.findings)} sources",
            f"Focus on {report.key_themes[0] if report.key_themes else 'key themes'} for deeper analysis",
            "Cross-reference findings across multiple sources for validation",
        ]

        # Calculate statistics
        source_counts = {}
        for finding in report.findings:
            source_type = finding.source.source_type
            source_counts[source_type] = source_counts.get(source_type, 0) + 1

        report.statistics = {
            "total_findings": len(report.findings),
            "sources_by_type": source_counts,
            "average_confidence": sum(f.confidence for f in report.findings) / len(report.findings) if report.findings else 0,
            "search_depth": search_depth,
        }

        logger.info(f"Research complete: {topic}")

        # Export based on format
        if export_format == "json":
            return report.to_json()
        elif export_format == "markdown":
            return report.to_markdown()
        else:
            return report.to_dict()

    async def compare(
        self,
        topics: list[str],
        *,
        search_depth: Literal["shallow", "medium"] = "shallow",
        max_sources: int = 3,
    ) -> dict[str, Any]:
        """Compare multiple topics side-by-side.

        Args:
            topics: List of topics to compare
            search_depth: Comparison depth
            max_sources: Max sources per topic

        Returns:
            Comparison report with findings for each topic
        """
        logger.info(f"Starting comparison: {topics}")

        # Run investigations in parallel
        tasks = [
            self.investigate(
                topic,
                search_depth=search_depth,
                include_social=False,
                max_sources=max_sources,
            )
            for topic in topics
        ]

        reports = await asyncio.gather(*tasks)

        return {
            "comparison": topics,
            "reports": {
                topic: report
                for topic, report in zip(topics, reports)
            },
        }

    async def trending(
        self,
        *,
        platforms: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get trending topics/content from social platforms.

        Args:
            platforms: Platforms to check (reddit, twitter, youtube, github)
            limit: Results per platform

        Returns:
            Trending content report
        """
        if platforms is None:
            platforms = ["reddit", "twitter", "github"]

        logger.info(f"Checking trending on: {platforms}")

        trending = {}

        if "reddit" in platforms:
            try:
                # Reddit trending subreddits
                trending["reddit"] = await self.reddit.get_subreddit(
                    subreddit="trending",
                    limit=limit,
                )
            except Exception as e:
                logger.warning(f"Reddit trending failed: {e}")

        if "github" in platforms:
            try:
                # GitHub trending repos
                trending["github"] = await self.github.search_repos(
                    query="language:*",
                    sort="stars",
                    limit=limit,
                )
            except Exception as e:
                logger.warning(f"GitHub trending failed: {e}")

        return {"trending": trending}


# Singleton instance
_instance: ResearchAgent | None = None


def get_research_agent() -> ResearchAgent:
    """Get or create research agent singleton."""
    global _instance
    if _instance is None:
        _instance = ResearchAgent()
    return _instance
