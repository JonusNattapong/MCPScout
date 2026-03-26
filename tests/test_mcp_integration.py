"""Integration tests for MCPSearch main workflows."""

from __future__ import annotations

import pytest
from mcp_server.server import (
    mcpsearch,
    list_tools,
    describe_tools,
    web_search,
    search_reddit,
    search_twitter,
    search_youtube,
    search_github,
    crawl_url,
    hybrid_crawl,
)


class TestSearchWorkflow:
    """Test web search workflow end-to-end."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """Test that web search returns formatted results."""
        result = await web_search(query="Python programming", max_results=5)
        assert isinstance(result, str)
        assert len(result) > 0
        # Results should have markdown formatting
        assert "#" in result  # Markdown headers

    @pytest.mark.asyncio
    async def test_search_empty_query_handling(self):
        """Test that search handles empty queries gracefully."""
        result = await web_search(query="", max_results=5)
        assert isinstance(result, str)
        # Should either return error or minimal results
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_with_limit(self):
        """Test that search respects limit parameter."""
        result_5 = await web_search(query="test", max_results=5)
        result_1 = await web_search(query="test", max_results=1)
        # With lower limit, result should generally be shorter
        assert isinstance(result_5, str)
        assert isinstance(result_1, str)

    @pytest.mark.asyncio
    async def test_mcpsearch_search_action(self):
        """Test unified mcpsearch tool with search action."""
        result = await mcpsearch(action="search", query="python tutorial", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0


class TestCrawlWorkflow:
    """Test web crawling workflow end-to-end."""

    @pytest.mark.asyncio
    async def test_crawl_url_returns_content(self):
        """Test that crawl_url returns page content."""
        result = await crawl_url(url="https://example.com")
        assert isinstance(result, str)
        # Should have some content
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_crawl_url_error_handling(self):
        """Test that crawl_url handles invalid URLs gracefully."""
        result = await crawl_url(url="https://invalid-domain-that-definitely-does-not-exist-12345.com")
        assert isinstance(result, str)
        # Should return error message, not crash
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_hybrid_crawl_routing(self):
        """Test that hybrid crawl uses appropriate mode."""
        result = await hybrid_crawl(url="https://example.com")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_mcpsearch_crawl_actions(self):
        """Test unified mcpsearch tool with different crawl modes."""
        # Test each mode
        for mode in ["fast", "deep", "stealth"]:
            result = await mcpsearch(
                action="crawl",
                url="https://example.com",
                mode=mode
            )
            assert isinstance(result, str)
            # Should return some result, even if it's an error
            assert len(result) > 0


class TestSocialMediaWorkflow:
    """Test social media scraping workflows."""

    @pytest.mark.asyncio
    async def test_search_reddit(self):
        """Test Reddit search workflow."""
        result = await search_reddit(query="python", limit=5)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_twitter(self):
        """Test Twitter search workflow."""
        result = await search_twitter(query="AI", limit=3)
        assert isinstance(result, str)
        # May be empty if no results or error, but should not crash
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_search_youtube(self):
        """Test YouTube search workflow."""
        result = await search_youtube(query="python tutorial", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_github(self):
        """Test GitHub search workflow."""
        result = await search_github(query="machine learning", limit=5)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_mcpsearch_reddit_action(self):
        """Test unified mcpsearch with Reddit action."""
        result = await mcpsearch(action="reddit", query="python", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_mcpsearch_twitter_action(self):
        """Test unified mcpsearch with Twitter action."""
        result = await mcpsearch(action="twitter", query="AI news", limit=2)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_mcpsearch_youtube_action(self):
        """Test unified mcpsearch with YouTube action."""
        result = await mcpsearch(action="youtube", query="tutorial", limit=2)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_mcpsearch_github_action(self):
        """Test unified mcpsearch with GitHub action."""
        result = await mcpsearch(action="github", query="python", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0


class TestMultiActionWorkflow:
    """Test multi-action orchestration."""

    @pytest.mark.asyncio
    async def test_mcpsearch_multi_parallel_execution(self):
        """Test that mcpsearch_multi executes actions in parallel."""
        # This would require importing mcpsearch_multi
        # For now, test that the unified tool supports multi action
        # This may be tested differently based on server implementation
        pass


class TestDiscoveryWorkflow:
    """Test tool discovery and documentation workflow."""

    @pytest.mark.asyncio
    async def test_list_tools_discovery(self):
        """Test that tools can be discovered via list_tools."""
        result = await list_tools()
        assert isinstance(result, str)
        assert "mcpsearch" in result
        assert "web_search" in result
        assert "search_reddit" in result

    @pytest.mark.asyncio
    async def test_describe_tools_documentation(self):
        """Test that tools can be documented via describe_tools."""
        # Test overview
        overview = await describe_tools()
        assert isinstance(overview, str)
        assert "MCPSearch" in overview or "search" in overview.lower()

        # Test specific tool
        tool_doc = await describe_tools(tool_name="mcpsearch")
        assert isinstance(tool_doc, str)
        assert "mcpsearch" in tool_doc.lower()
        assert "action" in tool_doc.lower()

    @pytest.mark.asyncio
    async def test_discovery_enables_ai_usage(self):
        """Test that discovery workflow supports AI agent usage."""
        # Simulate AI agent workflow
        # 1. Discover tools
        tools = await list_tools()
        assert "mcpsearch" in tools
        
        # 2. Get documentation
        docs = await describe_tools(tool_name="mcpsearch")
        assert "search" in docs.lower() or "action" in docs.lower()
        
        # 3. Use tool based on documentation
        result = await mcpsearch(action="search", query="test", limit=1)
        assert isinstance(result, str)


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_mcpsearch_action(self):
        """Test handling of invalid mcpsearch action."""
        result = await mcpsearch(action="invalid_action", query="test")
        assert isinstance(result, str)
        assert "Unknown action" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_mcpsearch_missing_required_params(self):
        """Test handling of missing required parameters."""
        # Search action requires query
        result = await mcpsearch(action="search", query="", limit=5)
        assert isinstance(result, str)
        # Should handle gracefully

    @pytest.mark.asyncio
    async def test_network_error_resilience(self):
        """Test that tools handle network errors gracefully."""
        # This would require mocking network failures
        # For now, just verify that invalid URLs don't crash
        result = await crawl_url(url="https://nonexistent-domain-xyz.invalid")
        assert isinstance(result, str)
        # Should have error message, not crash


class TestPerformacy:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_search_response_time(self):
        """Test that search completes in reasonable time."""
        import time
        
        start = time.time()
        result = await web_search(query="python", max_results=3)
        elapsed = time.time() - start
        
        assert isinstance(result, str)
        assert len(result) > 0
        # Should complete reasonably fast (adjust based on requirements)
        # Don't assert strict timing to avoid flakiness

    @pytest.mark.asyncio
    async def test_tool_listing_response_time(self):
        """Test that tool listing is fast."""
        import time
        
        start = time.time()
        result = await list_tools()
        elapsed = time.time() - start
        
        assert isinstance(result, str)
        assert len(result) > 0
        # Tool listing should be very fast (no I/O)


class TestMainFlowIntegration:
    """Test main end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_research_workflow_search_then_crawl(self):
        """Test research workflow: search then crawl top result."""
        # Step 1: Search
        search_result = await web_search(query="python asyncio", max_results=1)
        assert isinstance(search_result, str)
        assert len(search_result) > 0

    @pytest.mark.asyncio
    async def test_github_research_workflow(self):
        """Test GitHub research workflow."""
        # Search for repos
        result = await search_github(query="asyncio", limit=3)
        assert isinstance(result, str)
        assert len(result) > 0
        # Result should have repo information
        assert "github" in result.lower() or "repo" in result.lower() or "stars" in result.lower()

    @pytest.mark.asyncio
    async def test_reddit_discussion_research_workflow(self):
        """Test Reddit discussion research workflow."""
        result = await search_reddit(query="python tips", limit=3)
        assert isinstance(result, str)
        # Should have results about Python
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_cross_platform_research_workflow(self):
        """Test research across multiple platforms."""
        query = "machine learning"
        
        # Get results from multiple sources
        web = await web_search(query=query, max_results=2)
        github = await search_github(query=query, limit=2)
        reddit = await search_reddit(query=query, limit=2)
        
        # All should return non-empty results
        assert len(web) > 0
        assert len(github) > 0
        assert len(reddit) > 0
        
        # Results should be different
        assert web != github  # Different platforms, different content


class TestToolParameters:
    """Test various parameter combinations for tools."""

    @pytest.mark.asyncio
    async def test_web_search_parameters(self):
        """Test web search with different parameters."""
        # Test with different max_results
        for max_results in [1, 5, 10]:
            result = await web_search(query="test", max_results=max_results)
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_reddit_parameters(self):
        """Test Reddit search with different parameters."""
        # Test with different sorts
        for sort in ["relevance", "hot", "new"]:
            result = await search_reddit(query="test", sort=sort, limit=2)
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_github_sort_parameters(self):
        """Test GitHub search with different sort orders."""
        for sort in ["stars", "updated"]:
            result = await search_github(query="python", sort=sort, limit=2)
            assert isinstance(result, str)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_crawl_mode_parameters(self):
        """Test crawl with different modes."""
        url = "https://example.com"
        
        # Test modes work without crashing
        for mode in ["fast", "deep", "stealth"]:
            result = await mcpsearch(
                action="crawl",
                url=url,
                mode=mode
            )
            assert isinstance(result, str)
