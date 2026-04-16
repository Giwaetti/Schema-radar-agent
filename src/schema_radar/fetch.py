from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import feedparser
import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36 SchemaRadarBot/1.0"
    )
}


@dataclass
class FetchResult:
    url: str
    status_code: int | None
    text: str | None
    content: bytes | None
    final_url: str | None
    ok: bool
    error: str | None = None


class Fetcher:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str) -> FetchResult:
        try:
            response = self.session.get(url, timeout=self.timeout)
            return FetchResult(
                url=url,
                status_code=response.status_code,
                text=response.text,
                content=response.content,
                final_url=str(response.url),
                ok=response.ok,
                error=None,
            )
        except requests.RequestException as exc:
            return FetchResult(
                url=url,
                status_code=None,
                text=None,
                content=None,
                final_url=None,
                ok=False,
                error=str(exc),
            )

    def parse_feed(self, url: str) -> tuple[FetchResult, Any]:
        response = self.get(url)
        feed = feedparser.parse(response.content or b"")
        return response, feed
