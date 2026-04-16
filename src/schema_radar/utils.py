from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse


URL_RE = re.compile(r"https?://[^\s<>'\")]+", re.IGNORECASE)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_dir(path: str | Path) -> Path:
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_json(path: str | Path, data: Any) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def strip_html(raw_html: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", raw_html)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    relative = _parse_relative_datetime(value)
    if relative:
        return relative
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_relative_datetime(value: str) -> datetime | None:
    match = re.search(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago", value, re.IGNORECASE)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    now = utcnow()
    if unit.startswith("minute"):
        return now - timedelta(minutes=amount)
    if unit.startswith("hour"):
        return now - timedelta(hours=amount)
    if unit.startswith("day"):
        return now - timedelta(days=amount)
    if unit.startswith("week"):
        return now - timedelta(weeks=amount)
    if unit.startswith("month"):
        return now - timedelta(days=30 * amount)
    if unit.startswith("year"):
        return now - timedelta(days=365 * amount)
    return None


def normalize_url(url: str, base_url: str | None = None) -> str:
    combined = urljoin(base_url, url) if base_url else url
    parsed = urlparse(combined)
    path = parsed.path.rstrip("/") or "/"
    normalized = parsed._replace(query=parsed.query, fragment="", path=path)
    return normalized.geturl()


def extract_urls(text: str) -> list[str]:
    return [match.rstrip(".,)") for match in URL_RE.findall(text or "")]


def external_urls(urls: list[str], source_url: str) -> list[str]:
    source_domain = urlparse(source_url).netloc.lower()
    filtered: list[str] = []
    for url in urls:
        domain = urlparse(url).netloc.lower()
        if domain and domain != source_domain and url not in filtered:
            filtered.append(url)
    return filtered


def guess_business_name(url: str | None) -> str | None:
    if not url:
        return None
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    name = domain.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return name.title() if name else None


def make_id(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def flatten_for_csv(record: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, list):
            flat[key] = "; ".join(str(item) for item in value)
        elif isinstance(value, dict):
            flat[key] = json.dumps(value, ensure_ascii=False)
        else:
            flat[key] = value
    return flat
