"""
ZygoTrip OTA — Production Load Test Scenarios.

Usage:
    locust -f locustfile.py --host=http://localhost:8000

Scenarios mirror real OTA traffic distribution:
  - 40% search / autosuggest (read-heavy)
  - 25% hotel detail + room availability
  - 15% booking context creation (price lock)
  - 10% booking + payment flow
  - 10% user account / wallet

Targets:
  - Search P95 < 200ms @ 10k concurrent
  - Booking P95 < 500ms @ 1000/min
  - Availability < 100ms
"""

import random
import string
from locust import HttpUser, task, between, tag

# ── Sample data ──────────────────────────────────────────────────────────

CITIES = [
    'Mumbai', 'Delhi', 'Bengaluru', 'Hyderabad', 'Chennai',
    'Kolkata', 'Pune', 'Jaipur', 'Goa', 'Kochi',
    'Udaipur', 'Varanasi', 'Agra', 'Shimla', 'Manali',
    'Rishikesh', 'Mysuru', 'Ooty', 'Coorg', 'Munnar',
]

NOISE_QUERIES = [
    'hotels in {}', '{} hotels', 'best hotels {}',
    'cheap {} stay', '{} resorts', 'budget {} rooms',
]


def _random_dates():
    """Return check_in/check_out as ISO strings 7–30 days from now."""
    import datetime
    offset = random.randint(7, 30)
    ci = datetime.date.today() + datetime.timedelta(days=offset)
    co = ci + datetime.timedelta(days=random.randint(1, 5))
    return ci.isoformat(), co.isoformat()


def _random_email():
    slug = ''.join(random.choices(string.ascii_lowercase, k=8))
    return f'loadtest_{slug}@test.zygotrip.com'


# ── User behaviour classes ───────────────────────────────────────────────


class SearchUser(HttpUser):
    """Simulates travelers browsing/searching (40% of traffic)."""
    weight = 40
    wait_time = between(1, 3)

    @tag('search')
    @task(5)
    def search_city(self):
        city = random.choice(CITIES)
        ci, co = _random_dates()
        self.client.get(
            '/api/search/',
            params={'q': city, 'check_in': ci, 'check_out': co, 'guests': 2},
            name='/api/search/?q=[city]',
        )

    @tag('search')
    @task(3)
    def search_noise_query(self):
        """Test noise-word stripping (e.g. 'bangalore hotels')."""
        city = random.choice(CITIES)
        query = random.choice(NOISE_QUERIES).format(city)
        self.client.get(
            '/api/search/',
            params={'q': query},
            name='/api/search/?q=[noise_query]',
        )

    @tag('search')
    @task(4)
    def autosuggest_cities(self):
        city = random.choice(CITIES)
        prefix = city[:random.randint(2, 4)]
        self.client.get(
            '/api/cities/',
            params={'q': prefix},
            name='/api/cities/?q=[prefix]',
        )

    @tag('search')
    @task(2)
    def location_autocomplete(self):
        city = random.choice(CITIES)
        self.client.get(
            '/api/locations/',
            params={'q': city[:3]},
            name='/api/locations/?q=[prefix]',
        )


class BrowseUser(HttpUser):
    """Simulates users browsing hotel details (25% of traffic)."""
    weight = 25
    wait_time = between(2, 5)

    @tag('browse')
    @task(3)
    def hotel_list(self):
        self.client.get(
            '/api/v1/hotels/',
            params={'page': random.randint(1, 5)},
            name='/api/v1/hotels/?page=[n]',
        )

    @tag('browse')
    @task(2)
    def hotel_detail(self):
        """Fetch a random hotel detail page."""
        # First get a list to pick from
        with self.client.get('/api/v1/hotels/', params={'page': 1}, catch_response=True, name='/api/v1/hotels/ (for slug)') as resp:
            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                if results:
                    slug = results[0].get('slug', '')
                    if slug:
                        self.client.get(f'/api/v1/hotels/{slug}/', name='/api/v1/hotels/[slug]/')
                        return
            resp.success()

    @tag('browse')
    @task(1)
    def featured_offers(self):
        self.client.get('/api/v1/offers/featured/', name='/api/v1/offers/featured/')


class BookingUser(HttpUser):
    """Simulates the booking funnel — context creation + hold (15%)."""
    weight = 15
    wait_time = between(3, 8)

    @tag('booking')
    @task(2)
    def create_booking_context(self):
        """Create a price-locked booking context."""
        ci, co = _random_dates()
        self.client.post(
            '/api/v1/booking/context/',
            json={
                'property_uuid': '00000000-0000-0000-0000-000000000001',
                'room_type_uuid': '00000000-0000-0000-0000-000000000001',
                'checkin': ci,
                'checkout': co,
                'adults': 2,
                'children': 0,
                'rooms': 1,
                'meal_plan': 'R+B',
            },
            name='/api/v1/booking/context/ [POST]',
        )

    @tag('booking')
    @task(1)
    def promo_apply(self):
        self.client.post(
            '/api/v1/promo/apply/',
            json={'code': 'WELCOME10', 'amount': 5000},
            name='/api/v1/promo/apply/ [POST]',
        )


class PaymentUser(HttpUser):
    """Simulates payment + confirmation flow (10%)."""
    weight = 10
    wait_time = between(5, 15)

    @tag('payment')
    @task
    def checkout_flow(self):
        """Simulates the full checkout saga (without actual payment)."""
        ci, co = _random_dates()
        # Step 1: Create checkout session
        self.client.post(
            '/api/v1/checkout/session/',
            json={
                'property_uuid': '00000000-0000-0000-0000-000000000001',
                'room_type_uuid': '00000000-0000-0000-0000-000000000001',
                'check_in': ci,
                'check_out': co,
                'rooms': 1,
                'adults': 2,
                'guest_name': 'Load Test',
                'guest_email': _random_email(),
                'guest_phone': '9876543210',
            },
            name='/api/v1/checkout/session/ [POST]',
        )


class AccountUser(HttpUser):
    """Simulates account/wallet operations (10%)."""
    weight = 10
    wait_time = between(3, 10)

    @tag('account')
    @task(2)
    def health_check(self):
        self.client.get('/api/health/live/', name='/api/health/live/')

    @tag('account')
    @task(1)
    def health_detailed(self):
        self.client.get('/api/health/detailed/', name='/api/health/detailed/')

    @tag('account')
    @task(1)
    def wallet_balance(self):
        self.client.get(
            '/api/v1/wallet/balance/',
            name='/api/v1/wallet/balance/',
        )

    @tag('account')
    @task(1)
    def notifications(self):
        self.client.get(
            '/api/v1/notifications/',
            name='/api/v1/notifications/',
        )
