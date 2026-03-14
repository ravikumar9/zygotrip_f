"""Lightweight query parser for the unified search engine.

Production enhancements:
- Noise word stripping (hotels, in, near, best, cheap, etc.)
- City alias resolution via alternate_names field (Bangalore→Bengaluru)
- Compound query decomposition ("bangalore hotels" → city match on "bangalore")
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class QueryIntent:
    """Normalized intent object used by the search engine."""

    type: str
    confidence: float
    tokens: List[str]
    normalized: str


# Common noise words that users append to city/locality names
NOISE_WORDS = frozenset({
    'hotels', 'hotel', 'rooms', 'room', 'stay', 'stays',
    'in', 'at', 'near', 'around', 'nearby',
    'best', 'top', 'cheap', 'budget', 'luxury', 'premium',
    'resorts', 'resort', 'oyo', 'hostel', 'hostels',
    'booking', 'book', 'search', 'find',
})


def _strip_noise(tokens: List[str]) -> List[str]:
    """Remove common OTA noise words, preserving at least one token."""
    cleaned = [t for t in tokens if t not in NOISE_WORDS]
    return cleaned if cleaned else tokens


class QueryParser:
    """Parse query strings into an intent the engine can use."""

    def parse(self, query: str) -> QueryIntent:
        normalized = " ".join((query or "").strip().split()).lower()
        tokens = normalized.split() if normalized else []

        if not normalized:
            return QueryIntent(type="empty", confidence=1.0, tokens=[], normalized="")

        if normalized.isdigit():
            return QueryIntent(type="hotel_id", confidence=0.95, tokens=tokens, normalized=normalized)

        # Try exact match first (full query as-is)
        intent = self._detect_location_intent(normalized, tokens)
        if intent:
            return intent

        # Strip noise words and retry ("bangalore hotels" → "bangalore")
        cleaned_tokens = _strip_noise(tokens)
        if cleaned_tokens != tokens:
            cleaned_query = " ".join(cleaned_tokens)
            intent = self._detect_location_intent(cleaned_query, cleaned_tokens)
            if intent:
                return intent

        if len(tokens) >= 2:
            return QueryIntent(type="locality", confidence=0.6, tokens=tokens, normalized=normalized)

        return QueryIntent(type="property", confidence=0.55, tokens=tokens, normalized=normalized)

    def get_search_strategy(self, intent: QueryIntent) -> str:
        return intent.type

    def _detect_location_intent(self, normalized: str, tokens: List[str]) -> Optional[QueryIntent]:
        try:
            from apps.core.models import City, Locality

            # 1. Exact name / display_name match
            if City.objects.filter(name__iexact=normalized).exists() or \
               City.objects.filter(display_name__iexact=normalized).exists():
                return QueryIntent(type="city", confidence=0.9, tokens=tokens, normalized=normalized)

            # 2. City alias match via alternate_names (e.g. Bangalore → Bengaluru)
            alias_city = City.objects.filter(alternate_names__icontains=normalized).first()
            if alias_city:
                # Resolve to canonical city name
                canonical = alias_city.name.lower()
                return QueryIntent(
                    type="city", confidence=0.85,
                    tokens=canonical.split(), normalized=canonical,
                )

            # 3. Locality match
            if Locality.objects.filter(name__iexact=normalized).exists() or \
               Locality.objects.filter(display_name__iexact=normalized).exists():
                return QueryIntent(type="locality", confidence=0.85, tokens=tokens, normalized=normalized)
        except Exception:
            return None

        return None




