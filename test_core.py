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
from schema_radar.sales import build_sales_plan
from schema_radar.scoring import KeywordScorer
from schema_radar.utils import utcnow


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


OFFERS = {
    "contact_email": "schemaagent@gmail.com",
    "offers": {
        "ai_visibility_kit": {
            "display_name": "AI Visibility Kit",
            "gumroad_url": "https://schemaagent.gumroad.com/l/rfces",
            "cta_label": "Get the AI Visibility Kit",
        },
        "ai_generator": {
            "display_name": "AI Generator",
            "gumroad_url": "https://schemaagent.gumroad.com/l/wikuuu",
            "cta_label": "Open the AI Generator",
        },
        "direct_service": {
            "display_name": "Done-for-you / service",
            "gumroad_url": None,
            "cta_label": "Email for direct help",
        },
    },
    "aliases": {
        "AI Visibility Kit": "ai_visibility_kit",
        "AI Generator": "ai_generator",
        "Done-for-you / service": "direct_service",
    },
}


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
                    "tags": ["broad"],
                }
            ],
            keyword_config={
                "positive_groups": {
                    "schema_core": ["schema markup", "rich results"],
                    "commercial_intent": ["need help", "not showing"],
                    "platforms": ["shopify"],
                },
                "platform_aliases": {"shopify": ["shopify"]},
                "issue_aliases": {"product_schema": ["rich results"]},
                "gating": {
                    "schema_groups": ["schema_core"],
                    "intent_groups": ["commercial_intent"],
                    "broad_source_tags": ["broad"],
                    "schema_centric_tags": ["schema-centric"],
                    "platform_group_name": "platforms",
                    "require_intent_for_broad": True,
                },
                "weights": {
                    "schema_core": 4,
                    "commercial_intent": 2,
                    "platforms": 1,
                    "freshness_under_7_days": 3,
                },
                "thresholds": {"hot": 8, "warm": 5, "watch": 3},
            },
            offer_config=OFFERS,
            out_dir=out_dir,
            docs_dir=docs_dir,
            fetcher=fetcher,
        )
        summary = pipeline.run()
        self.assertEqual(summary["total"], 1)
        self.assertTrue((out_dir / "leads.json").exists())
        self.assertTrue((out_dir / "sales_queue.json").exists())
        self.assertTrue((docs_dir / "index.html").exists())


class ScoringTests(unittest.TestCase):
    def test_schema_issue_scores_hot(self) -> None:
        scorer = KeywordScorer(
            {
                "positive_groups": {
                    "schema_core": ["schema markup", "structured data", "merchant listings"],
                    "commercial_intent": ["need help", "error", "missing"],
                    "platforms": ["shopify"],
                },
                "platform_aliases": {"shopify": ["shopify"]},
                "issue_aliases": {"product_schema": ["merchant listings"], "missing_schema": ["missing"]},
                "gating": {
                    "schema_groups": ["schema_core"],
                    "intent_groups": ["commercial_intent"],
                    "broad_source_tags": ["broad"],
                    "schema_centric_tags": ["schema-centric"],
                    "platform_group_name": "platforms",
                    "require_intent_for_broad": True,
                },
                "weights": {
                    "schema_core": 4,
                    "commercial_intent": 2,
                    "platforms": 1,
                    "freshness_under_7_days": 3,
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
            tags=["broad"],
        )
        result = scorer.score_item(item)
        self.assertEqual(result.stage, "hot")
        self.assertIn("shopify", result.platforms)
        self.assertIn("product_schema", result.issue_types)


class SalesTests(unittest.TestCase):
    def test_sales_plan_points_generator_lead_to_gumroad(self) -> None:
        plan = build_sales_plan(
            offer_fit="AI Generator",
            action_hint="Position it as faster schema output for recurring implementation work.",
            source_type="jobs",
            source_name="Upwork",
            title="Need Shopify JSON-LD generated",
            summary="Agency needs fast repeatable schema output.",
            platforms=["shopify"],
            issue_types=["product_schema"],
            business_name=None,
            business_url=None,
            offers_config=OFFERS,
        )
        self.assertEqual(plan["offer_key"], "ai_generator")
        self.assertEqual(plan["sales_route"], "proposal_draft")
        self.assertIn("wikuuu", plan["cta_destination"])

    def test_sales_plan_points_service_lead_to_email(self) -> None:
        plan = build_sales_plan(
            offer_fit="Done-for-you / service",
            action_hint="Treat this as a direct service lead first.",
            source_type="forum",
            source_name="Forum",
            title="Need a developer for schema",
            summary="Urgent help wanted.",
            platforms=["shopify"],
            issue_types=["missing_schema"],
            business_name="Acme",
            business_url="https://acme.example",
            offers_config=OFFERS,
        )
        self.assertEqual(plan["offer_key"], "direct_service")
        self.assertEqual(plan["sales_route"], "email_contact")
        self.assertIn("schemaagent@gmail.com", plan["reply_draft"])


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


if __name__ == "__main__":
    unittest.main()
