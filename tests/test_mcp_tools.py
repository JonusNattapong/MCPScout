"""Test new MCPSearch tools for AI usage ease."""

from __future__ import annotations

import pytest
from mcp_server.server import mcp, list_tools, describe_tools, mcpsearch


class TestListTools:
    """Test list_tools() function."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_string(self):
        """Test that list_tools returns a string."""
        result = await list_tools()
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_list_tools_contains_tool_names(self):
        """Test that list_tools contains expected tool names."""
        result = await list_tools()
        
        # Check for key tools
        assert "web_search" in result
        assert "search_and_summarize" in result
        assert "smart_search" in result
        assert "deep_search" in result
        assert "crawl_url" in result
        assert "hybrid_crawl" in result
        assert "crawl_recursive" in result
        assert "extract_content" in result
        assert "mcpsearch" in result
        assert "mcpsearch_multi" in result
        assert "search_reddit" in result
        assert "search_twitter" in result
        assert "search_youtube" in result
        assert "search_github" in result
        assert "list_tools" in result
        assert "describe_tools" in result

    @pytest.mark.asyncio
    async def test_list_tools_format(self):
        """Test that list_tools has proper markdown format."""
        result = await list_tools()
        
        # Should have markdown headers
        assert "# MCPSearch Available Tools" in result
        assert "## Quick Start" in result
        
        # Should have bullet points with tool names
        assert "- **web_search**:" in result
        assert "- **mcpsearch**:" in result

    @pytest.mark.asyncio
    async def test_list_tools_descriptions(self):
        """Test that list_tools includes descriptions."""
        result = await list_tools()
        
        # Check for key descriptions
        assert "Search multiple websites in parallel" in result
        assert "All-in-one intelligence tool" in result
        assert "Search, crawl, and AI-summarize" in result


class TestDescribeTools:
    """Test describe_tools() function."""

    @pytest.mark.asyncio
    async def test_describe_tools_no_params(self):
        """Test describe_tools without parameters returns overview."""
        result = await describe_tools()
        assert isinstance(result, str)
        
        # Should have overview sections
        assert "# MCPSearch Tools Overview" in result
        assert "## Web Search & Research" in result
        assert "## Web Crawling" in result
        assert "## Unified Interface" in result
        assert "## Social Media" in result
        assert "## Utilities" in result

    @pytest.mark.asyncio
    async def test_describe_tools_specific_tool(self):
        """Test describe_tools with specific tool name."""
        result = await describe_tools(tool_name="web_search")
        assert isinstance(result, str)
        
        # Should have detailed documentation
        assert "# web_search" in result
        assert "**Description:**" in result
        assert "## Parameters" in result
        assert "## Example" in result
        
        # Should have parameter table
        assert "| Name | Type | Description |" in result
        assert "| query | `str` | Search query to execute |" in result

    @pytest.mark.asyncio
    async def test_describe_tools_scout_with_mode(self):
        """Test describe_tools for mcpsearch tool with mode parameter."""
        result = await describe_tools(tool_name="mcpsearch")
        assert isinstance(result, str)
        
        # Should document the mode parameter
        assert "mode" in result
        assert "fast (httpx)" in result or "fast" in result
        assert "deep (hybrid)" in result or "deep" in result
        assert "stealth (anti-bot bypass)" in result or "stealth" in result

    @pytest.mark.asyncio
    async def test_describe_tools_nonexistent_tool(self):
        """Test describe_tools with non-existent tool name."""
        result = await describe_tools(tool_name="nonexistent_tool")
        assert isinstance(result, str)
        assert "not found" in result.lower()
        assert "list_tools()" in result

    @pytest.mark.asyncio
    async def test_describe_tools_all_major_tools(self):
        """Test that describe_tools works for all major tools."""
        major_tools = [
            "web_search",
            "search_and_summarize",
            "smart_search",
            "deep_search",
            "crawl_url",
            "hybrid_crawl",
            "crawl_recursive",
            "extract_content",
            "mcpsearch",
            "mcpsearch_multi",
            "search_reddit",
            "search_twitter",
            "search_youtube",
            "search_github",
            "get_crawl_stats",
        ]
        
        for tool_name in major_tools:
            result = await describe_tools(tool_name=tool_name)
            assert isinstance(result, str)
            assert f"# {tool_name}" in result
            assert "**Description:**" in result


class TestMcpsearchWithMode:
    """Test mcpsearch tool with mode parameter."""
    async def test_scout_search_action(self):
        """Test mcpsearch with search action."""
        result = await mcpsearch(action="search", query="test query", limit=5)
        assert isinstance(result, str)
        # Should contain search results or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_crawl_fast_mode(self):
        """Test mcpsearch with crawl action in fast mode."""
        result = await mcpsearch(action="crawl", url="https://example.com", mode="fast")
        assert isinstance(result, str)
        # Should return content or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_crawl_deep_mode(self):
        """Test mcpsearch with crawl action in deep mode."""
        result = await mcpsearch(action="crawl", url="https://example.com", mode="deep")
        assert isinstance(result, str)
        # Should return content or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_crawl_stealth_mode(self):
        """Test mcpsearch with crawl action in stealth mode."""
        result = await mcpsearch(action="crawl", url="https://example.com", mode="stealth")
        assert isinstance(result, str)
        # Should return content or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_crawl_default_mode(self):
        """Test mcpsearch with crawl action without specifying mode."""
        result = await mcpsearch(action="crawl", url="https://example.com")
        assert isinstance(result, str)
        # Should return content or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_reddit_action(self):
        """Test mcpsearch with reddit action."""
        result = await mcpsearch(action="reddit", query="python", limit=5)
        assert isinstance(result, str)
        # Should return reddit results or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_twitter_action(self):
        """Test mcpsearch with twitter action."""
        result = await mcpsearch(action="twitter", query="test", limit=5)
        assert isinstance(result, str)
        # Should return twitter results or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_youtube_action(self):
        """Test mcpsearch with youtube action."""
        result = await mcpsearch(action="youtube", query="python tutorial", limit=5)
        assert isinstance(result, str)
        # Should return youtube results or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_github_action(self):
        """Test mcpsearch with github action."""
        result = await mcpsearch(action="github", query="machine learning", limit=5)
        assert isinstance(result, str)
        # Should return github results or error message
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_scout_invalid_action(self):
        """Test mcpsearch with invalid action."""
        result = await mcpsearch(action="invalid_action")
        assert isinstance(result, str)
        assert "Unknown action" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_scout_mode_documentation(self):
        """Test that mcpsearch mode parameter is properly documented."""
        result = await describe_tools(tool_name="mcpsearch")
        
        # Mode parameter should be documented
        assert "mode" in result
        # Should mention the three modes
        assert "fast" in result
        assert "deep" in result
        assert "stealth" in result


class TestMCPToolRegistration:
    """Test that tools are properly registered with MCP."""

    def test_list_tools_registered(self):
        """Test that list_tools is registered as an MCP tool."""
        # Check if the tool is registered
        tools = mcp._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        assert "list_tools" in tool_names

    def test_describe_tools_registered(self):
        """Test that describe_tools is registered as an MCP tool."""
        tools = mcp._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        assert "describe_tools" in tool_names

    def test_scout_registered(self):
        """Test that mcpsearch is registered as an MCP tool."""
        tools = mcp._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        assert "mcpsearch" in tool_names

    def test_all_expected_tools_registered(self):
        """Test that all expected tools are registered."""
        tools = mcp._tool_manager.list_tools()
        tool_names = [tool.name for tool in tools]
        
        expected_tools = [
            "web_search",
            "search_and_summarize",
            "smart_search",
            "deep_search",
            "crawl_url",
            "hybrid_crawl",
            "crawl_recursive",
            "extract_content",
            "mcpsearch",
            "mcpsearch_multi",
            "search_reddit",
            "get_subreddit",
            "get_reddit_post",
            "search_twitter",
            "get_user_tweets",
            "search_youtube",
            "get_youtube_channel",
            "get_youtube_content",
            "search_github",
            "get_github_user",
            "get_github_repo",
            "get_github_readme",
            "get_crawl_stats",
            "list_tools",
            "describe_tools",
        ]
        
        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not registered"


class TestIntegration:
    """Integration tests for the new tools."""

    @pytest.mark.asyncio
    async def test_list_tools_then_describe(self):
        """Test using list_tools then describe_tools workflow."""
        # First, list all tools
        list_result = await list_tools()
        assert "mcpsearch" in list_result
        
        # Then, describe a specific tool
        describe_result = await describe_tools(tool_name="mcpsearch")
        assert "# mcpsearch" in describe_result
        assert "mode" in describe_result

    @pytest.mark.asyncio
    async def test_scout_mode_workflow(self):
        """Test mcpsearch mode parameter workflow."""
        # Test that mode parameter is accepted and documented
        describe_result = await describe_tools(tool_name="mcpsearch")
        
        # Verify mode parameter is documented
        assert "mode" in describe_result
        assert "fast" in describe_result
        assert "deep" in describe_result
        assert "stealth" in describe_result
        
        # Test that mcpsearch accepts mode parameter
        result = await mcpsearch(action="crawl", url="https://example.com", mode="fast")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_ai_discovery_workflow(self):
        """Test AI discovery workflow using list_tools and describe_tools."""
        # AI discovers available tools
        list_result = await list_tools()
        assert "## Quick Start" in list_result
        
        # AI gets details on specific tool
        describe_result = await describe_tools(tool_name="mcpsearch")
        assert "## Parameters" in describe_result
        assert "## Example" in describe_result
        
        # AI uses the tool with documented parameters
        result = await mcpsearch(action="search", query="test", limit=5)
        assert isinstance(result, str)
