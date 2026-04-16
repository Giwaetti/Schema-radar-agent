from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .audit import SiteAuditor
from .dashboard import build_summary, generate_dashboard
from .fetch import Fetcher
from .matcher import match_offer
from .models import LeadRecord, SourceItem
from .parsers import parse_html_links, parse_html_list, parse_rss_entries
from .scoring import KeywordScorer
from .utils import (
    ensure_dir,
    external_urls,
    flatten_for_csv,
    guess_business_name,
    make_id,
    normalize_url,
    write_csv,
    write_json,
)


class SchemaRadarPipeline:
    def __init__(
        self,
        sources: list[dict[str, Any]],
        keyword_config: dict[str, Any],
        out_dir: str | Path,
        docs_dir: str | Path,
        audit_sites: bool = True,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.sources = [source for source in sources if source.get("enabled", False)]
        self.fetcher = fetcher or Fetcher()
        self.scorer = KeywordScorer(keyword_config)
        self.auditor = SiteAuditor(self.fetcher)
        self.out_dir = ensure_dir(out_dir)
        self.docs_dir = ensure_dir(docs_dir)
        self.audit_sites = audit_sites

    def run(self) -> dict[str, Any]:
        items = self._collect_items()
        leads = self._build_leads(items)
        leads_sorted = sorted(leads, key=lambda lead: (self._stage_rank(lead["stage"]), lead["score"]), reverse=True)
        write_json(self.out_dir / "leads.json", leads_sorted)
        write_csv(self.out_dir / "leads.csv", [flatten_for_csv(lead) for lead in leads_sorted])
        summary = build_summary(leads_sorted)
        write_json(self.out_dir / "summary.json", summary)
        generate_dashboard(leads_sorted, self.docs_dir / "index.html")
        return summary

    def _collect_items(self) -> list[SourceItem]:
        collected: list[SourceItem] = []
        for source in self.sources:
            kind = source.get("kind")
            if kind == "rss":
                response, feed = self.fetcher.parse_feed(source["url"])
                if response.ok:
                    collected.extend(parse_rss_entries(source, feed))
            elif kind == "html_list":
                response = self.fetcher.get(source["url"])
                if response.ok and response.text:
                    collected.extend(parse_html_list(source, response.text))
            elif kind == "html_links":
                response = self.fetcher.get(source["url"])
                if response.ok and response.text:
                    collected.extend(parse_html_links(source, response.text))
        deduped = OrderedDict()
        for item in collected:
            item_id = make_id(item.source_id, item.url, item.title)
            deduped[item_id] = item
        return list(deduped.values())

    def _build_leads(self, items: list[SourceItem]) -> list[dict[str, Any]]:
        leads: list[dict[str, Any]] = []
        for item in items:
            score = self.scorer.score_item(item)
            if score.stage == "noise":
                continue
            business_url = self._extract_business_url(item)
            audit = self.auditor.audit(business_url) if (business_url and self.audit_sites) else None
            offer_fit, action_hint = match_offer(score.stage, score.platforms, score.issue_types, audit)
            item_id = make_id(item.source_id, item.url, item.title)
            business_name = guess_business_name(business_url)
            lead = LeadRecord(
                item_id=item_id,
                source=item.source_name,
                source_id=item.source_id,
                source_type=item.source_type,
                source_url=item.url,
                title=item.title,
                summary=item.summary,
                published_at=item.published_at.isoformat() if item.published_at else None,
                discovered_at=item.discovered_at.isoformat() if item.discovered_at else "",
                stage=score.stage,
                score=score.score,
                score_breakdown=score.breakdown,
                platforms=score.platforms,
                issue_types=score.issue_types,
                intent_flags=score.intent_flags,
                business_name=business_name,
                business_url=business_url,
                audit=audit.to_dict() if audit else None,
                offer_fit=offer_fit,
                action_hint=action_hint,
                tags=item.tags,
            )
            leads.append(lead.to_dict())
        return leads

    def _extract_business_url(self, item: SourceItem) -> str | None:
        candidate_urls = external_urls(item.raw_links, item.url)
        default_blocked = ["reddit.com", "shopify.com", "wordpress.org", "upwork.com", "support.google.com"]
        source_meta = next((source for source in self.sources if source.get("id") == item.source_id), {})
        blocked = default_blocked + list(source_meta.get("block_domains", []))
        for url in candidate_urls:
            domain = urlparse(url).netloc.lower()
            if any(block in domain for block in blocked):
                continue
            return normalize_url(url)
        return None

    @staticmethod
    def _stage_rank(stage: str) -> int:
        return {"hot": 4, "warm": 3, "watch": 2, "noise": 1}.get(stage, 0)
