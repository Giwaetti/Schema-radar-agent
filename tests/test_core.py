from __future__ import annotations

import sys
import unittest
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from schema_radar.audit import SiteAuditor
from schema_radar.fetch import FetchResult
from schema_radar.models import SourceItem
from schema_radar.pipeline import SchemaRadarPipeline
from schema_radar.scoring import KeywordScorer
from schema_radar.utils import parse_datetime, utcnow


class DummyFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def get(self, url: str) -> FetchResult:
        return FetchResult(
            url=url,
            status_code=200,
            text=self.html,
            content=self.html.encode("utf-8"),
            final_url=url,
            ok=True,
            error=None,
        )


class DummyPipelineFetcher(DummyFetcher):
    def __init__(self, html: str, feed_xml: str) -> None:
        super().__init__(html)
        self.feed_xml = feed_xml

    def parse_feed(self, url: str):
        response = FetchResult(
            url=url,
            status_code=200,
            text=self.feed_xml,
            content=self.feed_xml.encode("utf-8"),
            final_url=url,
            ok=True,
            error=None,
        )
        return response, feedparser.parse(self.feed_xml)


class PipelineTests(unittest.TestCase):
    def test_pipeline_builds_dashboard_outputs(self) -> None:
        html = """
        <html><head><title>Store</title><meta name="generator" content="Shopify"></head>
        <body>
          <button>Add to Cart</button>
          <script type="application/ld+json">
          {"@context":"https://schema.org","@type":"Product","name":"Widget"}
          </script>
        </body></html>
        """
        feed_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>Demo</title>
          <item>
            <title>Need help with Shopify schema markup</title>
            <link>https://forum.example/thread-1</link>
            <description>My product rich results are not showing. See https://widgets.example</description>
            <pubDate>Thu, 16 Apr 2026 17:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """
        fetcher = DummyPipelineFetcher(html=html, feed_xml=feed_xml)
        out_dir = ROOT / "tests" / "tmp_data"
        docs_dir = ROOT / "tests" / "tmp_docs"
        pipeline = SchemaRadarPipeline(
            sources=[
                {
                    "id": "demo",
                    "name": "Demo RSS",
                    "kind": "rss",
                    "enabled": True,
                    "url": "https://demo.example/feed",
                    "source_type": "forum",
                    "tags": ["demo"],
                }
            ],
            keyword_config={
                "positive_groups": {
                    "schema": ["schema markup", "rich results"],
                    "intent": ["need help", "not showing"],
                    "platforms": ["shopify"],
                },
                "platform_aliases": {"shopify": ["shopify"]},
                "issue_aliases": {"product_schema": ["rich results"]},
                "weights": {
                    "schema": 3,
                    "intent": 2,
                    "platforms": 1,
                    "freshness_under_7_days": 3,
                    "freshness_under_30_days": 2,
                    "freshness_under_90_days": 1,
                },
                "thresholds": {"hot": 8, "warm": 5, "watch": 3},
            },
            out_dir=out_dir,
            docs_dir=docs_dir,
            fetcher=fetcher,
        )
        summary = pipeline.run()
        self.assertEqual(summary["total"], 1)
        self.assertTrue((out_dir / "leads.json").exists())
        self.assertTrue((docs_dir / "index.html").exists())


class ScoringTests(unittest.TestCase):
    def test_schema_issue_scores_hot(self) -> None:
        scorer = KeywordScorer(
            {
                "positive_groups": {
                    "schema": ["schema markup", "structured data", "merchant listings"],
                    "intent": ["need help", "error", "missing"],
                    "platforms": ["shopify"],
                },
                "platform_aliases": {"shopify": ["shopify"]},
                "issue_aliases": {"product_schema": ["merchant listings"], "missing_schema": ["missing"]},
                "weights": {
                    "schema": 3,
                    "intent": 2,
                    "platforms": 1,
                    "freshness_under_7_days": 3,
                    "freshness_under_30_days": 2,
                    "freshness_under_90_days": 1,
                },
                "thresholds": {"hot": 11, "warm": 7, "watch": 4},
            }
        )
        item = SourceItem(
            source_id="x",
            source_name="Reddit",
            source_type="forum",
            url="https://example.com/thread",
            title="Need help with Shopify schema markup",
            summary="Our merchant listings have an error and product fields are missing.",
            published_at=utcnow(),
            discovered_at=utcnow(),
        )
        result = scorer.score_item(item)
        self.assertEqual(result.stage, "hot")
        self.assertIn("shopify", result.platforms)
        self.assertIn("product_schema", result.issue_types)


class AuditTests(unittest.TestCase):
    def test_audit_detects_product_schema(self) -> None:
        html = """
        <html><head><title>Store</title><meta name="generator" content="Shopify"></head>
        <body>
          <button>Add to Cart</button>
          <script type="application/ld+json">
          {"@context":"https://schema.org","@type":"Product","name":"Widget"}
          </script>
        </body></html>
        """
        auditor = SiteAuditor(DummyFetcher(html))
        result = auditor.audit("https://widgets.example")
        self.assertTrue(result.ok)
        self.assertEqual(result.cms, "shopify")
        self.assertEqual(result.site_kind, "ecommerce")
        self.assertIn("Product", result.schema_types)
        self.assertEqual(result.opportunity_gaps, ["BreadcrumbList not detected on scanned page"])


class DatetimeTests(unittest.TestCase):
    def test_rfc822_datetime_parses(self) -> None:
        dt = parse_datetime("Thu, 16 Apr 2026 17:00:00 GMT")
        self.assertIsNotNone(dt)


if __name__ == "__main__":
    unittest.main()
