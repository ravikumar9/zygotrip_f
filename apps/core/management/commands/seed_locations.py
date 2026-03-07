"""
Location Hierarchy Seeder
Populates India geo tree: Country → States → Cities → Localities

Critical: This is the foundation for intelligent search
Without this, autocomplete returns empty results
"""
from django.core.management.base import BaseCommand
from apps.core.location_models import Country, State, City, Locality, LocationSearchIndex
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed location hierarchy for India'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding location hierarchy...')
        
        # Create India country
        india, _ = Country.objects.get_or_create(
            code='IN',
            defaults={
                'name': 'India',
                'display_name': 'India',
                'is_active': True
            }
        )
        self.stdout.write(f'+ Country: {india.name}')
        
        # Seed states with major cities
        states_data = self.get_states_data()
        
        for state_data in states_data:
            state, _ = State.objects.get_or_create(
                country=india,
                code=state_data['code'],
                defaults={
                    'name': state_data['name'],
                    'display_name': state_data['display_name'],
                    'is_active': True
                }
            )
            
            # Seed cities for this state
            for city_data in state_data['cities']:
                city, _ = City.objects.get_or_create(
                    state=state,
                    code=city_data['code'],
                    defaults={
                        'name': city_data['name'],
                        'display_name': city_data['display_name'],
                        'alternate_names': city_data.get('alternate_names', ''),
                        'latitude': Decimal(str(city_data['latitude'])),
                        'longitude': Decimal(str(city_data['longitude'])),
                        'ne_lat': Decimal(str(city_data.get('ne_lat', float(city_data['latitude']) + 0.1))),
                        'ne_lng': Decimal(str(city_data.get('ne_lng', float(city_data['longitude']) + 0.1))),
                        'sw_lat': Decimal(str(city_data.get('sw_lat', float(city_data['latitude']) - 0.1))),
                        'sw_lng': Decimal(str(city_data.get('sw_lng', float(city_data['longitude']) - 0.1))),
                        'hotel_count': 0,
                        'popularity_score': city_data.get('popularity_score', 50),
                        'is_top_destination': city_data.get('is_top_destination', False),
                        'is_active': True
                    }
                )
                
                # Seed localities for city
                if 'localities' in city_data:
                    for loc_data in city_data['localities']:
                        locality, _ = Locality.objects.get_or_create(
                            city=city,
                            name=loc_data['name'],
                            defaults={
                                'display_name': loc_data['display_name'],
                                'latitude': Decimal(loc_data['latitude']),
                                'longitude': Decimal(loc_data['longitude']),
                                'hotel_count': 0,
                                'locality_type': loc_data.get('type', 'tourist'),
                                'landmarks': loc_data.get('landmarks', ''),
                                'is_active': True
                            }
                        )
        
        self.stdout.write(f'+ Seeded {State.objects.count()} states')
        self.stdout.write(f'+ Seeded {City.objects.count()} cities')
        self.stdout.write(f'+ Seeded {Locality.objects.count()} localities')
        
        # Build search index
        self.build_search_index()
        
        self.stdout.write(self.style.SUCCESS('Location hierarchy seeded successfully'))
    
    def build_search_index(self):
        """Populate LocationSearchIndex table from location data"""
        LocationSearchIndex.objects.all().delete()
        
        # Index all cities
        for city in City.objects.filter(is_active=True):
            LocationSearchIndex.objects.create(
                entity_type='city',
                entity_id=city.id,
                display_name=city.display_name,
                search_text=f"{city.name} {city.alternate_names}".lower(),
                alternate_names=city.alternate_names,
                context_city=city,
                context_state=city.state,
                context_country=city.state.country,
                search_score=city.popularity_score,
                latitude=city.latitude,
                longitude=city.longitude,
                is_clickable=True,
                is_active=True
            )
        
        # Index all localities
        for locality in Locality.objects.filter(is_active=True):
            LocationSearchIndex.objects.create(
                entity_type='locality',
                entity_id=locality.id,
                display_name=f"{locality.display_name}, {locality.city.name}",
                search_text=f"{locality.name} {locality.landmarks}".lower(),
                context_city=locality.city,
                context_state=locality.city.state,
                context_country=locality.city.state.country,
                search_score=locality.popularity_score,
                latitude=locality.latitude,
                longitude=locality.longitude,
                is_clickable=True,
                is_active=True
            )
        
        self.stdout.write(f'+ Built search index: {LocationSearchIndex.objects.count()} entries')
    
    def get_states_data(self):
        """Return comprehensive state/city data for India"""
        return [
            {
                'code': 'KA',
                'name': 'Karnataka',
                'display_name': 'Karnataka',
                'cities': [
                    {
                        'code': 'BLR',
                        'name': 'Bangalore',
                        'display_name': 'Bangalore',
                        'alternate_names': 'Bengaluru, Bengalooru',
                        'latitude': '12.9716',
                        'longitude': '77.5946',
                        'popularity_score': 95,
                        'is_top_destination': True,
                        'localities': [
                            {
                                'name': 'Koramangala',
                                'display_name': 'Koramangala',
                                'latitude': '12.9352',
                                'longitude': '77.6245',
                                'type': 'business',
                                'landmarks': 'Forum Mall, Sony World'
                            },
                            {
                                'name': 'Indiranagar',
                                'display_name': 'Indiranagar',
                                'latitude': '12.9784',
                                'longitude': '77.6408',
                                'type': 'residential',
                                'landmarks': '100 Feet Road, CMH Road'
                            }
                        ]
                    },
                    {
                        'code': 'COORG',
                        'name': 'Coorg',
                        'display_name': 'Coorg',
                        'alternate_names': 'Kodagu, Madikeri',
                        'latitude': '12.4244',
                        'longitude': '75.7382',
                        'popularity_score': 88,
                        'is_top_destination': True,
                        'localities': [
                            {
                                'name': 'Madikeri',
                                'display_name': 'Madikeri',
                                'latitude': '12.4244',
                                'longitude': '75.7382',
                                'type': 'hill_station',
                                'landmarks': 'Raja Seat, Abbey Falls'
                            },
                            {
                                'name': 'Virajpet',
                                'display_name': 'Virajpet',
                                'latitude': '12.1961',
                                'longitude': '75.8046',
                                'type': 'hill_station',
                                'landmarks': 'Iruppu Falls, Nagarhole'
                            }
                        ]
                    },
                    {
                        'code': 'MYS',
                        'name': 'Mysore',
                        'display_name': 'Mysore',
                        'alternate_names': 'Mysuru',
                        'latitude': '12.2958',
                        'longitude': '76.6394',
                        'popularity_score': 82,
                        'is_top_destination': True
                    }
                ]
            },
            {
                'code': 'GOA',
                'name': 'Goa',
                'display_name': 'Goa',
                'cities': [
                    {
                        'code': 'GOA_NORTH',
                        'name': 'North Goa',
                        'display_name': 'North Goa',
                        'latitude': '15.5057',
                        'longitude': '73.8157',
                        'popularity_score': 98,
                        'is_top_destination': True,
                        'localities': [
                            {
                                'name': 'Calangute',
                                'display_name': 'Calangute Beach',
                                'latitude': '15.5446',
                                'longitude': '73.7559',
                                'type': 'beach',
                                'landmarks': 'Calangute Beach, Baga Beach'
                            },
                            {
                                'name': 'Anjuna',
                                'display_name': 'Anjuna',
                                'latitude': '15.5734',
                                'longitude': '73.7405',
                                'type': 'beach',
                                'landmarks': 'Anjuna Flea Market, Curlies'
                            }
                        ]
                    },
                    {
                        'code': 'GOA_SOUTH',
                        'name': 'South Goa',
                        'display_name': 'South Goa',
                        'latitude': '15.0819',
                        'longitude': '74.0863',
                        'popularity_score': 91,
                        'is_top_destination': True,
                        'localities': [
                            {
                                'name': 'Palolem',
                                'display_name': 'Palolem Beach',
                                'latitude': '15.0099',
                                'longitude': '74.0233',
                                'type': 'beach',
                                'landmarks': 'Palolem Beach, Butterfly Beach'
                            }
                        ]
                    }
                ]
            },
            {
                'code': 'MH',
                'name': 'Maharashtra',
                'display_name': 'Maharashtra',
                'cities': [
                    {
                        'code': 'BOM',
                        'name': 'Mumbai',
                        'display_name': 'Mumbai',
                        'alternate_names': 'Bombay',
                        'latitude': '19.0760',
                        'longitude': '72.8777',
                        'popularity_score': 100,
                        'is_top_destination': True,
                        'localities': [
                            {
                                'name': 'Colaba',
                                'display_name': 'Colaba',
                                'latitude': '18.9067',
                                'longitude': '72.8147',
                                'type': 'tourist',
                                'landmarks': 'Gateway of India, Taj Hotel'
                            },
                            {
                                'name': 'Bandra',
                                'display_name': 'Bandra',
                                'latitude': '19.0596',
                                'longitude': '72.8295',
                                'type': 'residential',
                                'landmarks': 'Bandra Fort, Linking Road'
                            }
                        ]
                    },
                    {
                        'code': 'PUN',
                        'name': 'Pune',
                        'display_name': 'Pune',
                        'latitude': '18.5204',
                        'longitude': '73.8567',
                        'popularity_score': 85,
                        'is_top_destination': True
                    }
                ]
            },
            {
                'code': 'DL',
                'name': 'Delhi',
                'display_name': 'Delhi',
                'cities': [
                    {
                        'code': 'DEL',
                        'name': 'New Delhi',
                        'display_name': 'New Delhi',
                        'alternate_names': 'Delhi, NCR',
                        'latitude': '28.6139',
                        'longitude': '77.2090',
                        'popularity_score': 100,
                        'is_top_destination': True,
                        'localities': [
                            {
                                'name': 'Connaught Place',
                                'display_name': 'Connaught Place',
                                'latitude': '28.6315',
                                'longitude': '77.2167',
                                'type': 'business',
                                'landmarks': 'CP, Palika Bazaar'
                            },
                            {
                                'name': 'Aerocity',
                                'display_name': 'Aerocity',
                                'latitude': '28.5562',
                                'longitude': '77.1180',
                                'type': 'airport',
                                'landmarks': 'IGI Airport, Worldmark'
                            }
                        ]
                    }
                ]
            },
            {
                'code': 'RJ',
                'name': 'Rajasthan',
                'display_name': 'Rajasthan',
                'cities': [
                    {
                        'code': 'JAI',
                        'name': 'Jaipur',
                        'display_name': 'Jaipur',
                        'alternate_names': 'Pink City',
                        'latitude': '26.9124',
                        'longitude': '75.7873',
                        'popularity_score': 93,
                        'is_top_destination': True
                    },
                    {
                        'code': 'UDR',
                        'name': 'Udaipur',
                        'display_name': 'Udaipur',
                        'latitude': '24.5854',
                        'longitude': '73.7125',
                        'popularity_score': 90,
                        'is_top_destination': True
                    }
                ]
            }
        ]