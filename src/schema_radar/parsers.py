from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import SourceItem
from .utils import extract_urls, normalize_url, parse_datetime, strip_html, utcnow


def parse_rss_entries(source: dict[str, Any], feed: Any) -> list[SourceItem]:
    items: list[SourceItem] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        summary_html = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = strip_html(summary_html)
        link = getattr(entry, "link", "").strip()
        published = getattr(entry, "published", None) or getattr(entry, "updated", None)
        raw_links = extract_urls(summary_html) + ([link] if link else [])
        item = SourceItem(
            source_id=source["id"],
            source_name=source["name"],
            source_type=source.get("source_type", "unknown"),
            url=normalize_url(link or source["url"]),
            title=title,
            summary=summary,
            author=getattr(entry, "author", None),
            published_at=parse_datetime(published),
            discovered_at=utcnow(),
            raw_links=list(dict.fromkeys(raw_links)),
            tags=list(source.get("tags", [])),
        )
        items.append(item)
    return items


def parse_html_list(source: dict[str, Any], html: str) -> list[SourceItem]:
    selectors = source.get("selectors", {})
    item_selector = selectors.get("item")
    title_selector = selectors.get("title")
    link_selector = selectors.get("link")
    snippet_selector = selectors.get("snippet")
    published_selector = selectors.get("published")
    if not item_selector or not title_selector:
        return []

    base_url = source.get("base_url") or source.get("url")
    soup = BeautifulSoup(html, "html.parser")
    items: list[SourceItem] = []

    for node in soup.select(item_selector):
        title_node = node.select_one(title_selector)
        if not title_node:
            continue
        link_node = node.select_one(link_selector) if link_selector else title_node
        href = (link_node.get("href") if link_node else None) or source.get("url")
        title = title_node.get_text(" ", strip=True)
        snippet_node = node.select_one(snippet_selector) if snippet_selector else None
        published_node = node.select_one(published_selector) if published_selector else None
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else _fallback_snippet(node.get_text(" ", strip=True), title)
        published_text = published_node.get_text(" ", strip=True) if published_node else None
        link = normalize_url(urljoin(base_url, href), base_url)
        raw_links = [link] + extract_urls(snippet)
        items.append(
            SourceItem(
                source_id=source["id"],
                source_name=source["name"],
                source_type=source.get("source_type", "unknown"),
                url=link,
                title=title,
                summary=snippet,
                published_at=parse_datetime(published_text),
                discovered_at=utcnow(),
                raw_links=list(dict.fromkeys(raw_links)),
                tags=list(source.get("tags", [])),
            )
        )
    return items


def parse_html_links(source: dict[str, Any], html: str) -> list[SourceItem]:
    selectors = source.get("selectors", {})
    link_selector = selectors.get("link", "a[href]")
    base_url = source.get("base_url") or source.get("url")
    title_min = int(source.get("title_min_length", 8))
    title_max = int(source.get("title_max_length", 180))
    max_items = int(source.get("max_items", 50))

    include_patterns = _compile_patterns(source.get("include_patterns", []))
    exclude_patterns = _compile_patterns(source.get("exclude_patterns", []))
    parent_text_must_include = [term.lower() for term in source.get("parent_text_must_include", [])]

    soup = BeautifulSoup(html, "html.parser")
    items: list[SourceItem] = []
    seen_links: set[str] = set()

    for anchor in soup.select(link_selector):
        href = anchor.get("href")
        if not href:
            continue
        link = normalize_url(urljoin(base_url, href), base_url)
        title = anchor.get_text(" ", strip=True)
        if not title or len(title) < title_min or len(title) > title_max:
            continue
        parent = anchor.find_parent(["article", "tr", "li", "div", "section"]) or anchor.parent
        parent_text = parent.get_text(" ", strip=True) if parent else title
        parent_text = re.sub(r"\s+", " ", parent_text).strip()
        combined = f"{link}\n{title}\n{parent_text}"
        if include_patterns and not any(pattern.search(combined) for pattern in include_patterns):
            continue
        if exclude_patterns and any(pattern.search(combined) for pattern in exclude_patterns):
            continue
        if parent_text_must_include and not any(term in parent_text.lower() for term in parent_text_must_include):
            continue
        if link in seen_links:
            continue
        seen_links.add(link)

        published_text = _find_published_text(parent_text)
        summary = _fallback_snippet(parent_text, title)
        raw_links = [link] + extract_urls(parent_text)
        items.append(
            SourceItem(
                source_id=source["id"],
                source_name=source["name"],
                source_type=source.get("source_type", "unknown"),
                url=link,
                title=title,
                summary=summary,
                published_at=parse_datetime(published_text),
                discovered_at=utcnow(),
                raw_links=list(dict.fromkeys(raw_links)),
                tags=list(source.get("tags", [])),
            )
        )
        if len(items) >= max_items:
            break

    return items


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        compiled.append(re.compile(pattern, re.IGNORECASE))
    return compiled


def _find_published_text(parent_text: str) -> str | None:
    match = re.search(
        r"(\b\d+\s+(?:minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago\b|"
        r"\b[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b)",
        parent_text,
        re.IGNORECASE,
    )
    return match.group(1) if match else None


def _fallback_snippet(text: str, title: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if cleaned.lower().startswith(title.lower()):
        cleaned = cleaned[len(title):].strip(" -:|•")
    return cleaned[:320]
