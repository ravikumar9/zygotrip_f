"""Lightweight query parser for the unified search engine."""

from dataclasses import dataclass
from typing import List


@dataclass
class QueryIntent:
    """Normalized intent object used by the search engine."""

    type: str
    confidence: float
    tokens: List[str]
    normalized: str


class QueryParser:
    """Parse query strings into an intent the engine can use."""

    def parse(self, query: str) -> QueryIntent:
        normalized = " ".join((query or "").strip().split()).lower()
        tokens = normalized.split() if normalized else []

        if not normalized:
            return QueryIntent(type="empty", confidence=1.0, tokens=[], normalized="")

        if normalized.isdigit():
            return QueryIntent(type="hotel_id", confidence=0.95, tokens=tokens, normalized=normalized)

        intent = self._detect_location_intent(normalized, tokens)
        if intent:
            return intent

        if len(tokens) >= 2:
            return QueryIntent(type="locality", confidence=0.6, tokens=tokens, normalized=normalized)

        return QueryIntent(type="property", confidence=0.55, tokens=tokens, normalized=normalized)

    def get_search_strategy(self, intent: QueryIntent) -> str:
        return intent.type

    def _detect_location_intent(self, normalized: str, tokens: List[str]) -> QueryIntent | None:
        try:
            from apps.core.models import City, Locality

            if City.objects.filter(name__iexact=normalized).exists() or City.objects.filter(display_name__iexact=normalized).exists():
                return QueryIntent(type="city", confidence=0.9, tokens=tokens, normalized=normalized)

            if Locality.objects.filter(name__iexact=normalized).exists() or Locality.objects.filter(display_name__iexact=normalized).exists():
                return QueryIntent(type="locality", confidence=0.85, tokens=tokens, normalized=normalized)
        except Exception:
            return None

        return None




