"""Tests for structured extraction behavior."""

from __future__ import annotations

from crawler.extractor import ContentExtractor


class TestStructuredDataExtraction:
    """Test structured data extraction paths."""

    def test_manual_jsonld_fallback_when_extruct_unavailable(self, monkeypatch):
        """Fallback should still extract JSON-LD when extruct is disabled."""
        html = """
        <html>
            <head>
                <script type="application/ld+json">
                    {"@context":"https://schema.org","@type":"Article","headline":"Fallback Title"}
                </script>
            </head>
            <body><article><p>Hello world.</p></article></body>
        </html>
        """

        monkeypatch.setattr("crawler.extractor.HAS_EXTRUCT", False)

        content = ContentExtractor().extract(html)

        assert len(content.structured_data) == 1
        assert content.structured_data[0].type == "Article"
        assert content.structured_data[0].data["headline"] == "Fallback Title"

    def test_extruct_path_collects_jsonld_and_opengraph(self, monkeypatch):
        """Extruct extraction should populate multiple structured syntaxes."""
        html = """
        <html>
            <head>
                <meta property="og:title" content="OG Title" />
            </head>
            <body><article><p>Hello world.</p></article></body>
        </html>
        """

        def fake_extract(*args, **kwargs):
            return {
                "json-ld": [{"@type": "Article", "headline": "JSON-LD Title"}],
                "microdata": [],
                "rdfa": [],
                "opengraph": [{"title": "OG Title"}],
                "dublincore": [],
            }

        monkeypatch.setattr("crawler.extractor.HAS_EXTRUCT", True)
        monkeypatch.setattr("crawler.extractor.extruct.extract", fake_extract)

        content = ContentExtractor().extract(html)

        types = [item.type for item in content.structured_data]
        assert "Article" in types
        assert "opengraph" in types
