"""
Trust Signal Badge Engine
Generates dynamic badges to increase booking confidence

Badge types:
- Scarcity: "Only X rooms left"
- Popularity: "Booked X times today"
- Social proof: "Popular choice in [City]"
- Value: "Best value"
- Quality: "Top rated"
- Flexibility: "Free cancellation"
"""

from typing import List, Dict
from datetime import date
from django.utils import timezone
from apps.hotels.constants import (
	MIN_RATING_EXCEPTIONAL,
	MIN_RATING_TOP_RATED,
	MIN_RATING_GOOD,
	MIN_BOOKINGS_TRENDING,
	MIN_BOOKINGS_POPULAR,
	MAX_ROOMS_SCARCITY_URGENT,
	MAX_ROOMS_SCARCITY_WARNING,
	MIN_CANCELLATION_HOURS_FLEXIBLE,
	MAX_BADGES_PER_CARD,
	BADGE_PRIORITY,
	PRICE_THRESHOLD_PREMIUM,
)


class TrustSignalService:
	"""
	Generates contextual trust signals (badges) for property cards
	Badges are calculated dynamically based on real-time data
	"""
	
	def __init__(self, property_obj, context: Dict = None):
		self.property = property_obj
		self.context = context or {}
		self.today = timezone.now().date()
	
	def generate_badges(self) -> List[Dict]:
		"""Generate all applicable badges for property"""
		badges = []
		
		# Quality badges
		if self.property.rating >= MIN_RATING_EXCEPTIONAL:
			badges.append({
				'type': 'quality',
				'level': 'premium',
				'label': 'Exceptional',
				'icon': '🏆',
				'color': 'gold',
			})
		elif self.property.rating >= MIN_RATING_TOP_RATED:
			badges.append({
				'type': 'quality',
				'level': 'high',
				'label': 'Top Rated',
				'icon': '⭐',
				'color': 'blue',
			})
		
		# Popularity badges
		if self.property.is_trending:
			badges.append({
				'type': 'trending',
				'level': 'high',
				'label': 'Trending',
				'icon': '🔥',
				'color': 'red',
			})
		
		if self.property.bookings_today >= MIN_BOOKINGS_TRENDING:
			badges.append({
				'type': 'popularity',
				'level': 'high',
				'label': f'Booked {self.property.bookings_today} times today',
				'icon': '👥',
				'color': 'purple',
			})
		elif self.property.bookings_today >= MIN_BOOKINGS_POPULAR:
			badges.append({
				'type': 'popularity',
				'level': 'medium',
				'label': f'{self.property.bookings_today} recent bookings',
				'icon': '✓',
				'color': 'green',
			})
		
		# Scarcity badges (requires RoomInventory check)
		rooms_left = self._get_available_rooms()
		if rooms_left is not None and rooms_left <= MAX_ROOMS_SCARCITY_URGENT:
			badges.append({
				'type': 'scarcity',
				'level': 'urgent',
				'label': f'Only {rooms_left} rooms left',
				'icon': '⚠️',
				'color': 'orange',
			})
		elif rooms_left is not None and rooms_left <= MAX_ROOMS_SCARCITY_WARNING:
			badges.append({
				'type': 'scarcity',
				'level': 'medium',
				'label': f'{rooms_left} rooms left',
				'icon': '⏰',
				'color': 'yellow',
			})
		
		# Flexibility badges
		if self.property.has_free_cancellation:
			if self.property.cancellation_hours >= MIN_CANCELLATION_HOURS_FLEXIBLE:
				badges.append({
					'type': 'flexibility',
					'level': 'high',
					'label': f'Free cancellation up to {self.property.cancellation_hours}h',
					'icon': '✓',
					'color': 'green',
				})
			else:
				badges.append({
					'type': 'flexibility',
					'level': 'standard',
					'label': 'Free cancellation',
					'icon': '✓',
					'color': 'green',
				})
		
		# Value badges (context-aware)
		if self._is_best_value():
			badges.append({
				'type': 'value',
				'level': 'high',
				'label': 'Best value in area',
				'icon': '💰',
				'color': 'teal',
			})
		
		# Location badges
		if self.context.get('user_distance_km') and self.context['user_distance_km'] <= 2:
			badges.append({
				'type': 'location',
				'level': 'high',
				'label': f'{self.context["user_distance_km"]} km away',
				'icon': '📍',
				'color': 'blue',
			})
		
		# Limit to top 3 badges for UI clarity
		return self._prioritize_badges(badges)
	
	def _get_available_rooms(self) -> int:
		"""
		Check RoomInventory for available rooms
		Returns total available rooms across all room types
		"""
		from apps.rooms.models import RoomInventory
		
		check_in = self.context.get('check_in', self.today)
		
		try:
			# Sum available rooms across all room types for the property
			total_available = 0
			for room_type in self.property.room_types.all()[:10]:  # Limit query
				inventory = RoomInventory.objects.filter(
					room_type=room_type,
					date=check_in
				).first()
				
				if inventory:
					total_available += inventory.available_count
			
			return total_available if total_available > 0 else None
		except Exception:
			return None
	
	def _is_best_value(self) -> bool:
		"""
		Determine if property offers best value
		Based on rating/price ratio compared to city average
		"""
		# Simple heuristic: rating >= 4.0 and price in lower 40th percentile
		if self.property.rating < MIN_RATING_GOOD:
			return False
		
		min_price = getattr(self.property, 'min_room_price', None)
		if not min_price:
			return False
		
		# Note: Calculate city average and percentile
		# For now, use static threshold
		return float(min_price) < PRICE_THRESHOLD_PREMIUM and self.property.rating >= MIN_RATING_GOOD
	
	def _prioritize_badges(self, badges: List[Dict]) -> List[Dict]:
		"""
		Prioritize badges by importance for conversion
		Return top 3 badges
		"""
		sorted_badges = sorted(
			badges,
			key=lambda b: (BADGE_PRIORITY.get(b['type'], 99), -self._badge_level_score(b['level']))
		)
		
		return sorted_badges[:MAX_BADGES_PER_CARD]
	
	@staticmethod
	def _badge_level_score(level: str) -> int:
		"""Convert level to numeric score for sorting"""
		level_map = {
			'urgent': 4,
			'premium': 3,
			'high': 2,
			'medium': 1,
			'standard': 0,
		}
		return level_map.get(level, 0)