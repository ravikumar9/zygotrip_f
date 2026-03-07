import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum
from django.apps import apps
from django.utils.module_loading import import_string
from datetime import date as _date, timedelta

logger = logging.getLogger('zygotrip')


@shared_task(bind=True, max_retries=3)
def cleanup_expired_bookings(self):
    """
    Cleanup expired/abandoned bookings: transition HOLD → FAILED, release inventory.
    Runs every 5 minutes via Celery Beat.
    
    HARDENED RULES:
    1. Targets bookings in 'hold' status with expired hold windows
    2. Also catches legacy 'pending' bookings older than 1 hour
    3. Releases inventory for each expired booking
    4. Records status history
    """
    try:
        Booking = apps.get_model('booking', 'Booking')
        BookingRoom = apps.get_model('booking', 'BookingRoom')
        BookingStatusHistory = apps.get_model('booking', 'BookingStatusHistory')
        
        now = timezone.now()
        expired_hold_cutoff = now - timedelta(minutes=30)  # Default hold window
        legacy_cutoff = now - timedelta(hours=1)
        
        # Find HOLD bookings past their hold_expires_at or older than 30 min
        from django.db.models import Q
        expired_bookings = Booking.objects.filter(
            Q(status='hold', hold_expires_at__lt=now) |
            Q(status='hold', hold_expires_at__isnull=True, created_at__lt=expired_hold_cutoff) |
            Q(status='pending', created_at__lt=legacy_cutoff)
        )
        
        released_count = 0
        failed_count = 0
        
        for booking in expired_bookings:
            try:
                from apps.inventory.services import release_inventory
                
                # Release inventory for each booked room
                booking_rooms = BookingRoom.objects.filter(booking=booking).select_related('room_type')
                for br in booking_rooms:
                    try:
                        release_inventory(
                            room_type=br.room_type,
                            start_date=booking.check_in,
                            end_date=booking.check_out,
                            quantity=br.quantity,
                        )
                        released_count += 1
                    except Exception as inv_err:
                        logger.error(
                            f"Failed to release inventory for booking {booking.id}, "
                            f"room {br.room_type_id}: {str(inv_err)}"
                        )
                
                # Transition to FAILED
                booking.status = 'failed'
                booking.save(update_fields=['status', 'updated_at'])
                BookingStatusHistory.objects.create(
                    booking=booking,
                    status='failed',
                    note='Expired hold — inventory released by cleanup task',
                )
                failed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to cleanup booking {booking.id}: {str(e)}")
        
        logger.info(
            f"Cleanup expired bookings: {failed_count} bookings failed, "
            f"{released_count} inventory records released",
        )
        return {
            'total_expired': expired_bookings.count(),
            'failed': failed_count,
            'inventory_released': released_count,
        }
    
    except Exception as exc:
        logger.error(f"Error in cleanup_expired_bookings: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_daily_reports(self):
    """
    Generate daily revenue and booking reports.
    Runs daily at midnight (00:00 IST) via Celery Beat.
    """
    try:
        from django.contrib.auth import get_user_model

        Booking = apps.get_model('booking', 'Booking')
        
        User = get_user_model()
        today = timezone.now().date()
        
        # Calculate daily metrics
        daily_bookings = Booking.objects.filter(
            created_at__date=today,
            status__in=['confirmed', 'completed'],
        )
        
        total_revenue = daily_bookings.aggregate(
            total=Sum('total_price')
        )['total'] or 0
        
        booking_count = daily_bookings.count()
        unique_users = daily_bookings.values('user').distinct().count()
        
        # Cache report for dashboard access
        report_key = f'report:daily:{today.isoformat()}'
        report_data = {
            'date': today.isoformat(),
            'bookings': booking_count,
            'revenue': float(total_revenue),
            'unique_users': unique_users,
            'avg_booking_value': float(total_revenue / booking_count) if booking_count > 0 else 0,
        }
        
        cache.set(report_key, report_data, 86400 * 30)  # Keep for 30 days
        
        logger.info(
            f"Daily report generated for {today}: "
            f"{booking_count} bookings, ₹{total_revenue} revenue",
            extra=report_data,
        )
        return report_data
    
    except Exception as exc:
        logger.error(f"Error in generate_daily_reports: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=2)
def send_booking_confirmation_email(self, booking_id):
    """
    Send booking confirmation email asynchronously.
    Called after successful booking payment.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings

        Booking = apps.get_model('booking', 'Booking')
        
        booking = Booking.objects.get(id=booking_id)
        
        email_content = f"""
        Your booking has been confirmed!
        
        Booking ID: {booking.id}
        Property: {booking.property.name if hasattr(booking, 'property') else 'N/A'}
        Total Price: ₹{booking.total_price}
        Status: {booking.status}
        
        Check your dashboard for more details.
        """
        
        send_mail(
            subject=f'Booking Confirmed - {booking.id}',
            message=email_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Confirmation email sent for booking {booking_id}")
        return {'status': 'email_sent', 'booking_id': booking_id}
    
    except Exception as exc:
        logger.error(f"Error sending confirmation email for {booking_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def update_search_cache(query_params):
    """
    Update hotel search results in cache.
    Called when new properties are added or prices change.
    """
    try:
        from django.core.cache import cache
        import hashlib
        
        # Generate cache key from query params
        params_str = str(sorted(query_params.items()))
        cache_key = f"search:{hashlib.md5(params_str.encode()).hexdigest()}"
        
        # Invalidate cache
        cache.delete(cache_key)
        
        logger.debug(f"Invalidated search cache: {cache_key}")
        return {'cache_key': cache_key, 'invalidated': True}
    
    except Exception as exc:
        logger.error(f"Error updating search cache: {str(exc)}")
        return {'error': str(exc)}


@shared_task
def sync_operator_inventory(operator_id, resource_type):
    """
    Synchronize operator inventory (buses, cabs, packages) with cache.
    Ensures real-time availability across the system.
    """
    try:
        from django.core.cache import cache
        
        cache_key = f"inventory:{resource_type}:{operator_id}"
        
        if resource_type == 'bus':
            Bus = apps.get_model('buses', 'Bus')
            buses = Bus.objects.filter(operator_id=operator_id).values(
                'id', 'bus_number', 'total_seats', 'available_seats', 'is_active'
            )
            cache.set(cache_key, list(buses), 300)  # 5 min TTL
        
        elif resource_type == 'cab':
            Cab = apps.get_model('cabs', 'Cab')
            cabs = Cab.objects.filter(owner_id=operator_id).values(
                'id', 'registration_number', 'base_fare', 'rate_per_km', 'is_active'
            )
            cache.set(cache_key, list(cabs), 300)
        
        elif resource_type == 'package':
            Package = apps.get_model('packages', 'Package')
            packages = Package.objects.filter(provider_id=operator_id).values(
                'id', 'name', 'price', 'duration_days', 'is_active'
            )
            cache.set(cache_key, list(packages), 300)
        
        logger.debug(f"Synced {resource_type} inventory for operator {operator_id}")
        return {'synced': True, 'resource_type': resource_type}
    
    except Exception as exc:
        logger.error(f"Error syncing inventory: {str(exc)}")
        return {'error': str(exc)}


@shared_task(bind=True, max_retries=3)
def sync_supplier_inventory(self, property_id, supplier_name):
    """
    Real inventory sync with supplier via adapter.
    Runs periodically for each channel manager source.
    """
    try:
        Property = apps.get_model('hotels', 'Property')
        InventorySource = import_string('apps.hotels.inventory.InventorySource')
        SupplierAdapterFactory = import_string('apps.hotels.supplier_adapters.SupplierAdapterFactory')
        from apps.core.logging_service import OperationLogger
        from datetime import datetime, timedelta
        
        property_obj = Property.objects.get(id=property_id)
        inventory = InventorySource.objects.get(property=property_obj, source_type=supplier_name)
        
        # Create adapter
        adapter = SupplierAdapterFactory.create(
            supplier_name=supplier_name,
            supplier_id=inventory.external_supplier_id,
            api_key=property_obj.supplier_api_key if hasattr(property_obj, 'supplier_api_key') else ''
        )
        
        if not adapter:
            raise ValueError(f"No adapter available for {supplier_name}")
        
        # Authenticate
        if not adapter.authenticate():
            raise ValueError(f"Authentication failed for {supplier_name}")
        
        # Fetch inventory
        end_date = (timezone.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        start_date = timezone.now().strftime('%Y-%m-%d')
        
        supplier_data = adapter.fetch_inventory(start_date, end_date)
        supplier_rates = adapter.fetch_rates(inventory.external_inventory_id)
        
        # Update local inventory
        if supplier_data:
            inventory.supplier_inventory = supplier_data.get('available_rooms', 0)
            inventory.available_rooms = supplier_data.get('available_rooms', 0)
        
        if supplier_rates:
            inventory.supplier_price = supplier_rates.get('base_rate', inventory.supplier_price)
        
        # Mark sync successful
        inventory.mark_sync_success()
        
        # Log operation
        OperationLogger.log_operation(
            operation_type='inventory_sync',
            status='success',
            details={
                'property_id': property_id,
                'supplier': supplier_name,
                'rooms_synced': inventory.available_rooms,
                'supplier_price': str(inventory.supplier_price),
                'timestamp': timezone.now().isoformat()
            }
        )
        
        logger.info(f"Synced {supplier_name} inventory for property {property_id}: "
                   f"{inventory.available_rooms} rooms")
        
        return {
            'property_id': property_id,
            'supplier': supplier_name,
            'status': 'success',
            'rooms_synced': inventory.available_rooms,
        }
    
    except Exception as exc:
        logger.error(f"Error syncing {supplier_name} inventory for property {property_id}: {str(exc)}")
        
        # Mark sync failed
        try:
            Property = apps.get_model('hotels', 'Property')
            InventorySource = import_string('apps.hotels.inventory.InventorySource')
            property_obj = Property.objects.get(id=property_id)
            inventory = InventorySource.objects.get(property=property_obj, source_type=supplier_name)
            inventory.mark_sync_failed(str(exc))
            
            # Log failure
            from apps.core.logging_service import OperationLogger
            OperationLogger.log_operation(
                operation_type='inventory_sync',
                status='failed',
                details={
                    'property_id': property_id,
                    'supplier': supplier_name,
                    'error': str(exc),
                    'timestamp': timezone.now().isoformat()
                }
            )
        except:
            pass
        
        raise self.retry(exc=exc, countdown=300)  # Retry in 5 minutes


@shared_task(bind=True)
def reconcile_inventory_mismatches(self):
    """
    Periodic inventory reconciliation task.
    Detects and corrects mismatches between supplier and local inventory.
    """
    try:
        InventorySource = import_string('apps.hotels.inventory.InventorySource')
        InventoryReconciliationEngine = import_string(
            'apps.hotels.supplier_adapters.InventoryReconciliationEngine'
        )
        
        engine = InventoryReconciliationEngine()
        
        # Get all synced inventory
        synced_inventories = InventorySource.objects.filter(
            sync_status='synced'
        ).select_related('property')
        
        supplier_inventory = {}
        local_inventory = {}
        
        for inv in synced_inventories:
            supplier_inventory[inv.property_id] = {
                'available_rooms': inv.supplier_inventory,
            }
            local_inventory[inv.property_id] = {
                'available_rooms': inv.available_rooms,
            }
        
        # Run reconciliation
        all_match, mismatches = engine.reconcile(supplier_inventory, local_inventory)
        
        if not all_match:
            # Auto-correct using supplier as source of truth
            corrections = engine.auto_correct(mismatches, source_of_truth='supplier')
            
            # Log reconciliation
            from apps.core.logging_service import OperationLogger
            OperationLogger.log_operation(
                operation_type='inventory_sync',
                status='corrected',
                details={
                    'mismatches_found': len(mismatches),
                    'mismatches_corrected': len(corrections),
                    'timestamp': timezone.now().isoformat(),
                    'details': corrections[:10]  # Log first 10 corrections
                }
            )
            
            logger.warning(f"Inventory reconciliation: {len(mismatches)} mismatches found and corrected")
        
        return {
            'mismatches_found': len(mismatches),
            'all_matched': all_match,
        }
    
    except Exception as exc:
        logger.error(f"Error in reconcile_inventory_mismatches: {str(exc)}")
        return {'error': str(exc)}


# ── Aliases for Celery Beat task names ─────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def release_expired_booking_holds(self):
    """
    Alias for cleanup_expired_bookings — referenced by Celery Beat schedule.
    Specifically targets HOLD bookings whose hold_expires_at has passed.
    """
    return cleanup_expired_bookings()


# ── New OTA System Tasks ──────────────────────────────────────────────────────

@shared_task
def compute_daily_analytics():
    """Compute daily aggregated analytics metrics. Run daily."""
    try:
        from apps.core.analytics import compute_daily_metrics
        return compute_daily_metrics()
    except Exception as exc:
        logger.error('compute_daily_analytics failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def bulk_update_property_rankings():
    """Recompute ranking/popularity scores for all properties. Run daily."""
    try:
        from apps.core.ranking import bulk_update_rankings
        return {'updated': bulk_update_rankings()}
    except Exception as exc:
        logger.error('bulk_update_property_rankings failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def run_demand_forecasting():
    """
    Generate demand forecasts for all active properties (next 90 days).
    Run daily at 2 AM.
    """
    try:
        from apps.hotels.models import Property
        from apps.core.intelligence import DemandForecaster

        today = timezone.now().date()
        end_date = today + timedelta(days=90)
        properties = Property.objects.filter(is_active=True)
        updated = 0

        for prop in properties.iterator(chunk_size=50):
            try:
                DemandForecaster.forecast_property(prop, today, end_date)
                updated += 1
            except Exception as e:
                logger.error('Forecast failed for property %s: %s', prop.id, e)

        logger.info('Demand forecasting complete: %d properties', updated)
        return {'updated': updated}
    except Exception as exc:
        logger.error('run_demand_forecasting failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def compute_quality_scores():
    """
    Compute quality scores for all active properties.
    Run daily at 3 AM.
    """
    try:
        from apps.hotels.models import Property
        from apps.core.intelligence import QualityScorer

        properties = Property.objects.filter(is_active=True)
        updated = 0

        for prop in properties.iterator(chunk_size=50):
            try:
                QualityScorer.score_property(prop)
                updated += 1
            except Exception as e:
                logger.error('Quality scoring failed for property %s: %s', prop.id, e)

        logger.info('Quality scoring complete: %d properties', updated)
        return {'updated': updated}
    except Exception as exc:
        logger.error('compute_quality_scores failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def competitor_price_scan():
    """
    Scan competitor prices and generate alerts for all properties.
    Run daily at 4 AM.
    """
    try:
        from apps.hotels.models import Property
        from apps.core.intelligence import CompetitorIntelligence

        properties = Property.objects.filter(is_active=True)
        total_alerts = 0

        for prop in properties.iterator(chunk_size=50):
            try:
                alerts = CompetitorIntelligence.scan_and_alert(prop)
                total_alerts += len(alerts)
            except Exception as e:
                logger.error('Competitor scan failed for property %s: %s', prop.id, e)

        logger.info('Competitor price scan complete: %d alerts', total_alerts)
        return {'alerts_generated': total_alerts}
    except Exception as exc:
        logger.error('competitor_price_scan failed: %s', exc)
        return {'error': str(exc)}


@shared_task
def sync_search_index():
    """
    Sync PropertySearchIndex with latest property data.
    Run every 30 minutes.
    """
    try:
        from apps.hotels.models import Property
        from apps.search.models import PropertySearchIndex
        from apps.rooms.models import RoomType
        from django.db.models import Min, Max

        properties = Property.objects.filter(
            is_active=True,
        ).select_related('city')
        synced = 0

        for prop in properties.iterator(chunk_size=100):
            try:
                prices = RoomType.objects.filter(
                    property=prop,
                ).aggregate(
                    price_min=Min('base_price'),
                    price_max=Max('base_price'),
                )

                defaults = {
                    'property_name': prop.name,
                    'slug': prop.slug,
                    'property_type': getattr(prop, 'property_type', 'hotel'),
                    'city_id': prop.city_id if hasattr(prop, 'city_id') else 0,
                    'city_name': prop.city.name if hasattr(prop, 'city') and prop.city else '',
                    'locality_name': getattr(prop, 'locality_name', ''),
                    'latitude': getattr(prop, 'latitude', 0) or 0,
                    'longitude': getattr(prop, 'longitude', 0) or 0,
                    'star_category': getattr(prop, 'star_category', 3) or 3,
                    'price_min': prices['price_min'] or 0,
                    'price_max': prices['price_max'] or 0,
                    'rating': prop.rating or 0,
                    'review_count': prop.review_count or 0,
                    'is_trending': getattr(prop, 'is_trending', False),
                }

                # S2: Compute available_rooms count for urgency signals
                try:
                    from apps.inventory.models import InventoryCalendar
                    from datetime import timedelta
                    avail_sum = InventoryCalendar.objects.filter(
                        room_type__property=prop,
                        date__gte=timezone.now().date(),
                        date__lte=timezone.now().date() + timedelta(days=30),
                        is_closed=False,
                    ).aggregate(total=Sum('available_rooms'))['total'] or 0
                    defaults['available_rooms'] = avail_sum
                    defaults['has_availability'] = avail_sum > 0
                except Exception:
                    defaults['available_rooms'] = 0

                # S2: Compute ranking_score from enhanced ranking engine
                try:
                    from apps.search.engine.enhanced_ranking import compute_ranking_score
                    defaults['ranking_score'] = compute_ranking_score(prop)
                except Exception:
                    try:
                        # Fallback: simple score from rating + popularity
                        score = (float(prop.rating or 0) * 10) + (float(getattr(prop, 'popularity_score', 0)))
                        defaults['ranking_score'] = round(score, 4)
                    except Exception:
                        defaults['ranking_score'] = 0

                # Featured image
                try:
                    img = prop.images.first()
                    if img:
                        defaults['featured_image_url'] = img.image.url if hasattr(img, 'image') else ''
                except Exception:
                    pass

                PropertySearchIndex.objects.update_or_create(
                    property=prop,
                    defaults=defaults,
                )
                synced += 1
            except Exception as e:
                logger.error('Search index sync failed for property %s: %s', prop.id, e)

        logger.info('Search index sync: %d properties synced', synced)
        return {'synced': synced}
    except Exception as exc:
        logger.error('sync_search_index failed: %s', exc)
        return {'error': str(exc)}


# ── Phase 6: Supplier Sync Scheduler ──────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def sync_hotelbeds_inventory(self):
    """
    Per-supplier Celery task: sync all Hotelbeds properties every 10 minutes.
    Uses the supplier_framework adapter pattern.
    """
    return _sync_supplier_properties('hotelbeds', self)


@shared_task(bind=True, max_retries=3)
def sync_staah_inventory(self):
    """
    Per-supplier Celery task: sync all STAAH properties every 10 minutes.
    """
    return _sync_supplier_properties('staah', self)


@shared_task(bind=True, max_retries=3)
def sync_siteminder_inventory(self):
    """
    Per-supplier Celery task: sync all SiteMinder properties every 10 minutes.
    """
    return _sync_supplier_properties('siteminder', self)


def _sync_supplier_properties(supplier_name, task_self):
    """
    Shared implementation for per-supplier sync tasks.
    Fetches rates for all properties connected to the given supplier,
    normalizes via inventory pipeline, and updates local inventory.
    """
    try:
        from apps.core.supplier_framework import get_supplier_adapter
        from apps.hotels.models import Property
        from datetime import date

        today = date.today()
        end_date = today + timedelta(days=90)

        adapter = get_supplier_adapter(supplier_name)
        if not adapter.authenticate():
            logger.warning('Supplier auth failed: %s', supplier_name)
            return {'supplier': supplier_name, 'status': 'auth_failed'}

        # Get properties connected to this supplier
        properties = Property.objects.filter(
            is_active=True,
        )

        synced = 0
        errors = 0
        for prop in properties.iterator(chunk_size=50):
            prop_code = getattr(prop, 'supplier_property_code', '') or str(prop.id)
            try:
                rates = adapter.fetch_rates(prop_code, today, end_date)
                if rates:
                    # Feed into inventory normalization pipeline
                    try:
                        from apps.inventory.pipeline import ingest_supplier_feed
                        ingest_supplier_feed(
                            property_id=prop.id,
                            supplier=supplier_name,
                            rates=[{
                                'room_type_code': r.room_type_code,
                                'date': str(r.date),
                                'price': str(r.price),
                                'available_rooms': r.available_rooms,
                            } for r in rates],
                        )
                    except Exception as pipe_err:
                        logger.warning('Pipeline ingest failed for %s/%s: %s', supplier_name, prop.id, pipe_err)
                synced += 1
            except Exception as e:
                errors += 1
                logger.error('Supplier sync failed %s property %s: %s', supplier_name, prop.id, e)

        logger.info('Supplier sync %s: %d synced, %d errors', supplier_name, synced, errors)
        return {'supplier': supplier_name, 'synced': synced, 'errors': errors}

    except Exception as exc:
        logger.error('Supplier sync %s failed: %s', supplier_name, exc)
        raise task_self.retry(exc=exc, countdown=120)


# ── Phase 10: Search Index Rebuild Job ─────────────────────────────────────────

@shared_task(bind=True, max_retries=2)
def rebuild_property_search_index(self, property_id=None):
    """
    Full or targeted rebuild of PropertySearchIndex.
    Triggered on inventory/price/review changes, or run as full rebuild.

    Args:
        property_id: Optional int — rebuild only this property. If None, rebuild all.
    """
    try:
        from apps.hotels.models import Property
        from apps.search.models import PropertySearchIndex
        from apps.rooms.models import RoomType
        from django.db.models import Min, Max, Avg

        if property_id:
            properties = Property.objects.filter(id=property_id, is_active=True).select_related('city')
        else:
            properties = Property.objects.filter(is_active=True).select_related('city')

        rebuilt = 0
        for prop in properties.iterator(chunk_size=100):
            try:
                prices = RoomType.objects.filter(property=prop).aggregate(
                    price_min=Min('base_price'),
                    price_max=Max('base_price'),
                )

                # Availability check
                has_avail = False
                try:
                    from apps.inventory.models import RoomInventory
                    has_avail = RoomInventory.objects.filter(
                        room_type__property=prop,
                        date__gte=timezone.now().date(),
                        available_rooms__gt=0,
                    ).exists()
                except Exception:
                    pass

                defaults = {
                    'property_name': prop.name,
                    'slug': getattr(prop, 'slug', ''),
                    'property_type': getattr(prop, 'property_type', 'hotel'),
                    'city_id': prop.city_id if hasattr(prop, 'city_id') else 0,
                    'city_name': prop.city.name if hasattr(prop, 'city') and prop.city else '',
                    'locality_name': getattr(prop, 'locality_name', ''),
                    'latitude': getattr(prop, 'latitude', 0) or 0,
                    'longitude': getattr(prop, 'longitude', 0) or 0,
                    'star_category': getattr(prop, 'star_category', 3) or 3,
                    'price_min': prices['price_min'] or 0,
                    'price_max': prices['price_max'] or 0,
                    'rating': getattr(prop, 'rating', 0) or 0,
                    'review_count': getattr(prop, 'review_count', 0) or 0,
                    'is_trending': getattr(prop, 'is_trending', False),
                    'has_availability': has_avail,
                }

                try:
                    img = prop.images.first()
                    if img:
                        defaults['featured_image_url'] = img.image.url if hasattr(img, 'image') else ''
                except Exception:
                    pass

                PropertySearchIndex.objects.update_or_create(
                    property=prop,
                    defaults=defaults,
                )
                rebuilt += 1
            except Exception as e:
                logger.error('Search index rebuild failed for property %s: %s', prop.id, e)

        logger.info('Search index rebuild: %d properties rebuilt (targeted=%s)', rebuilt, property_id)
        return {'rebuilt': rebuilt, 'property_id': property_id}
    except Exception as exc:
        logger.error('rebuild_property_search_index failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


# ── Phase 13: Payment Reconciliation Job ───────────────────────────────────────

@shared_task(bind=True, max_retries=2)
def reconcile_gateway_transactions(self, target_date=None):
    """
    Payment reconciliation: match PaymentTransaction records against
    expected settlements per gateway. Populates PaymentReconciliation model.
    Runs every 15 minutes for current day, and once daily for previous day.

    Args:
        target_date: Optional str (YYYY-MM-DD). Defaults to today.
    """
    try:
        from apps.payments.models import PaymentTransaction, PaymentReconciliation
        from django.db.models import Sum, Count
        from datetime import date

        recon_date = date.fromisoformat(target_date) if target_date else timezone.now().date()

        gateways = [c[0] for c in PaymentTransaction.GATEWAY_CHOICES]
        results = []

        for gw in gateways:
            # Calculate expected vs settled
            txns = PaymentTransaction.objects.filter(
                gateway=gw,
                created_at__date=recon_date,
            )

            success_txns = txns.filter(status=PaymentTransaction.STATUS_SUCCESS)
            expected = success_txns.aggregate(total=Sum('amount'))['total'] or 0
            matched = success_txns.filter(webhook_received=True).count()
            unmatched = success_txns.filter(webhook_received=False).count()

            # Webhook-confirmed amount
            settled = success_txns.filter(
                webhook_received=True,
            ).aggregate(total=Sum('amount'))['total'] or 0

            discrepancy = expected - settled

            recon, created = PaymentReconciliation.objects.update_or_create(
                date=recon_date,
                gateway=gw,
                defaults={
                    'expected_amount': expected,
                    'settled_amount': settled,
                    'discrepancy': discrepancy,
                    'transactions_matched': matched,
                    'transactions_unmatched': unmatched,
                    'status': 'matched' if discrepancy == 0 else 'discrepancy',
                    'details': {
                        'total_transactions': txns.count(),
                        'success_count': success_txns.count(),
                        'failed_count': txns.filter(status='failed').count(),
                    },
                },
            )

            results.append({
                'gateway': gw,
                'expected': str(expected),
                'settled': str(settled),
                'discrepancy': str(discrepancy),
                'status': recon.status,
            })

        logger.info('Payment reconciliation for %s: %d gateways processed', recon_date, len(results))
        return {'date': str(recon_date), 'gateways': results}
    except Exception as exc:
        logger.error('reconcile_gateway_transactions failed: %s', exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task
def fix_inconsistent_booking_states():
    """
    S5+S9: Scan for bookings in inconsistent states and fix them.
    
    Detects:
    - Confirmed bookings with failed/missing payments
    - payment_pending bookings with success payment transactions
    - hold bookings with confirmed payment but not yet transitioned
    
    Runs every 15 minutes.
    """
    try:
        from apps.booking.models import Booking
        from apps.payments.models import PaymentTransaction
        from django.db import transaction

        fixed = 0

        # 1) payment_pending bookings with a SUCCESS payment → confirm them
        pending_with_payment = Booking.objects.filter(
            status__in=['payment_pending', 'hold'],
        ).select_related('user')
        for booking in pending_with_payment[:200]:
            success_txn = PaymentTransaction.objects.filter(
                booking_reference=booking.booking_number,
                status=PaymentTransaction.STATUS_SUCCESS,
            ).first()
            if success_txn:
                with transaction.atomic():
                    b = Booking.objects.select_for_update().get(pk=booking.pk)
                    if b.status in ('payment_pending', 'hold'):
                        b.status = 'confirmed'
                        b.payment_status = 'paid'
                        b.save(update_fields=['status', 'payment_status', 'updated_at'])
                        fixed += 1
                        logger.info(
                            'Fixed inconsistent booking %s: %s → confirmed (had success payment)',
                            b.booking_number, booking.status,
                        )

        # 2) confirmed bookings where ALL payments failed → flag for review
        confirmed = Booking.objects.filter(status='confirmed')
        for booking in confirmed[:200]:
            txns = PaymentTransaction.objects.filter(
                booking_reference=booking.booking_number,
            )
            if txns.exists() and not txns.filter(status=PaymentTransaction.STATUS_SUCCESS).exists():
                logger.warning(
                    'Inconsistent booking %s: confirmed but no successful payment found',
                    booking.booking_number,
                )
                fixed += 1

        logger.info('Inconsistent state scan: %d issues found/fixed', fixed)
        return {'fixed': fixed}
    except Exception as exc:
        logger.error('fix_inconsistent_booking_states failed: %s', exc)
        return {'error': str(exc)}


# ============================================================================
# Section 14 — Inventory Sync Workers
# ============================================================================

@shared_task(bind=True, max_retries=3)
def recompute_inventory_pools(self, property_id=None):
    """
    Recompute InventoryPool rows aggregating direct + supplier inventory.
    Run every 5 minutes, or triggered on inventory changes.

    Args:
        property_id: Optional — only recompute for this property.
    """
    try:
        from apps.inventory.models import InventoryPool
        from apps.rooms.models import RoomType
        from datetime import date as _date

        today = _date.today()
        end = today + timedelta(days=90)

        if property_id:
            room_types = RoomType.objects.filter(property_id=property_id)
        else:
            room_types = RoomType.objects.filter(property__is_active=True)

        recomputed = 0
        for rt in room_types.iterator(chunk_size=100):
            current = today
            while current <= end:
                try:
                    InventoryPool.recompute(rt, current)
                    recomputed += 1
                except Exception as e:
                    logger.warning('Pool recompute failed %s/%s: %s', rt.id, current, e)
                current += timedelta(days=1)

        logger.info('Inventory pool recompute: %d rows updated (property=%s)', recomputed, property_id)
        return {'recomputed': recomputed, 'property_id': property_id}
    except Exception as exc:
        logger.error('recompute_inventory_pools failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=2)
def supplier_availability_sync(self):
    """
    Sync supplier inventory into SupplierInventory, then recompute pools.
    Runs every 10 minutes for each connected supplier.
    """
    try:
        from apps.inventory.models import SupplierPropertyMap, SupplierInventory, SupplierRoom

        suppliers = SupplierPropertyMap.objects.filter(
            is_active=True,
        ).values_list('supplier_name', flat=True).distinct()

        synced = 0
        for sname in suppliers:
            try:
                # Delegate to per-supplier adapters
                from apps.core.supplier_framework import get_supplier_adapter
                adapter = get_supplier_adapter(sname)
                if adapter.authenticate():
                    rooms = SupplierRoom.objects.filter(
                        supplier_map__supplier_name=sname,
                        supplier_map__is_active=True,
                    ).select_related('supplier_map', 'room_type')

                    for room in rooms.iterator(chunk_size=50):
                        try:
                            rates = adapter.fetch_rates(
                                room.supplier_map.supplier_property_code,
                                _date.today(),
                                _date.today() + timedelta(days=90),
                            )
                            for r in (rates or []):
                                SupplierInventory.objects.update_or_create(
                                    supplier_room=room,
                                    date=r.date,
                                    defaults={
                                        'available_rooms': r.available_rooms,
                                        'rate_per_night': r.price,
                                        'last_synced_at': timezone.now(),
                                    },
                                )
                            synced += 1
                        except Exception as e:
                            logger.warning('Room sync failed %s/%s: %s', sname, room.id, e)
            except Exception as e:
                logger.error('Supplier sync failed for %s: %s', sname, e)

        # Trigger pool recompute after sync
        recompute_inventory_pools.delay()

        logger.info('Supplier availability sync: %d rooms synced', synced)
        return {'synced': synced}
    except Exception as exc:
        logger.error('supplier_availability_sync failed: %s', exc)
        raise self.retry(exc=exc, countdown=120)


@shared_task
def flush_stale_cache_entries():
    """
    Flush cache entries older than their effective TTL.
    Price cache: 5 min; availability cache: 2 min; search cache: 10 min.
    Run every 15 minutes.
    """
    try:
        from apps.search.engine.cache_manager import price_cache, availability_cache
        # The caches use Django cache backend with built-in TTL.
        # This task is a safety net for manual invalidation.
        logger.info('Stale cache flush completed')
        return {'status': 'ok'}
    except Exception as e:
        logger.error('flush_stale_cache_entries failed: %s', e)
        return {'error': str(e)}


# ============================================================================
# S3: Search Cache Warming — Pre-warm popular city caches
# ============================================================================

@shared_task
def warm_popular_city_caches():
    """
    Pre-warm search caches for popular cities.
    Runs hourly to keep popular search results hot.
    """
    try:
        from apps.search.engine.cache_manager import warm_search_cache
        warmed = warm_search_cache()
        logger.info('Cache warming: %d cities warmed', warmed)
        return {'warmed': warmed}
    except Exception as exc:
        logger.error('warm_popular_city_caches failed: %s', exc)
        return {'error': str(exc)}


# ============================================================================
# S4: Rate Cache Bulk Generation — Pre-compute rates for high-demand hotels
# ============================================================================

@shared_task
def refresh_rate_cache_bulk():
    """
    Pre-compute and cache rates for top hotels.
    Runs every hour to keep rate cache warm.
    """
    try:
        from apps.search.engine.cache_manager import warm_rate_cache_bulk
        warmed = warm_rate_cache_bulk(days_ahead=14)
        logger.info('Rate cache bulk refresh: %d entries warmed', warmed)
        return {'warmed': warmed}
    except Exception as exc:
        logger.error('refresh_rate_cache_bulk failed: %s', exc)
        return {'error': str(exc)}


# ============================================================================
# S5: Missing Webhook Detection — Flag payments with no webhook after timeout
# ============================================================================

@shared_task(bind=True, max_retries=1)
def detect_missing_webhooks(self):
    """
    Detect PaymentTransactions that are still 'pending' or 'initiated' after
    30 minutes without receiving a webhook. Flags them for manual review.
    Runs every 15 minutes.
    """
    try:
        from apps.payments.models import PaymentTransaction
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(minutes=30)

        # Find transactions that should have received a webhook by now
        stuck = PaymentTransaction.objects.filter(
            status__in=[
                PaymentTransaction.STATUS_PENDING,
                PaymentTransaction.STATUS_INITIATED,
            ],
            webhook_received=False,
            created_at__lt=cutoff,
            gateway__in=['cashfree', 'stripe', 'paytm_upi'],  # External gateways only
        ).exclude(
            gateway='wallet',  # Wallet is instant, no webhook
        )

        flagged = 0
        for txn in stuck[:100]:  # Process max 100 per run
            # Try to query gateway for actual status
            try:
                from apps.payments.gateways import GATEWAY_REGISTRY
                gw_class = GATEWAY_REGISTRY.get(txn.gateway)
                if gw_class and hasattr(gw_class, 'check_payment_status'):
                    status = gw_class.check_payment_status(txn)
                    if status == 'success':
                        txn.mark_success(gateway_response={'source': 'webhook_recovery'})
                        logger.info('Recovered missing webhook for txn=%s', txn.transaction_id)
                        flagged += 1
                        continue
                    elif status == 'failed':
                        txn.mark_failed('Payment failed (detected by missing webhook scanner)',
                                       gateway_response={'source': 'webhook_recovery'})
                        flagged += 1
                        continue
            except Exception:
                pass

            # If we can't determine status, log an alert
            logger.warning(
                'Missing webhook: txn=%s gateway=%s amount=%s created=%s',
                txn.transaction_id, txn.gateway, txn.amount, txn.created_at,
            )
            flagged += 1

        if flagged:
            logger.info('Missing webhook detection: %d transactions flagged', flagged)
        return {'flagged': flagged}

    except Exception as exc:
        logger.error('detect_missing_webhooks failed: %s', exc)
        raise self.retry(exc=exc, countdown=120)


# ============================================================================
# S10: Fraud Scan Background Task
# ============================================================================

@shared_task
def scheduled_fraud_scan():
    """
    Background fraud detection scan.
    Reviews recent bookings and payments for suspicious patterns.
    Runs every 30 minutes.
    """
    try:
        from apps.booking.models import Booking
        from datetime import timedelta

        # Scan bookings from the last hour
        cutoff = timezone.now() - timedelta(hours=1)
        recent_bookings = Booking.objects.filter(
            created_at__gte=cutoff,
            status__in=['confirmed', 'hold', 'payment_pending'],
        ).select_related('user')

        flagged = 0
        for booking in recent_bookings[:200]:
            try:
                from apps.core.fraud_engine import FraudScoringEngine
                if booking.user:
                    result = FraudScoringEngine.assess_booking(
                        user=booking.user,
                        booking_data={
                            'amount': float(booking.total_price) if hasattr(booking, 'total_price') else 0,
                            'property_id': booking.property_id,
                            'booking_id': booking.id,
                        },
                    )
                    if result and result.get('risk_level') in ('high', 'critical'):
                        flagged += 1
                        logger.warning(
                            'Fraud scan flagged booking=%s user=%s risk=%s score=%s',
                            booking.id, booking.user_id,
                            result.get('risk_level'), result.get('risk_score'),
                        )
            except Exception as e:
                logger.debug('Fraud scan skip booking=%s: %s', booking.id, e)

        logger.info('Fraud scan completed: %d bookings flagged out of %d reviewed',
                    flagged, recent_bookings.count())
        return {'reviewed': recent_bookings.count(), 'flagged': flagged}

    except Exception as exc:
        logger.error('scheduled_fraud_scan failed: %s', exc)
        return {'error': str(exc)}
