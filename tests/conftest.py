import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model
import factory
from factory import django as fdj, Faker, LazyFunction, SubFactory

User = get_user_model()


class UserFactory(fdj.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f'user{n}@zygotest.com')
    full_name = Faker('name')
    phone = factory.Sequence(lambda n: f'+9198765{n:05d}')
    role = 'traveler'
    is_active = True


class CountryFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'core.Country'
        django_get_or_create = ('code',)

    code = 'IN'
    name = 'India'
    display_name = 'India'


class StateFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'core.State'
        django_get_or_create = ('country', 'code')

    country = SubFactory(CountryFactory)
    code = 'GA'
    name = 'Goa'
    display_name = 'Goa'


class CityFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'core.City'
        django_get_or_create = ('code',)

    state = SubFactory(StateFactory)
    name = 'Goa'
    display_name = 'Goa'
    code = 'GOA'
    latitude = Decimal('15.299300')
    longitude = Decimal('74.124000')


class PropertyFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'hotels.Property'

    owner = SubFactory(UserFactory, role='property_owner')
    name = Faker('company')
    property_type = 'Hotel'
    city = SubFactory(CityFactory)
    address = Faker('address')
    description = Faker('text')
    status = 'approved'
    agreement_signed = True
    is_active = True
    latitude = Decimal('15.2993')
    longitude = Decimal('74.1240')


class RoomTypeFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'rooms.RoomType'

    property = SubFactory(PropertyFactory)
    name = 'Deluxe Room'
    base_price = Decimal('2500.00')
    price_per_night = Decimal('2500.00')
    max_occupancy = 2
    available_count = 5


class WalletFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'wallet.Wallet'

    user = SubFactory(UserFactory)
    balance = Decimal('5000.00')
    locked_balance = Decimal('0.00')
    currency = 'INR'
    is_active = True


class BookingFactory(fdj.DjangoModelFactory):
    class Meta:
        model = 'booking.Booking'

    user = SubFactory(UserFactory)
    property = SubFactory(PropertyFactory)
    check_in = LazyFunction(lambda: date.today() + timedelta(days=7))
    check_out = LazyFunction(lambda: date.today() + timedelta(days=9))
    total_amount = Decimal('5500.00')
    status = 'confirmed'


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def user_factory(db):
    def _factory(**kwargs):
        return UserFactory(**kwargs)

    return _factory


@pytest.fixture
def property_obj(db):
    return PropertyFactory()


@pytest.fixture
def room_type(db, property_obj):
    return RoomTypeFactory(property=property_obj)


@pytest.fixture
def wallet(db, user):
    return WalletFactory(user=user)


@pytest.fixture
def booking(db, user, property_obj):
    return BookingFactory(user=user, property=property_obj)


@pytest.fixture
def booking_factory(db):
    def _factory(**kwargs):
        return BookingFactory(**kwargs)

    return _factory


@pytest.fixture
def wallet_factory(db):
    def _factory(**kwargs):
        return WalletFactory(**kwargs)

    return _factory
