"""
Unified Search Engine - Main Orchestrator
Production-grade OTA search with ranking, caching, and fallback strategies
"""

from typing import Dict, Any, Optional, List
from django.db.models import Q, QuerySet
from django.db import connection
from django.core.exceptions import ObjectDoesNotExist
import time
import logging

from .query_parser import QueryParser, QueryIntent
from .ranking_engine import RankingEngine
from .autocomplete_engine import AutocompleteEngine
from .filters_engine import FiltersEngine
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

try:
    from django.contrib.postgres.search import TrigramSimilarity
except ImportError:  # pragma: no cover - optional dependency
    TrigramSimilarity = None


class SearchResults:
    """Search results container with tuple and dict-like access."""

    def __init__(self, results, count: int, strategy: str = "", intent: str = "", cached: bool = False, query_time_ms: float | None = None):
        self.results = results
        self.count = count
        self.strategy = strategy
        self.intent = intent
        self.cached = cached
        self.query_time_ms = query_time_ms

    def __iter__(self):
        yield self.results
        yield self.count

    def __getitem__(self, key):
        if isinstance(key, str):
            return {
                "results": self.results,
                "count": self.count,
                "strategy": self.strategy,
                "intent": self.intent,
                "cached": self.cached,
                "query_time_ms": self.query_time_ms,
            }.get(key)
        return self.results[key]

    def get(self, key, default=None):
        value = self.__getitem__(key)
        return default if value is None else value


