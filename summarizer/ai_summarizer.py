"""AI-powered summarizer for search results."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class AISummarizer:
    """Summarize search results using AI (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                logger.error("openai package not installed")
                raise
        return self._client

    async def summarize(
        self,
        query: str,
        sources: list[dict[str, Any]],
        length: str = "detailed",
    ) -> str:
        """Summarize search results based on query."""
        if not self.api_key:
            return self._fallback_summarize(query, sources)

        length_instructions = {
            "brief": "a brief 2-3 sentence summary",
            "detailed": "a detailed paragraph with key points",
            "comprehensive": "a comprehensive multi-paragraph analysis",
        }

        instruction = length_instructions.get(length, length_instructions["detailed"])

        # Build context from sources
        context = self._build_context(sources)

        prompt = f"""Based on the following search results, provide {instruction} that answers the user's question.

Question: {query}

Search Results:
{context}

Provide a well-structured answer based ONLY on the information in the search results. 
If the search results don't contain relevant information, say so.
Include key facts and details from the sources.
"""

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful research assistant that synthesizes information from multiple sources into clear, accurate answers."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=self._get_max_tokens(length),
            )

            return response.choices[0].message.content or "No summary generated."

        except Exception as e:
            logger.error(f"AI summarization error: {e}")
            return self._fallback_summarize(query, sources)

    def _build_context(self, sources: list[dict[str, Any]]) -> str:
        """Build context string from crawled sources."""
        parts = []
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Unknown")
            url = source.get("url", "")
            content = source.get("content", "")

            # Limit content length per source
            if len(content) > 2000:
                content = content[:2000] + "..."

            parts.append(f"Source {i}: {title}")
            parts.append(f"URL: {url}")
            parts.append(f"Content: {content}")
            parts.append("")

        return "\n".join(parts)

    def _get_max_tokens(self, length: str) -> int:
        """Get max tokens based on summary length."""
        return {
            "brief": 200,
            "detailed": 500,
            "comprehensive": 1000,
        }.get(length, 500)

    def _fallback_summarize(self, query: str, sources: list[dict[str, Any]]) -> str:
        """Fallback summarization without AI."""
        if not sources:
            return f"No information found for query: {query}"

        lines = [f"## Search Results for: {query}\n"]
        lines.append(f"Found {len(sources)} sources:\n")

        for i, source in enumerate(sources, 1):
            title = source.get("title", "Unknown")
            url = source.get("url", "")
            content = source.get("content", "")

            # Extract first 500 chars of content
            if len(content) > 500:
                content = content[:500] + "..."

            lines.append(f"### {i}. {title}")
            lines.append(f"**URL:** {url}")
            lines.append(f"{content}\n")

        return "\n".join(lines)
