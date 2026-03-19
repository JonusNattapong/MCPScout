"""CLI entry point for MCPScout."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MCPScout - AI-powered multi-source intelligence platform",
    )
    parser.add_argument(
        "command",
        choices=["server", "search", "crawl", "read"],
        help="Command to run",
    )
    parser.add_argument(
        "--query", "-q",
        help="Search query",
    )
    parser.add_argument(
        "--url", "-u",
        nargs="+",
        help="URL(s) to crawl or read",
    )
    parser.add_argument(
        "--sources", "-s",
        nargs="+",
        default=["duckduckgo"],
        help="Search sources to use",
    )
    parser.add_argument(
        "--max-results", "-n",
        type=int,
        default=10,
        help="Maximum number of results",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json", "markdown"],
        default="markdown",
        help="Output format",
    )

    args = parser.parse_args()

    if args.command == "server":
        # Run MCP server (blocking call)
        from mcpspider.mcp_server.server import main as server_main
        server_main()
    elif args.command == "search":
        asyncio.run(run_search(args))
    elif args.command == "crawl":
        asyncio.run(run_crawl(args))
    elif args.command == "read":
        asyncio.run(run_read(args))


async def run_search(args):
    """Run search command."""
    import json
    from mcpspider.search.aggregator import SearchAggregator

    if not args.query:
        print("Error: --query is required for search command", file=sys.stderr)
        sys.exit(1)

    aggregator = SearchAggregator(engines=args.sources)
    results = await aggregator.search(args.query, max_results=args.max_results)

    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.format == "text":
        for r in results:
            print(f"{r['rank']}. {r['title']}")
            print(f"   URL: {r['url']}")
            if r.get("snippet"):
                print(f"   {r['snippet'][:100]}...")
            print()
    else:  # markdown
        print(f"# Search Results: {args.query}\n")
        for r in results:
            print(f"### {r['rank']}. {r['title']}")
            print(f"**URL:** {r['url']}")
            if r.get("snippet"):
                print(f"\n{r['snippet']}\n")

    await aggregator.close()


async def run_crawl(args):
    """Run crawl command."""
    from mcpspider.crawler.engine import CrawlerEngine

    if not args.url:
        print("Error: --url is required for crawl command", file=sys.stderr)
        sys.exit(1)

    crawler = CrawlerEngine()

    # Handle multiple URLs
    urls = args.url if isinstance(args.url, list) else [args.url]

    if len(urls) == 1:
        result = await crawler.crawl(urls[0], extract_mode="markdown")
        print(result)
    else:
        results = await crawler.crawl_multiple(urls, extract_mode="markdown")
        for r in results:
            print(f"# {r.get('title', 'No title')}\n")
            print(f"**URL:** {r.get('url', '')}\n")
            print(r.get("content", "")[:2000])
            print("\n" + "=" * 60 + "\n")


async def run_read(args):
    """Run read command - just view webpage content in terminal."""
    import httpx
    from mcpspider.crawler.extractor import ContentExtractor

    if not args.url:
        print("Error: --url is required for read command", file=sys.stderr)
        sys.exit(1)

    extractor = ContentExtractor()
    urls = args.url if isinstance(args.url, list) else [args.url]

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        for i, url in enumerate(urls):
            try:
                response = await client.get(url, headers={"User-Agent": "MCPScout/1.0.0"})
                response.raise_for_status()
                content = extractor.extract(response.text, base_url=url)

                # Header for multiple URLs
                if len(urls) > 1:
                    print(f"\n{'=' * 60}")
                    print(f"[{i+1}/{len(urls)}]")
                    print("=" * 60)

                # Display based on format
                if args.format == "text":
                    print(f"Title: {content.title}")
                    print(f"URL: {url}")
                    print(f"Words: {content.word_count}")
                    print("-" * 40)
                    print(content.text[:5000])
                else:  # markdown
                    print(f"# {content.title}\n")
                    print(f"**URL:** {url} | **Words:** {content.word_count}")
                    print()

                    if content.tables:
                        print("## Tables\n")
                        for t in content.tables:
                            print(t.to_markdown())
                            print()

                    if content.code_blocks:
                        print("## Code\n")
                        for code in content.code_blocks[:3]:
                            lang = code.language or ""
                            print(f"```{lang}")
                            print(code.code[:500])
                            print("```\n")

                    print("## Content\n")
                    print(content.text[:3000])

            except Exception as e:
                print(f"Error reading {url}: {e}")

            if i < len(urls) - 1:
                print("\n")


if __name__ == "__main__":
    main()
