"""
Duffel flight search client.
Falls back to internal FlightFareClass queryset if Duffel fails.
Results cached in Redis for 8 minutes.
"""
import hashlib
import json
import logging
from typing import List, Optional
from django.conf import settings

logger = logging.getLogger('zygotrip.flights.duffel')


def _get_cache_key(prefix: str, **kwargs) -> str:
    raw = json.dumps(kwargs, sort_keys=True, default=str)
    return f'duffel:{prefix}:{hashlib.md5(raw.encode()).hexdigest()}'


def _redis_get(key: str):
    try:
        from django.core.cache import cache
        return cache.get(key)
    except Exception:
        return None


def _redis_set(key: str, value, ttl: int = 480):  # 8 minutes
    try:
        from django.core.cache import cache
        cache.set(key, value, timeout=ttl)
    except Exception:
        pass


class DuffelClient:
    """Duffel Flights API client with Redis caching and internal fallback."""

    BASE_URL = 'https://api.duffel.com'

    def __init__(self):
        self.access_token = getattr(settings, 'DUFFEL_ACCESS_TOKEN', '')

    @property
    def _headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Duffel-Version': 'v1',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def search_offers(
        self,
        origin_iata: str,
        destination_iata: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = 'economy',
    ) -> list:
        """
        Search Duffel for flight offers.
        Returns list of mapped offer dicts.
        Falls back to internal DB if Duffel unavailable.
        """
        if not self.access_token:
            logger.warning('DUFFEL_ACCESS_TOKEN not set — using internal fallback')
            return self._internal_fallback(origin_iata, destination_iata, departure_date)

        cache_key = _get_cache_key(
            'search', origin=origin_iata, dest=destination_iata,
            date=departure_date, pax=passengers, cabin=cabin_class,
        )
        cached = _redis_get(cache_key)
        if cached:
            return cached

        try:
            import requests as _requests
            slices = [{'origin': origin_iata, 'destination': destination_iata, 'departure_date': departure_date}]
            if return_date:
                slices.append({'origin': destination_iata, 'destination': origin_iata, 'departure_date': return_date})

            payload = {
                'data': {
                    'slices': slices,
                    'passengers': [{'type': 'adult'} for _ in range(passengers)],
                    'cabin_class': cabin_class,
                }
            }
            resp = _requests.post(
                f'{self.BASE_URL}/air/offer_requests?return_offers=true',
                json=payload,
                headers=self._headers,
                timeout=30,
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                offers = data.get('data', {}).get('offers', [])
                mapped = [self.map_duffel_offer_to_internal(o) for o in offers[:20]]
                _redis_set(cache_key, mapped)
                logger.info('Duffel search: %s→%s found %d offers', origin_iata, destination_iata, len(mapped))
                return mapped
            else:
                logger.warning('Duffel API error: %s %s', resp.status_code, resp.text[:200])
                return self._internal_fallback(origin_iata, destination_iata, departure_date)

        except Exception as exc:
            logger.warning('Duffel search failed: %s', exc)
            return self._internal_fallback(origin_iata, destination_iata, departure_date)

    def get_offer_details(self, offer_id: str) -> dict:
        """Get full offer details from Duffel."""
        if not self.access_token:
            return {}

        cache_key = _get_cache_key('offer', offer_id=offer_id)
        cached = _redis_get(cache_key)
        if cached:
            return cached

        try:
            import requests as _requests
            resp = _requests.get(
                f'{self.BASE_URL}/air/offers/{offer_id}',
                headers=self._headers,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {})
                _redis_set(cache_key, data)
                return data
        except Exception as exc:
            logger.warning('Duffel get_offer_details failed: %s', exc)
        return {}

    def create_order(self, offer_id: str, passengers: list) -> dict:
        """
        Create a Duffel order (book the flight).
        passengers: list of {title, first_name, last_name, born_on, gender,
                             email, phone_number, id_document: {type, number, expires_on, issuing_country_code}}
        """
        if not self.access_token:
            return {'error': 'Duffel not configured'}

        try:
            import requests as _requests
            payload = {
                'data': {
                    'selected_offers': [offer_id],
                    'passengers': passengers,
                    'payments': [{'type': 'balance', 'amount': '0', 'currency': 'INR'}],
                }
            }
            resp = _requests.post(
                f'{self.BASE_URL}/air/orders',
                json=payload,
                headers=self._headers,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return resp.json().get('data', {})
            return {'error': f'Duffel order failed: {resp.status_code}'}
        except Exception as exc:
            logger.error('Duffel create_order failed: %s', exc)
            return {'error': str(exc)}

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a Duffel order and get cancellation details."""
        if not self.access_token:
            return {'error': 'Duffel not configured'}

        try:
            import requests as _requests
            # First create cancellation request
            resp = _requests.post(
                f'{self.BASE_URL}/air/order_cancellations',
                json={'data': {'order_id': order_id}},
                headers=self._headers,
                timeout=15,
            )
            if resp.status_code in (200, 201):
                cancellation = resp.json().get('data', {})
                cancellation_id = cancellation.get('id')
                # Confirm cancellation
                confirm_resp = _requests.post(
                    f'{self.BASE_URL}/air/order_cancellations/{cancellation_id}/actions/confirm',
                    headers=self._headers,
                    timeout=15,
                )
                if confirm_resp.status_code in (200, 201):
                    return {'success': True, 'cancellation': confirm_resp.json().get('data', {})}
            return {'error': f'Cancellation failed: {resp.status_code}'}
        except Exception as exc:
            logger.error('Duffel cancel_order failed: %s', exc)
            return {'error': str(exc)}

    def map_duffel_offer_to_internal(self, offer: dict) -> dict:
        """Convert Duffel offer to our internal FlightFareClass-like structure."""
        slices = offer.get('slices', [])
        first_slice = slices[0] if slices else {}
        segments = first_slice.get('segments', [])
        first_seg = segments[0] if segments else {}

        # Extract pricing
        total_amount = offer.get('total_amount', '0')
        total_currency = offer.get('total_currency', 'INR')

        return {
            'duffel_offer_id': offer.get('id'),
            'source': 'duffel',
            'airline': first_seg.get('marketing_carrier', {}).get('name', ''),
            'airline_iata': first_seg.get('marketing_carrier', {}).get('iata_code', ''),
            'flight_number': (
                first_seg.get('marketing_carrier', {}).get('iata_code', '')
                + str(first_seg.get('marketing_carrier_flight_number', ''))
            ),
            'origin_iata': first_seg.get('origin', {}).get('iata_code', ''),
            'destination_iata': first_seg.get('destination', {}).get('iata_code', ''),
            'departure_time': first_seg.get('departing_at', ''),
            'arrival_time': first_seg.get('arriving_at', ''),
            'duration_minutes': self._parse_duration(first_slice.get('duration', 'PT0M')),
            'stops': len(segments) - 1,
            'cabin_class': offer.get('cabin_class', 'economy'),
            'fare_amount': float(total_amount),
            'currency': total_currency,
            'seats_available': offer.get('available_services', 1),
            'expires_at': offer.get('expires_at', ''),
            'conditions': {
                'refund_before_departure': offer.get('conditions', {}).get('refund_before_departure', {}),
                'change_before_departure': offer.get('conditions', {}).get('change_before_departure', {}),
            },
        }

    def _parse_duration(self, iso_duration: str) -> int:
        """Parse ISO 8601 duration to minutes. e.g. PT2H30M -> 150"""
        import re
        hours = int(re.search(r'(\d+)H', iso_duration).group(1)) if 'H' in iso_duration else 0
        minutes = int(re.search(r'(\d+)M', iso_duration).group(1)) if 'M' in iso_duration else 0
        return hours * 60 + minutes

    def _internal_fallback(self, origin: str, destination: str, date: str) -> list:
        """Return internal flight inventory when Duffel is unavailable."""
        try:
            from apps.flights.models import Flight
            import datetime
            flights = Flight.objects.filter(
                is_active=True,
                departure_time__date=date,
            ).select_related('airline')[:20]

            return [
                {
                    'source': 'internal',
                    'flight_number': getattr(f, 'flight_number', ''),
                    'airline': str(getattr(f, 'airline', '')),
                    'origin_iata': str(getattr(f, 'origin', '')),
                    'destination_iata': str(getattr(f, 'destination', '')),
                    'departure_time': str(f.departure_time),
                    'arrival_time': str(getattr(f, 'arrival_time', '')),
                    'fare_amount': float(getattr(f, 'economy_price', 0)),
                    'currency': 'INR',
                    'seats_available': getattr(f, 'available_seats', 0),
                }
                for f in flights
            ]
        except Exception as exc:
            logger.warning('_internal_fallback failed: %s', exc)
            return []


duffel_client = DuffelClient()
