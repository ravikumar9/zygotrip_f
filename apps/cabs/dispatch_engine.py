"""
Cab Dispatch Engine — Driver matching and real-time tracking.

Implements:
- Nearest driver matching with haversine distance
- Driver availability management
- ETA calculation
- Live location tracking via WebSocket-ready updates
- Dispatch queue with automatic reassignment
"""
import logging
import math
import random
import string
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone

from apps.core.models import TimeStampedModel

logger = logging.getLogger('zygotrip.cabs')


class DriverLocation(TimeStampedModel):
    """Real-time driver location tracking."""
    driver = models.OneToOneField(
        'cabs.Driver', on_delete=models.CASCADE, related_name='live_location',
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    heading = models.FloatField(default=0, help_text='Compass heading in degrees')
    speed_kmh = models.FloatField(default=0)
    accuracy_meters = models.FloatField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'cabs'
        indexes = [
            models.Index(fields=['last_updated'], name='driverloc_updated_idx'),
        ]

    def __str__(self):
        return f"Location({self.driver}: {self.latitude},{self.longitude})"


class DispatchRequest(TimeStampedModel):
    """Dispatch request submitted when a user books a cab."""
    STATUS_SEARCHING = 'searching'
    STATUS_DRIVER_FOUND = 'driver_found'
    STATUS_DRIVER_ACCEPTED = 'driver_accepted'
    STATUS_NO_DRIVERS = 'no_drivers'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_SEARCHING, 'Searching for Driver'),
        (STATUS_DRIVER_FOUND, 'Driver Found'),
        (STATUS_DRIVER_ACCEPTED, 'Driver Accepted'),
        (STATUS_NO_DRIVERS, 'No Drivers Available'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    booking = models.OneToOneField(
        'cabs.CabBooking', on_delete=models.CASCADE, related_name='dispatch',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SEARCHING)
    pickup_latitude = models.DecimalField(max_digits=10, decimal_places=7)
    pickup_longitude = models.DecimalField(max_digits=10, decimal_places=7)
    drop_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    drop_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Matching
    matched_driver = models.ForeignKey(
        'cabs.Driver', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dispatch_requests',
    )
    search_radius_km = models.FloatField(default=5.0)
    drivers_contacted = models.IntegerField(default=0)
    match_attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)

    # ETA
    estimated_pickup_minutes = models.IntegerField(null=True, blank=True)
    estimated_trip_minutes = models.IntegerField(null=True, blank=True)

    # Timing
    expires_at = models.DateTimeField()
    matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'cabs'
        indexes = [
            models.Index(fields=['status', 'expires_at'], name='dispatch_status_exp_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)


def _haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula."""
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def find_nearest_drivers(pickup_lat, pickup_lng, radius_km=5.0, cab_type=None, limit=10):
    """
    Find available drivers within radius, sorted by distance.
    Uses Redis cache for recent locations, falls back to DB.
    """
    from apps.cabs.models import Driver

    # Get all active driver locations updated in last 15 minutes
    cutoff = timezone.now() - timedelta(minutes=15)
    locations = DriverLocation.objects.filter(
        last_updated__gte=cutoff,
        driver__is_active=True,
    ).select_related('driver', 'driver__cab')

    if cab_type:
        locations = locations.filter(driver__cab__cab_type=cab_type)

    # Calculate distances and filter by radius
    candidates = []
    for loc in locations:
        dist = _haversine_km(pickup_lat, pickup_lng, loc.latitude, loc.longitude)
        if dist <= radius_km:
            candidates.append({
                'driver_id': loc.driver_id,
                'driver_name': loc.driver.name,
                'driver_phone': loc.driver.phone,
                'driver_rating': float(loc.driver.rating) if loc.driver.rating else 0,
                'cab_id': loc.driver.cab_id,
                'distance_km': round(dist, 2),
                'eta_minutes': max(1, int(dist * 3)),  # ~20 km/h in city
                'latitude': float(loc.latitude),
                'longitude': float(loc.longitude),
            })

    candidates.sort(key=lambda x: x['distance_km'])
    return candidates[:limit]


def dispatch_driver(booking, pickup_lat, pickup_lng, drop_lat=None, drop_lng=None,
                    cab_type=None, radius_km=5.0):
    """
    Main dispatch function. Finds nearest driver and creates dispatch request.
    
    Returns: DispatchRequest or None if no driver found.
    """
    nearest = find_nearest_drivers(pickup_lat, pickup_lng, radius_km, cab_type, limit=5)

    dispatch = DispatchRequest.objects.create(
        booking=booking,
        pickup_latitude=pickup_lat,
        pickup_longitude=pickup_lng,
        drop_latitude=drop_lat,
        drop_longitude=drop_lng,
        search_radius_km=radius_km,
        drivers_contacted=len(nearest),
    )

    if not nearest:
        dispatch.status = DispatchRequest.STATUS_NO_DRIVERS
        dispatch.save(update_fields=['status', 'updated_at'])
        return dispatch

    # Assign the nearest available driver
    best = nearest[0]
    from apps.cabs.models import Driver
    try:
        driver = Driver.objects.get(id=best['driver_id'])
    except Driver.DoesNotExist:
        dispatch.status = DispatchRequest.STATUS_NO_DRIVERS
        dispatch.save(update_fields=['status', 'updated_at'])
        return dispatch

    dispatch.matched_driver = driver
    dispatch.status = DispatchRequest.STATUS_DRIVER_FOUND
    dispatch.estimated_pickup_minutes = best['eta_minutes']
    dispatch.matched_at = timezone.now()
    dispatch.save(update_fields=[
        'matched_driver', 'status', 'estimated_pickup_minutes', 'matched_at', 'updated_at',
    ])

    # Generate OTP for rider-driver verification
    otp = ''.join(random.choices(string.digits, k=4))
    cache.set(f'cab_otp:{dispatch.id}', otp, timeout=1800)

    logger.info(
        'Dispatch %d: matched driver %s (%.1f km, ~%d min ETA)',
        dispatch.id, driver.name, best['distance_km'], best['eta_minutes'],
    )

    return dispatch


def update_driver_location(driver_id, latitude, longitude, heading=0, speed=0, accuracy=0):
    """Update driver's live location (called from driver app)."""
    loc, created = DriverLocation.objects.update_or_create(
        driver_id=driver_id,
        defaults={
            'latitude': latitude,
            'longitude': longitude,
            'heading': heading,
            'speed_kmh': speed,
            'accuracy_meters': accuracy,
        },
    )
    # Also cache in Redis for fast lookups
    cache.set(
        f'driver_loc:{driver_id}',
        {'lat': float(latitude), 'lng': float(longitude), 'ts': timezone.now().isoformat()},
        timeout=300,
    )
    return loc


def expire_stale_dispatches():
    """Expire dispatch requests that haven't been accepted. Runs via Celery."""
    expired = DispatchRequest.objects.filter(
        status__in=[DispatchRequest.STATUS_SEARCHING, DispatchRequest.STATUS_DRIVER_FOUND],
        expires_at__lt=timezone.now(),
    )
    count = expired.update(status=DispatchRequest.STATUS_EXPIRED)
    if count:
        logger.info('Expired %d stale dispatch requests', count)
    return count
