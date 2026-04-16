from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SourceItem:
    source_id: str
    source_name: str
    source_type: str
    url: str
    title: str
    summary: str = ""
    author: str | None = None
    published_at: datetime | None = None
    discovered_at: datetime | None = None
    raw_links: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("published_at", "discovered_at"):
            value = data.get(key)
            data[key] = value.isoformat() if value else None
        return data


@dataclass
class AuditResult:
    business_url: str
    final_url: str | None = None
    domain: str | None = None
    status_code: int | None = None
    ok: bool = False
    has_json_ld: bool = False
    schema_types: list[str] = field(default_factory=list)
    cms: str | None = None
    site_kind: str | None = None
    title: str | None = None
    opportunity_gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LeadRecord:
    item_id: str
    source: str
    source_id: str
    source_type: str
    source_url: str
    title: str
    summary: str
    published_at: str | None
    discovered_at: str
    stage: str
    score: int
    score_breakdown: dict[str, Any]
    platforms: list[str]
    issue_types: list[str]
    intent_flags: list[str]
    business_name: str | None
    business_url: str | None
    audit: dict[str, Any] | None
    offer_fit: str
    action_hint: str
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
