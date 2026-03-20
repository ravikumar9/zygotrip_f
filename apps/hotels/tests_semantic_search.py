from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.location_models import City, Country, State
from apps.hotels.models import HotelEmbedding, Property


class SemanticSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email='owner@example.com',
            password='pass12345',
            full_name='Hotel Owner',
            role='property_owner',
        )
        country = Country.objects.create(name='India', code='IN')
        country.display_name = 'India'
        country.save(update_fields=['display_name'])
        state = State.objects.create(name='Karnataka', display_name='Karnataka', code='KA', country=country)
        city = City.objects.create(
            name='Bengaluru',
            display_name='Bengaluru',
            code='BLR',
            state=state,
            latitude=12.9716,
            longitude=77.5946,
        )

        self.property = Property.objects.create(
            owner=self.owner,
            name='City Center Residency',
            property_type='Hotel',
            city=city,
            area='MG Road',
            landmark='Metro',
            country='India',
            address='1 MG Road',
            description='Central business hotel with breakfast and wifi',
            latitude=12.9716,
            longitude=77.5946,
            status='approved',
            agreement_signed=True,
        )
        HotelEmbedding.objects.create(
            property=self.property,
            embedding=[0.1, 0.2, 0.3],
            embedding_model='text-embedding-3-small',
            content_hash='abc',
            content_text='business hotel mg road',
        )

    def test_semantic_endpoint_short_query(self):
        resp = self.client.get('/api/v1/hotels/semantic-search/?q=a')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['results'], [])
