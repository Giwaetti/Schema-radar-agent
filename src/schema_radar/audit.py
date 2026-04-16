from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .fetch import Fetcher
from .models import AuditResult


JSON_LD_RE = re.compile(r"application/ld\+json", re.IGNORECASE)


def _walk_schema_types(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        schema_type = value.get("@type")
        if isinstance(schema_type, str):
            found.add(schema_type)
        elif isinstance(schema_type, list):
            for entry in schema_type:
                if isinstance(entry, str):
                    found.add(entry)
        for nested in value.values():
            _walk_schema_types(nested, found)
    elif isinstance(value, list):
        for entry in value:
            _walk_schema_types(entry, found)


class SiteAuditor:
    def __init__(self, fetcher: Fetcher, timeout: int = 20) -> None:
        self.fetcher = fetcher
        self.timeout = timeout

    def audit(self, business_url: str) -> AuditResult:
        result = self.fetcher.get(business_url)
        domain = urlparse(business_url).netloc.lower()
        audit = AuditResult(
            business_url=business_url,
            final_url=result.final_url,
            domain=domain,
            status_code=result.status_code,
            ok=result.ok,
        )
        if not result.ok or not result.text:
            audit.error = result.error or f"HTTP {result.status_code}"
            return audit

        soup = BeautifulSoup(result.text, "html.parser")
        audit.title = soup.title.get_text(" ", strip=True) if soup.title else None
        audit.cms = self._detect_cms(result.text, soup)
        audit.site_kind = self._detect_site_kind(result.text, soup)
        audit.has_json_ld, audit.schema_types = self._extract_schema_types(soup)
        audit.opportunity_gaps = self._detect_gaps(audit.site_kind, audit.schema_types)
        audit.notes = self._notes(audit)
        return audit

    def _extract_schema_types(self, soup: BeautifulSoup) -> tuple[bool, list[str]]:
        types: set[str] = set()
        scripts = soup.find_all("script", attrs={"type": JSON_LD_RE})
        for script in scripts:
            raw = script.string or script.get_text("\n", strip=True)
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            _walk_schema_types(parsed, types)
        return bool(scripts), sorted(types)

    def _detect_cms(self, html: str, soup: BeautifulSoup) -> str | None:
        haystack = html.lower()
        generator = soup.find("meta", attrs={"name": re.compile("generator", re.IGNORECASE)})
        if generator and generator.get("content"):
            content = generator["content"].lower()
            if "wordpress" in content:
                return "wordpress"
            if "wix" in content:
                return "wix"
            if "shopify" in content:
                return "shopify"
            if "webflow" in content:
                return "webflow"
        if "cdn.shopify.com" in haystack or "shopify.theme" in haystack:
            return "shopify"
        if "wp-content" in haystack or "wp-json" in haystack:
            return "wordpress"
        if "static.wixstatic.com" in haystack:
            return "wix"
        if "webflow" in haystack:
            return "webflow"
        if "squarespace" in haystack:
            return "squarespace"
        return None

    def _detect_site_kind(self, html: str, soup: BeautifulSoup) -> str:
        haystack = html.lower()
        address = soup.find(attrs={"itemprop": re.compile("address", re.IGNORECASE)})
        if any(term in haystack for term in ["add to cart", "cart", "product", "sku", "checkout"]):
            return "ecommerce"
        if address or any(term in haystack for term in ["book now", "get quote", "opening hours", "service area"]):
            return "local_service"
        return "general"

    def _detect_gaps(self, site_kind: str | None, schema_types: list[str]) -> list[str]:
        schema_set = {entry.lower() for entry in schema_types}
        gaps: list[str] = []
        if site_kind == "ecommerce" and "product" not in schema_set:
            gaps.append("Missing Product schema on scanned page")
        if site_kind == "local_service" and not ({"localbusiness", "service"} & schema_set):
            gaps.append("Missing LocalBusiness/Service schema on scanned page")
        if "breadcrumblist" not in schema_set:
            gaps.append("BreadcrumbList not detected on scanned page")
        if not schema_set:
            gaps.append("No JSON-LD schema detected on scanned page")
        return gaps

    def _notes(self, audit: AuditResult) -> list[str]:
        notes: list[str] = []
        if audit.cms:
            notes.append(f"Detected CMS: {audit.cms}")
        if audit.site_kind:
            notes.append(f"Detected site kind: {audit.site_kind}")
        if audit.schema_types:
            notes.append(f"Schema types found: {', '.join(audit.schema_types[:8])}")
        return notes
