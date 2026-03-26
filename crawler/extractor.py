"""Advanced content extractor for web pages.

Extracts structured content including:
- Tables (as markdown)
- Code blocks (with language detection)
- Images (with metadata)
- JSON-LD structured data
- Microdata, RDFa, OpenGraph, Dublin Core
- Article content (main body)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag, NavigableString

try:
    import extruct
    HAS_EXTRUCT = True
except ImportError:
    HAS_EXTRUCT = False


@dataclass
class ExtractedTable:
    """A extracted table with headers and rows."""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        if not self.headers and not self.rows:
            return ""

        lines = []
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        for row in self.rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)


@dataclass
class ExtractedCode:
    """A extracted code block."""
    code: str
    language: str = ""
    filename: str = ""


@dataclass
class ExtractedImage:
    """An extracted image."""
    src: str
    alt: str = ""
    title: str = ""
    width: str = ""
    height: str = ""


@dataclass
class StructuredData:
    """Extracted structured data (JSON-LD, microdata)."""
    data: dict[str, Any] = field(default_factory=dict)
    type: str = ""


@dataclass
class ExtractedContent:
    """Comprehensive extracted content from a web page."""
    # Main content
    title: str = ""
    text: str = ""
    markdown: str = ""

    # Structured elements
    tables: list[ExtractedTable] = field(default_factory=list)
    code_blocks: list[ExtractedCode] = field(default_factory=list)
    images: list[ExtractedImage] = field(default_factory=list)
    structured_data: list[StructuredData] = field(default_factory=list)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)

    # Summary stats
    word_count: int = 0
    reading_time_minutes: float = 0.0


class ContentExtractor:
    """Advanced content extractor for web pages."""

    # CSS selectors for main content areas
    CONTENT_SELECTORS = [
        "article",
        "main",
        "[role='main']",
        ".post-content",
        ".article-content",
        ".entry-content",
        ".content",
        "#content",
    ]

    # Selectors to remove
    NOISE_SELECTORS = [
        "script", "style", "nav", "footer", "header",
        ".sidebar", ".advertisement", ".ad", ".ads",
        ".comment", ".comments", ".related",
        "nav", "aside",
    ]

    def extract(self, html: str, base_url: str = "") -> ExtractedContent:
        """Extract comprehensive content from HTML."""
        soup = BeautifulSoup(html, "lxml")
        content = ExtractedContent()

        # Extract title
        content.title = self._extract_title(soup)

        # Extract structured data first (for metadata)
        content.structured_data = self._extract_structured_data(soup, html)

        # Find main content area
        main = self._find_main_content(soup)

        # Clean noise from main content
        self._remove_noise(main)

        # Extract different content types
        content.tables = self._extract_tables(main)
        content.code_blocks = self._extract_code_blocks(main)
        content.images = self._extract_images(main, base_url)
        content.links = self._extract_links(main, base_url)
        content.metadata = self._extract_metadata(soup)

        # Extract text content (excluding already extracted elements)
        content.text = self._extract_text(main)
        content.markdown = self._extract_markdown(main)

        # Calculate stats
        content.word_count = len(content.text.split())
        content.reading_time_minutes = content.word_count / 200  # avg reading speed

        return content

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]

        # Fallback to <title>
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        # Fallback to h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    def _find_main_content(self, soup: BeautifulSoup) -> Tag:
        """Find the main content area of the page."""
        for selector in self.CONTENT_SELECTORS:
            main = soup.select_one(selector)
            if main and len(main.get_text(strip=True)) > 100:
                return main

        # Fallback to body
        body = soup.find("body")
        return body if body else soup

    def _remove_noise(self, element: Tag) -> None:
        """Remove noisy elements from content."""
        for selector in self.NOISE_SELECTORS:
            for noise in element.select(selector):
                noise.decompose()

    def _extract_tables(self, element: Tag) -> list[ExtractedTable]:
        """Extract all tables as structured data."""
        tables = []
        for table in element.find_all("table"):
            extracted = ExtractedTable()

            # Extract headers
            header_row = table.find("tr")
            if header_row:
                for th in header_row.find_all(["th", "td"]):
                    extracted.headers.append(th.get_text(strip=True))

            # Extract data rows
            for tr in table.find_all("tr")[1:]:  # Skip header row
                row = []
                for td in tr.find_all(["td", "th"]):
                    row.append(td.get_text(strip=True))
                if row:
                    extracted.rows.append(row)

            if extracted.headers or extracted.rows:
                tables.append(extracted)

        return tables

    def _extract_code_blocks(self, element: Tag) -> list[ExtractedCode]:
        """Extract code blocks with language detection."""
        code_blocks = []

        # Handle <pre><code> blocks
        for pre in element.find_all("pre"):
            code_tag = pre.find("code")
            if code_tag:
                code_text = code_tag.get_text()
                language = self._detect_code_language(code_tag, pre)
            else:
                code_text = pre.get_text()
                language = ""

            if code_text.strip():
                code_blocks.append(ExtractedCode(
                    code=code_text.strip(),
                    language=language,
                ))

        # Handle <code> blocks not inside <pre> (inline code snippets)
        for code in element.find_all("code"):
            if code.parent.name != "pre" and code.parent.name != "a":
                code_text = code.get_text()
                if len(code_text) > 20:  # Only extract substantial inline code
                    language = self._detect_code_language(code, code.parent)
                    code_blocks.append(ExtractedCode(
                        code=code_text.strip(),
                        language=language,
                    ))

        return code_blocks

    def _detect_code_language(self, code_tag: Tag, parent: Tag) -> str:
        """Detect programming language from class names."""
        # Check code tag classes
        classes = code_tag.get("class", []) + parent.get("class", [])
        language_map = {
            "language-python": "python",
            "language-py": "python",
            "language-javascript": "javascript",
            "language-js": "javascript",
            "language-typescript": "typescript",
            "language-ts": "typescript",
            "language-rust": "rust",
            "language-go": "go",
            "language-java": "java",
            "language-cpp": "cpp",
            "language-c": "c",
            "language-html": "html",
            "language-xml": "xml",
            "language-css": "css",
            "language-sql": "sql",
            "language-bash": "bash",
            "language-shell": "shell",
            "language-json": "json",
            "language-yaml": "yaml",
            "language-yml": "yaml",
            "language-markdown": "markdown",
            "highlight": "",  # Generic highlight class
        }

        for cls in classes:
            if isinstance(cls, str):
                cls_lower = cls.lower()
                if cls_lower in language_map:
                    return language_map[cls_lower]
                # Try prefix matching
                for prefix, lang in language_map.items():
                    if cls_lower.startswith(prefix) and lang:
                        return lang

        return ""

    def _extract_images(self, element: Tag, base_url: str) -> list[ExtractedImage]:
        """Extract images with metadata."""
        images = []
        for img in element.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue

            # Convert relative URLs to absolute
            if base_url and not src.startswith(("http://", "https://", "data:")):
                src = urljoin(base_url, src)

            images.append(ExtractedImage(
                src=src,
                alt=img.get("alt", ""),
                title=img.get("title", ""),
                width=img.get("width", ""),
                height=img.get("height", ""),
            ))

        return images

    def _extract_links(self, element: Tag, base_url: str) -> list[dict[str, str]]:
        """Extract links with text and URL."""
        links = []
        for a in element.find_all("a", href=True):
            href = a["href"]
            if base_url and not href.startswith(("http://", "https://", "#", "mailto:")):
                href = urljoin(base_url, href)

            links.append({
                "text": a.get_text(strip=True),
                "url": href,
            })

        return links

    def _extract_structured_data(self, soup: BeautifulSoup, html: str = "") -> list[StructuredData]:
        """Extract structured data using extruct (JSON-LD, microdata, RDFa, OpenGraph, Dublin Core)."""
        structured = []

        # Use extruct if available for comprehensive extraction
        if HAS_EXTRUCT and html:
            try:
                extracted = extruct.extract(html, base_url="", syntaxes=["json-ld", "microdata", "rdfa", "opengraph", "dublincore"])
                
                # Process JSON-LD
                for item in extracted.get("json-ld", []):
                    if isinstance(item, dict):
                        structured.append(StructuredData(
                            data=item,
                            type=item.get("@type", "json-ld"),
                        ))
                
                # Process Microdata
                for item in extracted.get("microdata", []):
                    if isinstance(item, dict):
                        structured.append(StructuredData(
                            data=item,
                            type=item.get("type", "microdata"),
                        ))
                
                # Process RDFa
                for item in extracted.get("rdfa", []):
                    if isinstance(item, dict):
                        structured.append(StructuredData(
                            data=item,
                            type=item.get("type", "rdfa"),
                        ))
                
                # Process OpenGraph
                for item in extracted.get("opengraph", []):
                    if isinstance(item, dict):
                        structured.append(StructuredData(
                            data=item,
                            type="opengraph",
                        ))
                
                # Process Dublin Core
                for item in extracted.get("dublincore", []):
                    if isinstance(item, dict):
                        structured.append(StructuredData(
                            data=item,
                            type="dublincore",
                        ))
            except Exception:
                pass  # Fallback to manual extraction

        # Fallback: manual JSON-LD extraction if extruct not available or failed
        if not structured:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, dict):
                        structured.append(StructuredData(
                            data=data,
                            type=data.get("@type", ""),
                        ))
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                structured.append(StructuredData(
                                    data=item,
                                    type=item.get("@type", ""),
                                ))
                except (json.JSONDecodeError, TypeError):
                    pass

        return structured

    def _extract_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract page metadata."""
        metadata = {}

        # Meta description
        desc = soup.find("meta", attrs={"name": "description"})
        if desc:
            metadata["description"] = desc.get("content", "")

        # Meta keywords
        keywords = soup.find("meta", attrs={"name": "keywords"})
        if keywords:
            metadata["keywords"] = keywords.get("content", "")

        # Open Graph
        for prop in ["og:title", "og:description", "og:type", "og:url", "og:image"]:
            og = soup.find("meta", property=prop)
            if og:
                metadata[prop.replace(":", "_")] = og.get("content", "")

        # Author
        author = soup.find("meta", attrs={"name": "author"})
        if author:
            metadata["author"] = author.get("content", "")

        # Published date
        for attr in ["article:published_time", "datePublished", "pubdate"]:
            date_meta = soup.find("meta", property=attr) or soup.find("meta", attrs={"name": attr})
            if date_meta:
                metadata["published_date"] = date_meta.get("content", "")
                break

        return metadata

    def _extract_text(self, element: Tag) -> str:
        """Extract clean text content."""
        # Get text with newlines for block elements
        for br in element.find_all("br"):
            br.replace_with("\n")

        text = element.get_text(separator="\n", strip=True)

        # Clean up multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _extract_markdown(self, element: Tag) -> str:
        """Extract content as markdown."""
        lines = []

        for child in element.descendants:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    lines.append(text)
                continue

            if not isinstance(child, Tag):
                continue

            name = child.name
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(name[1])
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"\n{'#' * level} {text}\n")
            elif name == "p":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"\n{text}\n")
            elif name == "li":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")
            elif name == "blockquote":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"\n> {text}\n")
            elif name == "code" and child.parent.name == "pre":
                # Code blocks handled separately
                pass
            elif name == "pre":
                code_text = child.get_text()
                if code_text.strip():
                    lines.append(f"\n```\n{code_text.strip()}\n```\n")
            elif name == "a":
                href = child.get("href", "")
                text = child.get_text(strip=True)
                if href and text and text != href:
                    lines.append(f"[{text}]({href})")
            elif name == "strong" or name == "b":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"**{text}**")
            elif name == "em" or name == "i":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"*{text}*")

        return "\n".join(lines)


def extract_tables_markdown(html: str) -> str:
    """Quick helper to extract tables as markdown."""
    extractor = ContentExtractor()
    content = extractor.extract(html)
    if not content.tables:
        return "No tables found."

    markdown_tables = []
    for i, table in enumerate(content.tables, 1):
        markdown_tables.append(f"### Table {i}\n{table.to_markdown()}")

    return "\n\n".join(markdown_tables)


def extract_code_blocks(html: str, language: str = "") -> list[str]:
    """Quick helper to extract code blocks, optionally filtered by language."""
    extractor = ContentExtractor()
    content = extractor.extract(html)

    if language:
        return [cb.code for cb in content.code_blocks if cb.language == language]
    return [cb.code for cb in content.code_blocks]