class UnifiedSearchEngine:
    """
    Main search orchestrator with intelligent fallback strategies
    
    Features:
    ─────────
    - Intent-based search routing
    - Multi-level fallback (exact → fuzzy → partial → popular)
    - Intelligent ranking with relevance scoring
    - Smart caching with Redis
    - Performance tracking (<120ms target)
    - Grouped autocomplete results
    """
    
    def __init__(self, cache_ttl: int = 900):
        self.query_parser = QueryParser()
        self.ranking_engine = RankingEngine()
        self.autocomplete_engine = AutocompleteEngine()
        self.filters_engine = FiltersEngine()
        self.cache_manager = CacheManager()
        self.cache_ttl = cache_ttl
    
    def search_hotels(
        self,
        query: str | None = None,
        filters: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        limit: int = 50,
        city: str | None = None,
        area: str | None = None,
        hotel_name: str | None = None,
    ) -> SearchResults:
        """
        Main search method with fallback strategies
        
        Args:
            query: Search query string
            filters: Optional filter parameters
            use_cache: Whether to use cache (default: True)
            
        Returns:
            {
                "results": [...],  # Property queryset or list
                "count": 42,
                "query_time_ms": 85,
                "strategy": "fuzzy",
                "intent": "city"
            }
        """
        start_time = time.time()
        search_query = (query or "").strip()
        filter_payload = filters.copy() if filters else {}

        if city:
            filter_payload["city"] = city
        if area:
            filter_payload["area"] = area
        if hotel_name:
            filter_payload["hotel_name"] = hotel_name
        
        try:
            # Check cache first
            if use_cache:
                cached = self.cache_manager.get_search_results(search_query, filter_payload)
                if cached is not None:
                    ids = cached.get("ids", [])
                    if ids:
                        from apps.hotels.models import Property
                        results = list(Property.objects.filter(id__in=ids))
                        results.sort(key=lambda item: ids.index(item.id))
                    else:
                        results = []
                    return SearchResults(
                        results=results,
                        count=cached.get("count", 0),
                        strategy=cached.get("strategy", ""),
                        intent=cached.get("intent", ""),
                        cached=True,
                        query_time_ms=cached.get("query_time_ms"),
                    )
            
            # Parse query intent
            intent = self.query_parser.parse(search_query)
            logger.info(f"Search query: '{search_query}' → Intent: {intent.type} (confidence: {intent.confidence})")
            
            # Get base queryset
            from apps.hotels.selectors import public_properties_queryset
            queryset = public_properties_queryset().select_related(
                'city', 'locality'
            ).prefetch_related(
                'images', 'amenities', 'room_types'
            )
            
            # Apply search based on intent
            queryset = self._apply_search_strategy(queryset, intent)
            
            # Apply filters if provided
            if filter_payload:
                queryset = self.filters_engine.apply_filters(queryset, filter_payload)
            
            # Apply ranking
            ranked = self.ranking_engine.rank_results(queryset, search_query)
            
            # Get result count
            count = len(ranked)
            
            # Fallback if no results
            if count == 0:
                fallback_qs = self._fallback_search(search_query, filter_payload)
                ranked = self.ranking_engine.rank_results(fallback_qs, search_query)
                count = len(ranked)

            if limit:
                ranked = ranked[:limit]
            
            # Prepare response
            query_time = (time.time() - start_time) * 1000  # Convert to ms
            
            result = SearchResults(
                results=ranked,
                count=count,
                query_time_ms=round(query_time, 2),
                strategy=self.query_parser.get_search_strategy(intent),
                intent=intent.type,
                cached=False,
            )
            
            # Cache results
            if use_cache and count > 0:
                self.cache_manager.set_search_results(
                    search_query,
                    {
                        "ids": [item.id for item in ranked],
                        "count": count,
                        "query_time_ms": round(query_time, 2),
                        "strategy": result.strategy,
                        "intent": result.intent,
                    },
                    filter_payload,
                )
            
            logger.info(f"Search completed: {count} results in {query_time:.2f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            from apps.hotels.models import Property
            return SearchResults(
                results=list(Property.objects.none()),
                count=0,
                query_time_ms=round((time.time() - start_time) * 1000, 2),
                strategy="error",
                intent="error",
                cached=False,
            )
    
    def _apply_search_strategy(self, queryset: QuerySet, intent: QueryIntent) -> QuerySet:
        """
        Apply search based on detected intent
        
        Strategies:
        ───────────
        - hotel_id: Exact ID match
        - city: City name match
        - locality: Locality + city match
        - property: Property name match
        - landmark: Landmark proximity (fallback to property name)
        - unknown: Broad search across all fields
        """
        try:
            if intent.type == 'hotel_id':
                # Exact ID match
                return queryset.filter(id=int(intent.tokens[0]))
            
            elif intent.type == 'city':
                # City name match
                city_name = intent.normalized
                return queryset.filter(
                    Q(city__name__icontains=city_name) |
                    Q(city__name__istartswith=city_name) |
                    Q(city__name__iexact=city_name)
                )
            
            elif intent.type == 'locality':
                # Locality and city match
                tokens = intent.tokens
                if len(tokens) >= 2:
                    locality_name = tokens[0]
                    city_name = tokens[-1]
                    return queryset.filter(
                        Q(locality__name__icontains=locality_name) &
                        Q(city__name__icontains=city_name)
                    )
                else:
                    return queryset.filter(locality__name__icontains=intent.normalized)
            
            elif intent.type == 'property':
                # Property name match
                result = queryset.filter(
                    Q(name__icontains=intent.normalized) |
                    Q(name__istartswith=intent.normalized)
                )
                return self._apply_trigram_similarity(result, intent.normalized)
            
            elif intent.type == 'landmark':
                # Search near landmarks (fallback to name search)
                # Note: Implement geospatial search if coordinates available
                result = queryset.filter(
                    Q(name__icontains=intent.normalized) |
                    Q(description__icontains=intent.normalized) |
                    Q(locality__name__icontains=intent.normalized)
                )
                return self._apply_trigram_similarity(result, intent.normalized)
            
            else:
                # Unknown intent: broad search
                return self._broad_search(queryset, intent.normalized)
        
        except Exception as e:
            logger.error(f"Search strategy error: {e}")
            return queryset
    
    def _broad_search(self, queryset: QuerySet, query: str) -> QuerySet:
        """
        Broad search across multiple fields
        Used for unknown intent or fallback
        """
        result = queryset.filter(
            Q(name__icontains=query) |
            Q(city__name__icontains=query) |
            Q(city_text__icontains=query) |
            Q(legacy_city__icontains=query) |
            Q(locality__name__icontains=query) |
            Q(area__icontains=query) |
            Q(landmark__icontains=query) |
            Q(description__icontains=query)
        )
        return self._apply_trigram_similarity(result, query)

    def _apply_trigram_similarity(self, queryset: QuerySet, query: str) -> QuerySet:
        if not query or not TrigramSimilarity:
            return queryset
        if connection.vendor != "postgresql":
            return queryset
        try:
            return queryset.annotate(
                similarity=(
                    TrigramSimilarity('name', query)
                    + TrigramSimilarity('city__name', query)
                    + TrigramSimilarity('area', query)
                    + TrigramSimilarity('landmark', query)
                )
            ).filter(similarity__gt=0.1)
        except Exception:
            logger.exception("Trigram similarity annotation failed")
            return queryset
    
    def _fallback_search(self, query: str, filters: Optional[Dict] = None) -> QuerySet:
        """
        Fallback strategy when no results found
        
        Fallback Chain:
        ───────────────
        1. Fuzzy match (relaxed query)
        2. Partial word match (any token)
        3. City-only match
        4. Popular properties in any city
        """
        from apps.hotels.selectors import public_properties_queryset
        
        logger.info(f"Triggering fallback for query: '{query}'")
        
        # Try partial token match
        tokens = query.lower().split()
        if len(tokens) > 1:
            for token in tokens:
                if len(token) >= 3:
                    results = public_properties_queryset().filter(
                        Q(name__icontains=token) |
                        Q(city__name__icontains=token) |
                        Q(city_text__icontains=token) |
                        Q(legacy_city__icontains=token) |
                        Q(locality__name__icontains=token) |
                        Q(area__icontains=token) |
                        Q(landmark__icontains=token)
                    )
                    if results.exists():
                        logger.info(f"Fallback success: partial match on '{token}'")
                        return results
        
        # Try city-only (remove all filters except city)
        if filters and (filters.get('city_id') or filters.get('city')):
            city_value = filters.get('city_id') or filters.get('city')
            city_filter = Q(city_id=city_value) if str(city_value).isdigit() else Q(city__name__icontains=city_value)
            results = public_properties_queryset().filter(city_filter)
            if results.exists():
                logger.info("Fallback success: city-only match")
                return results
        
        # Last resort: popular properties
        logger.info("Fallback: returning popular properties")
        return public_properties_queryset().order_by('-popularity_score', '-rating')[:20]
    
    def autocomplete(self, query: str) -> Dict[str, Any]:
        """
        Autocomplete with grouped results
        
        Args:
            query: Partial search query
            
        Returns:
            Grouped autocomplete results
        """
        start_time = time.time()
        
        try:
            # Check cache
            cached = self.cache_manager.get_autocomplete_results(query)
            if cached is not None:
                logger.debug(f"Autocomplete cache hit: '{query}'")
                return cached
            
            # Get autocomplete results
            results = self.autocomplete_engine.autocomplete(query)
            
            # Add timing
            query_time = (time.time() - start_time) * 1000
            results['query_time_ms'] = round(query_time, 2)
            
            # Cache results
            self.cache_manager.set_autocomplete_results(query, results)
            
            logger.info(f"Autocomplete: '{query}' → {sum(len(g['items']) for g in results.get('groups', []))} results in {query_time:.2f}ms")
            
            return results
            
        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return {"groups": [], "error": str(e)}
    
    def get_filters(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Get available filter options
        
        Args:
            query: Optional base query to scope filters
            
        Returns:
            Available filter options with counts
        """
        try:
            # Check cache
            cached = self.cache_manager.get_filters()
            if cached is not None:
                return cached
            
            # Get base queryset
            from apps.hotels.selectors import public_properties_queryset
            queryset = public_properties_queryset()
            
            # Scope to query if provided
            if query:
                intent = self.query_parser.parse(query)
                queryset = self._apply_search_strategy(queryset, intent)
            
            # Get filter options
            filters = self.filters_engine.get_available_filters(queryset)
            
            # Cache filters
            self.cache_manager.set_filters(filters)
            
            return filters
            
        except Exception as e:
            logger.error(f"Get filters error: {e}")
            return {}
    
    def get_popular_destinations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get popular destinations for homepage/empty state
        
        Args:
            limit: Number of destinations to return
            
        Returns:
            List of popular cities with property counts
        """
        try:
            from apps.core.models import City
            from django.db.models import Count
            
            cities = City.objects.annotate(
                property_count=Count('property', distinct=True)
            ).filter(
                property_count__gt=0
            ).order_by('-property_count')[:limit]
            
            return [
                {
                    "name": city.name,
                    "id": city.id,
                    "slug": city.slug if hasattr(city, 'slug') else city.name.lower().replace(' ', '-'),
                    "property_count": city.property_count,
                    "image": city.image.url if hasattr(city, 'image') and city.image else None
                }
                for city in cities
            ]
            
        except Exception as e:
            logger.error(f"Popular destinations error: {e}")
            return []


# Create a singleton instance of the search engine
search_engine = UnifiedSearchEngine()