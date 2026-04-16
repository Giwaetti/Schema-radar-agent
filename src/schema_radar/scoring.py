from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .models import SourceItem


@dataclass
class ScoreResult:
    score: int
    stage: str
    platforms: list[str]
    issue_types: list[str]
    intent_flags: list[str]
    breakdown: dict[str, Any]


class KeywordScorer:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.positive_groups = config.get("positive_groups", {})
        self.negative_phrases = [phrase.lower() for phrase in config.get("negative_phrases", [])]
        self.platform_aliases = {
            key: [entry.lower() for entry in values]
            for key, values in config.get("platform_aliases", {}).items()
        }
        self.issue_aliases = {
            key: [entry.lower() for entry in values]
            for key, values in config.get("issue_aliases", {}).items()
        }
        self.weights = config.get("weights", {})
        self.thresholds = config.get("thresholds", {})

    def score_item(self, item: SourceItem) -> ScoreResult:
        haystack = f"{item.title}\n{item.summary}".lower()
        score = 0
        breakdown: dict[str, Any] = {"matches": {}, "freshness": 0, "negative_hits": []}
        intent_flags: list[str] = []

        for group_name, phrases in self.positive_groups.items():
            matches = [phrase for phrase in phrases if phrase.lower() in haystack]
            if matches:
                weight = int(self.weights.get(group_name, 1))
                score += len(matches) * weight
                breakdown["matches"][group_name] = matches
                if group_name == "intent":
                    intent_flags.extend(matches)

        negative_hits = [phrase for phrase in self.negative_phrases if phrase in haystack]
        if negative_hits:
            score -= len(negative_hits)
            breakdown["negative_hits"] = negative_hits

        freshness_points = self._freshness_points(item.published_at)
        score += freshness_points
        breakdown["freshness"] = freshness_points

        platforms = self._detect_platforms(haystack)
        issue_types = self._detect_issue_types(haystack)
        stage = self._stage(score)

        return ScoreResult(
            score=max(score, 0),
            stage=stage,
            platforms=platforms,
            issue_types=issue_types,
            intent_flags=list(dict.fromkeys(intent_flags)),
            breakdown=breakdown,
        )

    def _detect_platforms(self, haystack: str) -> list[str]:
        found: list[str] = []
        for platform, aliases in self.platform_aliases.items():
            if any(alias in haystack for alias in aliases):
                found.append(platform)
        return found

    def _detect_issue_types(self, haystack: str) -> list[str]:
        found: list[str] = []
        for issue_type, aliases in self.issue_aliases.items():
            if any(alias in haystack for alias in aliases):
                found.append(issue_type)
        return found

    def _freshness_points(self, published_at: datetime | None) -> int:
        if not published_at:
            return 0
        published_at = published_at.astimezone(timezone.utc)
        age_days = max((datetime.now(timezone.utc) - published_at).days, 0)
        if age_days <= 7:
            return int(self.weights.get("freshness_under_7_days", 0))
        if age_days <= 30:
            return int(self.weights.get("freshness_under_30_days", 0))
        if age_days <= 90:
            return int(self.weights.get("freshness_under_90_days", 0))
        return 0

    def _stage(self, score: int) -> str:
        if score >= int(self.thresholds.get("hot", 11)):
            return "hot"
        if score >= int(self.thresholds.get("warm", 7)):
            return "warm"
        if score >= int(self.thresholds.get("watch", 4)):
            return "watch"
        return "noise"
