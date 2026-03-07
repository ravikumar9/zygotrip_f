# Search ranking algorithm service
# Composite scoring: rating + price + distance + popularity + availability

from typing import Dict, List, Optional
from decimal import Decimal
from django.db.models import QuerySet, F, Case, When, FloatField, Value
from django.db.models.functions import Cast
from django.utils import timezone


class SearchRankingService:
	"""
	Production-grade search ranking algorithm
    
	Scoring formula:
	score = match_score + rating*0.3 + bookings*0.2 + popularity*0.2
	"""
	
	def __init__(self, queryset: QuerySet, params: Dict):
		self.queryset = queryset
		self.params = params
		self.user_lat = self._parse_float(params.get('lat'))
		self.user_lng = self._parse_float(params.get('lng'))
	
	def apply_ranking(self) -> QuerySet:
		"""Apply composite ranking score and sort by relevance"""
		query = (self.params.get('q') or '').strip()

		qs = self.queryset.annotate(
			match_score=self._match_score(query),
			booking_score=self._booking_score(),
			popularity_score_normalized=self._popularity_score(),
		)
		
		qs = qs.annotate(
			relevance_score=(
				F('match_score') +
				(Cast('rating', FloatField()) * Value(0.3, output_field=FloatField())) +
				(F('booking_score') * Value(0.2, output_field=FloatField())) +
				(F('popularity_score_normalized') * Value(0.2, output_field=FloatField()))
			)
		)
		
		return qs.order_by('-relevance_score', '-rating', 'min_room_price')
	
	def _rating_score(self):
		"""Rating quality (0-5) normalized to 0-1"""
		return Case(
			When(rating__gte=4.5, then=Value(1.0)),
			When(rating__gte=4.0, then=Value(0.85)),
			When(rating__gte=3.5, then=Value(0.70)),
			When(rating__gte=3.0, then=Value(0.55)),
			When(rating__gte=2.5, then=Value(0.40)),
			When(rating__gte=2.0, then=Value(0.25)),
			default=Value(0.10),
			output_field=FloatField()
		)
	
	def _price_score(self):
		"""Price competitiveness - inverse scoring (lower price = higher score)"""
		# Note: Implement percentile-based scoring across result set
		# For now, use simple inverse: cheaper properties score higher
		budget = 1500
		moderate = 3000
		premium = 6000
		luxury = 12000
		ultra = 20000
		return Case(
			When(min_room_price__lte=budget, then=Value(1.0)),
			When(min_room_price__lte=moderate, then=Value(0.80)),
			When(min_room_price__lte=premium, then=Value(0.60)),
			When(min_room_price__lte=luxury, then=Value(0.40)),
			When(min_room_price__lte=ultra, then=Value(0.20)),
			default=Value(0.05),
			output_field=FloatField()
		)
	
	def _distance_score(self):
		"""Distance proximity - requires lat/lng in params"""
		if not self.user_lat or not self.user_lng:
			return Value(0.5, output_field=FloatField())  # Neutral score if no location
		
		# Note: Implement Haversine distance calculation in database
		# For now, return neutral score
		return Value(0.5, output_field=FloatField())
	
	def _popularity_score(self):
		"""Popularity from booking signals"""
		return Case(
			When(popularity_score__gte=80, then=Value(1.0)),
			When(popularity_score__gte=50, then=Value(0.8)),
			When(popularity_score__gte=20, then=Value(0.6)),
			When(popularity_score__gte=1, then=Value(0.4)),
			default=Value(0.2),
			output_field=FloatField()
		)

	def _booking_score(self):
		"""Bookings activity score"""
		return Case(
			When(bookings_today__gte=20, then=Value(1.0)),
			When(bookings_today__gte=10, then=Value(0.8)),
			When(bookings_today__gte=5, then=Value(0.6)),
			When(bookings_today__gte=1, then=Value(0.4)),
			default=Value(0.2),
			output_field=FloatField()
		)

	def _match_score(self, query: str):
		"""Match score based on query text relevance"""
		if not query:
			return Value(0.5, output_field=FloatField())
		return Case(
			When(name__icontains=query, then=Value(1.0)),
			When(city__name__icontains=query, then=Value(0.8)),
			When(locality__name__icontains=query, then=Value(0.7)),
			When(area__icontains=query, then=Value(0.6)),
			When(landmark__icontains=query, then=Value(0.5)),
			default=Value(0.0),
			output_field=FloatField()
		)
	
	def _availability_score(self):
		"""Availability signal - properties with rooms available score higher"""
		# Note: Check RoomInventory for date range availability
		# For now, assume all properties available (neutral score)
		return Value(0.7, output_field=FloatField())
	
	@staticmethod
	def _parse_float(value: Optional[str]) -> Optional[float]:
		"""Safely parse float from query param"""
		if not value:
			return None
		try:
			return float(value)
		except (ValueError, TypeError):
			return None


# Import from sibling search.py module
import os
import sys
import importlib.util

# Get path to search.py (sibling of this __init__.py)
parent_dir = os.path.dirname(os.path.dirname(__file__))
search_py_path = os.path.join(parent_dir, 'search.py')

if os.path.exists(search_py_path):
	spec = importlib.util.spec_from_file_location("hotels_search_module", search_py_path)
	search_module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(search_module)
	ProductionSearchEngine = search_module.ProductionSearchEngine
	FilterAggregator = search_module.FilterAggregator