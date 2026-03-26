#!/usr/bin/env python3
"""Small benchmark helpers for search parsing and hybrid crawl rendering.

This script compares:
1. BeautifulSoup vs selectolax parsing on representative search-result HTML
2. Hybrid Playwright rendering with resource blocking disabled vs enabled

The crawl benchmark is optional and runs only when --url is provided.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from crawler.hybrid import PlaywrightRenderer
    from search.aggregator import BingEngine, DuckDuckGoEngine, GoogleEngine
except ModuleNotFoundError as exc:
    missing_module = exc.name or "unknown"
    print(
        "Missing runtime dependency for benchmarks: "
        f"{missing_module}. Install project dependencies first, for example:\n"
        '  pip install -e ".[dev]"\n'
        "  playwright install chromium"
    )
    raise SystemExit(1) from exc


SEARCH_HTML = {
    "duckduckgo": """
    <div class="result__body">
      <div class="result__title"><a href="https://example.com/a">Result A</a></div>
      <div class="result__snippet">Snippet A</div>
    </div>
    <div class="result__body">
      <div class="result__title"><a href="https://example.com/b">Result B</a></div>
      <div class="result__snippet">Snippet B</div>
    </div>
    """,
    "google": """
    <div class="g">
      <a href="https://example.com/a"><h3>Result A</h3></a>
      <div class="VwiC3b">Snippet A</div>
    </div>
    <div class="g">
      <a href="https://example.com/b"><h3>Result B</h3></a>
      <div class="VwiC3b">Snippet B</div>
    </div>
    """,
    "bing": """
    <li class="b_algo">
      <h2><a href="https://example.com/a">Result A</a></h2>
      <div class="b_caption"><p>Snippet A</p></div>
    </li>
    <li class="b_algo">
      <h2><a href="https://example.com/b">Result B</a></h2>
      <div class="b_caption"><p>Snippet B</p></div>
    </li>
    """,
}


@dataclass
class DummyClient:
    """Minimal client placeholder for parser benchmarks."""


def _benchmark_parser(fn, html: str, iterations: int) -> float:
    """Return average parse time in milliseconds."""
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn(html, 10)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.mean(samples)


def run_search_benchmark(iterations: int) -> None:
    """Benchmark parser methods on representative HTML."""
    print("== Search parser benchmark ==")

    cases = [
        ("duckduckgo", DuckDuckGoEngine(DummyClient())),
        ("google", GoogleEngine(DummyClient())),
        ("bing", BingEngine(DummyClient())),
    ]

    for name, engine in cases:
        html = SEARCH_HTML[name]
        bs4_time = _benchmark_parser(engine._parse_beautifulsoup, html, iterations)
        line = f"{name}: BeautifulSoup={bs4_time:.3f}ms"

        if hasattr(engine, "_parse_selectolax"):
            try:
                selectolax_time = _benchmark_parser(engine._parse_selectolax, html, iterations)
                speedup = bs4_time / selectolax_time if selectolax_time else 0.0
                line += f" | selectolax={selectolax_time:.3f}ms | speedup={speedup:.2f}x"
            except Exception as exc:
                line += f" | selectolax unavailable ({exc})"

        print(line)


async def _run_render(url: str, block_resources: bool) -> float:
    """Run one Playwright render and return load time in milliseconds."""
    renderer = PlaywrightRenderer(block_resources=block_resources)
    try:
        result = await renderer.render(url)
        return result.load_time_ms
    finally:
        await renderer.close()


async def run_crawl_benchmark(url: str, iterations: int) -> None:
    """Benchmark blocked vs unblocked hybrid render path."""
    print("\n== Hybrid crawl benchmark ==")
    print(f"Target URL: {url}")

    blocked = []
    unblocked = []

    for _ in range(iterations):
        unblocked.append(await _run_render(url, block_resources=False))
        blocked.append(await _run_render(url, block_resources=True))

    avg_unblocked = statistics.mean(unblocked)
    avg_blocked = statistics.mean(blocked)
    improvement = avg_unblocked - avg_blocked
    ratio = avg_unblocked / avg_blocked if avg_blocked else 0.0

    print(f"unblocked avg: {avg_unblocked:.2f}ms")
    print(f"blocked avg:   {avg_blocked:.2f}ms")
    print(f"delta:         {improvement:.2f}ms")
    print(f"speedup:       {ratio:.2f}x")


def main() -> None:
    """Run configured benchmarks."""
    parser = argparse.ArgumentParser(description="Benchmark MCPSearch search/crawl improvements")
    parser.add_argument("--url", help="Optional URL for live Playwright crawl benchmark")
    parser.add_argument("--iterations", type=int, default=20, help="Iterations per benchmark")
    args = parser.parse_args()

    run_search_benchmark(args.iterations)

    if args.url:
        asyncio.run(run_crawl_benchmark(args.url, max(1, min(args.iterations, 5))))
    else:
        print("\nHybrid crawl benchmark skipped. Pass --url to run a live before/after render test.")


if __name__ == "__main__":
    main()
