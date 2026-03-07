"""
Management command to seed marketplace data for testing and demo.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.core.marketplace_models import Destination, Category, Offer, SearchIndex


class Command(BaseCommand):
    help = 'Seeds initial marketplace data (destinations, categories, offers)'

    def handle(self, *args, **options):
        self.stdout.write('Seeding marketplace data...')
        
        # Create Categories
        categories = [
            {'name': 'Hotels', 'slug': 'hotels', 'icon': '🏨', 'description': 'Find and book premium hotels'},
            {'name': 'Buses', 'slug': 'buses', 'icon': '🚌', 'description': 'Book intercity bus tickets'},
            {'name': 'Packages', 'slug': 'packages', 'icon': '📦', 'description': 'Holiday packages with meals'},
            {'name': 'Cabs', 'slug': 'cabs', 'icon': '🚕', 'description': 'Book cabs and transfers'},
            {'name': 'Flights', 'slug': 'flights', 'icon': '✈️', 'description': 'Book domestic flights'},
            {'name': 'Trains', 'slug': 'trains', 'icon': '🚆', 'description': 'Book train tickets'},
        ]
        
        for idx, cat_data in enumerate(categories, 1):
            Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'icon': cat_data['icon'],
                    'description': cat_data['description'],
                    'is_active': True,
                    'priority': idx * 10
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(categories)} categories'))
        
        # Create Trending Destinations
        destinations = [
            {'name': 'Goa', 'country': 'India', 'state': 'Goa', 'description': 'Beautiful beaches and vibrant nightlife'},
            {'name': 'Jaipur', 'country': 'India', 'state': 'Rajasthan', 'description': 'The Pink City with majestic forts'},
            {'name': 'Kerala', 'country': 'India', 'state': 'Kerala', 'description': 'God\'s own country with backwaters'},
            {'name': 'Mumbai', 'country': 'India', 'state': 'Maharashtra', 'description': 'The city that never sleeps'},
            {'name': 'Udaipur', 'country': 'India', 'state': 'Rajasthan', 'description': 'City of lakes and palaces'},
            {'name': 'Shimla', 'country': 'India', 'state': 'Himachal Pradesh', 'description': 'Hill station with scenic beauty'},
        ]
        
        for idx, dest_data in enumerate(destinations, 1):
            Destination.objects.get_or_create(
                name=dest_data['name'],
                defaults={
                    'country': dest_data['country'],
                    'state': dest_data['state'],
                    'description': dest_data['description'],
                    'is_trending': True,
                    'priority': idx * 10,
                    'search_count': 100 - (idx * 10)
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(destinations)} trending destinations'))
        
        # Create Special Offers
        now = timezone.now()
        offers = [
            {
                'title': 'Flat 20% OFF on Hotel Bookings',
                'subtitle': 'Book any hotel and get instant discount',
                'offer_type': 'PERCENTAGE',
                'discount_value': 20,
                'code': 'HOTEL20',
                'min_booking_amount': 1000,
                'max_discount': 2000,
            },
            {
                'title': 'Save ₹500 on Bus Tickets',
                'subtitle': 'Valid on all routes',
                'offer_type': 'FLAT',
                'discount_value': 500,
                'code': 'BUS500',
                'min_booking_amount': 800,
                'max_discount': 500,
            },
            {
                'title': '25% OFF on Holiday Packages',
                'subtitle': 'Plan your dream vacation',
                'offer_type': 'PERCENTAGE',
                'discount_value': 25,
                'code': 'HOLIDAY25',
                'min_booking_amount': 5000,
                'max_discount': 5000,
            },
        ]
        
        for offer_data in offers:
            Offer.objects.get_or_create(
                code=offer_data['code'],
                defaults={
                    'title': offer_data['title'],
                    'subtitle': offer_data['subtitle'],
                    'offer_type': offer_data['offer_type'],
                    'discount_value': offer_data['discount_value'],
                    'min_booking_amount': offer_data['min_booking_amount'],
                    'max_discount': offer_data.get('max_discount'),
                    'valid_from': now,
                    'valid_until': now + timedelta(days=30),
                    'is_active': True,
                    'priority': 10
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(offers)} offers'))
        
        # Create Search Index entries
        search_entries = [
            {'search_type': 'CITY', 'name': 'Mumbai', 'city': 'Mumbai', 'state': 'Maharashtra'},
            {'search_type': 'CITY', 'name': 'Delhi', 'city': 'Delhi', 'state': 'Delhi'},
            {'search_type': 'CITY', 'name': 'Bangalore', 'city': 'Bangalore', 'state': 'Karnataka'},
            {'search_type': 'AREA', 'name': 'Bandra', 'city': 'Mumbai', 'state': 'Maharashtra'},
            {'search_type': 'AREA', 'name': 'Andheri', 'city': 'Mumbai', 'state': 'Maharashtra'},
            {'search_type': 'LANDMARK', 'name': 'Gateway of India', 'city': 'Mumbai', 'state': 'Maharashtra'},
        ]
        
        for entry in search_entries:
            SearchIndex.objects.get_or_create(
                search_type=entry['search_type'],
                name=entry['name'],
                defaults={
                    'city': entry['city'],
                    'state': entry['state'],
                    'is_active': True,
                    'search_count': 0
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(search_entries)} search index entries'))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Marketplace data seeded successfully!'))