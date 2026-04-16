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
        self.group_caps = {key: int(value) for key, value in config.get("group_caps", {}).items()}
        self.source_boost_tags = {
            key.lower(): int(value) for key, value in config.get("source_boost_tags", {}).items()
        }
        schema_gate = config.get("schema_gate", {})
        self.required_any_of_groups = [entry for entry in schema_gate.get("required_any_of_groups", [])]
        self.allow_if_source_tags_include = {
            entry.lower() for entry in schema_gate.get("allow_if_source_tags_include", [])
        }

    def score_item(self, item: SourceItem) -> ScoreResult:
        haystack = f"{item.title}\n{item.summary}".lower()
        item_tags = {tag.lower() for tag in item.tags}
        score = 0
        breakdown: dict[str, Any] = {
            "matches": {},
            "group_points": {},
            "freshness": 0,
            "negative_hits": [],
            "source_boost": 0,
            "gated": False,
        }
        intent_flags: list[str] = []

        for group_name, phrases in self.positive_groups.items():
            matches = [phrase for phrase in phrases if phrase.lower() in haystack]
            if not matches:
                continue

            raw_points = len(matches) * int(self.weights.get(group_name, 1))
            points = min(raw_points, self.group_caps.get(group_name, raw_points))
            score += points
            breakdown["matches"][group_name] = matches
            breakdown["group_points"][group_name] = points

            if group_name in {"commercial_intent", "implementation_intent", "intent"}:
                intent_flags.extend(matches)

        negative_hits = [phrase for phrase in self.negative_phrases if phrase in haystack]
        if negative_hits:
            score -= len(negative_hits)
            breakdown["negative_hits"] = negative_hits

        source_boost = sum(points for tag, points in self.source_boost_tags.items() if tag in item_tags)
        if source_boost:
            score += source_boost
            breakdown["source_boost"] = source_boost

        freshness_points = self._freshness_points(item.published_at)
        score += freshness_points
        breakdown["freshness"] = freshness_points

        if not self._passes_schema_gate(breakdown["matches"], item_tags):
            breakdown["gated"] = True
            return ScoreResult(
                score=0,
                stage="noise",
                platforms=[],
                issue_types=[],
                intent_flags=[],
                breakdown=breakdown,
            )

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

    def _passes_schema_gate(self, matches: dict[str, list[str]], item_tags: set[str]) -> bool:
        if not self.required_any_of_groups and not self.allow_if_source_tags_include:
            return True
        if any(group in matches for group in self.required_any_of_groups):
            return True
        return any(tag in item_tags for tag in self.allow_if_source_tags_include)

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
