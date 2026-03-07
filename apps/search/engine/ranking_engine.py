"""Ranking engine for search results."""

from difflib import SequenceMatcher


class RankingEngine:
    """Rank search results using match and business signals."""

    def rank_results(self, results, query: str | None = None):
        items = list(results)
        query_text = (query or "").strip().lower()

        if not items:
            return items

        max_bookings = max((getattr(item, "bookings_today", 0) or 0) for item in items) or 1
        max_popularity = max((getattr(item, "popularity_score", 0) or 0) for item in items) or 1

        for item in items:
            match_score = self._match_score(item, query_text)
            rating = float(getattr(item, "rating", 0) or 0)
            bookings = float(getattr(item, "bookings_today", 0) or 0)
            popularity = float(getattr(item, "popularity_score", 0) or 0)

            bookings_score = bookings / max_bookings
            popularity_score = popularity / max_popularity

            relevance = match_score + (rating * 0.3) + (bookings_score * 0.2) + (popularity_score * 0.2)
            setattr(item, "relevance_score", relevance)

        return sorted(items, key=lambda item: (getattr(item, "relevance_score", 0), getattr(item, "rating", 0)), reverse=True)

    def _match_score(self, item, query_text: str) -> float:
        if not query_text:
            return 0.5

        similarity = getattr(item, "similarity", None)
        if similarity is not None:
            try:
                return min(1.0, float(similarity))
            except (TypeError, ValueError):
                pass

        candidates = [
            getattr(item, "name", ""),
            getattr(getattr(item, "city", None), "name", ""),
            getattr(getattr(item, "locality", None), "name", ""),
            getattr(item, "area", ""),
            getattr(item, "landmark", ""),
        ]

        best = 0.0
        for candidate in candidates:
            candidate_text = (candidate or "").lower()
            if not candidate_text:
                continue
            if query_text in candidate_text:
                best = max(best, 1.0)
                continue
            ratio = SequenceMatcher(None, query_text, candidate_text).ratio()
            best = max(best, ratio)
        return best




