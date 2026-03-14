#!/usr/bin/env python
"""
End-to-end booking flow test script.
Tests: Login, Context creation, Promo apply, Booking success, Cancel/refund,
       Insufficient wallet, Session expired.
"""
import os, sys, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zygotrip_project.settings')
django.setup()

from django.test import Client
from datetime import date, timedelta
from decimal import Decimal

# Clean up stale promo usage from previous test runs
from apps.promos.models import PromoUsage
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    test_user = User.objects.get(email='testuser@zygotrip.com')
    PromoUsage.objects.filter(user=test_user).delete()
    # Reset wallet balance to 10000
    from apps.wallet.models import Wallet
    wallet = Wallet.objects.get(user=test_user)
    wallet.balance = Decimal('10000.00')
    wallet.save(update_fields=['balance'])
    print('[setup] Cleaned up stale PromoUsage records and reset wallet to ₹10,000')
except User.DoesNotExist:
    pass

client = Client()
PASS = 0
FAIL = 0

def test(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  ✓ {name}')
    else:
        FAIL += 1
        print(f'  ✗ {name}: {detail}')

def api(method, url, data=None, token=None):
    headers = {}
    if token:
        headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    if method == 'POST':
        resp = client.post(url, data=json.dumps(data or {}), content_type='application/json', **headers)
    else:
        resp = client.get(url, **headers)
    return resp.status_code, json.loads(resp.content)

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 1: LOGIN ===')
status, data = api('POST', '/api/v1/auth/login/', {'email': 'testuser@zygotrip.com', 'password': 'Test@1234'})
test('Login returns 200', status == 200, f'got {status}')
test('Login success=true', data.get('success') == True, str(data))
access_token = data.get('data', {}).get('tokens', {}).get('access', '')
test('Got access token', len(access_token) > 20)

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 2: CREATE BOOKING CONTEXT ===')
ci = date(2026, 3, 15)
co = date(2026, 3, 16)
status, data = api('POST', '/api/v1/booking/context/', {
    'property_id': 118, 'room_type_id': 316,
    'checkin': str(ci), 'checkout': str(co),
    'adults': 2, 'rooms': 1, 'meal_plan': 'R+A',
}, token=access_token)
test('Context returns 201', status == 201, f'got {status}: {data}')
test('Context success=true', data.get('success') == True)
ctx = data.get('data', {})
ctx_uuid = ctx.get('uuid', '')
test('Context has UUID', len(str(ctx_uuid)) > 10)
base = Decimal(str(ctx.get('base_price', 0)))
final = Decimal(str(ctx.get('final_price', 0)))
test('Price > 0', final > 0, f'final={final}')
print(f'    base={base} meal={ctx.get("meal_amount")} tax={ctx.get("tax")} fee={ctx.get("service_fee")} final={final}')

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 3: APPLY PROMO TO CONTEXT ===')
status, data = api('POST', f'/api/v1/booking/context/{ctx_uuid}/apply-promo/', {
    'promo_code': 'ZYGO20',
}, token=access_token)
test('Apply promo returns 200', status == 200, f'got {status}: {data}')
test('Promo success=true', data.get('success') == True, str(data.get('error', '')))
ctx_after = data.get('data', {})
promo_discount = Decimal(str(ctx_after.get('promo_discount', 0)))
final_after = Decimal(str(ctx_after.get('final_price', 0)))
test('Promo discount > 0', promo_discount > 0, f'got {promo_discount}')
test('Final price decreased', final_after < final, f'before={final} after={final_after}')
test('Promo code stored', ctx_after.get('promo_code') == 'ZYGO20')
print(f'    discount={promo_discount} new_final={final_after}')

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 4: SUCCESSFUL BOOKING ===')
status, data = api('POST', '/api/v1/booking/', {
    'context_uuid': str(ctx_uuid),
    'payment_method': 'wallet',
    'guest_name': 'Test Traveler',
    'guest_email': 'testuser@zygotrip.com',
    'guest_phone': '+919000010000',
    'idempotency_key': f'test-{ctx_uuid}',
}, token=access_token)
test('Booking returns 201', status == 201, f'got {status}: {data}')
test('Booking success=true', data.get('success') == True, str(data.get('error', '')))
booking = data.get('data', {})
booking_uuid = booking.get('uuid', '')
booking_id = booking.get('public_booking_id', '')
test('Got booking UUID', len(str(booking_uuid)) > 10)
test('Got public booking ID', len(str(booking_id)) > 0)
total = booking.get('total_amount', 0)
total_dec = Decimal(str(total)) if total else Decimal('0')
test('Booking total matches promo price', abs(total_dec - final_after) < 1, f'booking={total_dec} expected≈{final_after}')
print(f'    booking_id={booking_id} uuid={booking_uuid} total={total} status={booking.get("status")}')

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 5: CANCEL BOOKING / REFUND ===')
if booking_uuid:
    status, data = api('POST', f'/api/v1/booking/{booking_uuid}/cancel/', {
        'guest_email': 'testuser@zygotrip.com',
    }, token=access_token)
    test('Cancel returns 200', status == 200, f'got {status}: {data}')
    test('Cancel success=true', data.get('success') == True, str(data.get('error', '')))
    cancel_data = data.get('data', {})
    test('Status is cancelled', cancel_data.get('status') == 'cancelled', f'got {cancel_data.get("status")}')
    refund = cancel_data.get('refund', {})
    if refund:
        print(f'    refund_amount={refund.get("amount")} tier={refund.get("tier")} note={refund.get("note")}')
    else:
        print(f'    No refund data (booking was in HOLD status)')
else:
    test('Cancel skipped (no booking)', False, 'no booking_uuid')

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 6: INSUFFICIENT WALLET BALANCE ===')
# Set wallet balance to 0
from apps.wallet.models import Wallet
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(email='testuser@zygotrip.com')
wallet = Wallet.objects.get(user=user)
original_balance = wallet.balance
wallet.balance = Decimal('0.00')
wallet.save(update_fields=['balance'])

# Create a new context
status, data = api('POST', '/api/v1/booking/context/', {
    'property_id': 118, 'room_type_id': 316,
    'checkin': str(date(2026, 3, 17)), 'checkout': str(date(2026, 3, 18)),
    'adults': 2, 'rooms': 1, 'meal_plan': 'R',
}, token=access_token)
ctx2_uuid = data.get('data', {}).get('uuid', '')

# Try to book with zero wallet
status, data = api('POST', '/api/v1/booking/', {
    'context_uuid': str(ctx2_uuid),
    'payment_method': 'wallet',
    'guest_name': 'Test Traveler',
    'guest_email': 'testuser@zygotrip.com',
    'guest_phone': '+919000010000',
}, token=access_token)
test('Insufficient wallet returns 402', status == 402, f'got {status}: {data}')
test('Error code is insufficient_balance', data.get('error', {}).get('code') == 'insufficient_balance', str(data))
print(f'    error_msg: {data.get("error", {}).get("message", "")}')

# Restore wallet
wallet.balance = original_balance
wallet.save(update_fields=['balance'])

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 7: SESSION/CONTEXT EXPIRED ===')
from apps.booking.models import BookingContext
from django.utils import timezone

# Create a context and expire it
status, data = api('POST', '/api/v1/booking/context/', {
    'property_id': 118, 'room_type_id': 316,
    'checkin': str(date(2026, 3, 20)), 'checkout': str(date(2026, 3, 21)),
    'adults': 2, 'rooms': 1, 'meal_plan': 'R',
}, token=access_token)
ctx3_uuid = data.get('data', {}).get('uuid', '')

# Force expire the context
ctx3 = BookingContext.objects.get(uuid=ctx3_uuid)
ctx3.expires_at = timezone.now() - timedelta(hours=1)
ctx3.save(update_fields=['expires_at'])

# Try to book with expired context
status, data = api('POST', '/api/v1/booking/', {
    'context_uuid': str(ctx3_uuid),
    'payment_method': 'wallet',
    'guest_name': 'Test Traveler',
    'guest_email': 'testuser@zygotrip.com',
    'guest_phone': '+919000010000',
}, token=access_token)
test('Expired context returns 410', status == 410, f'got {status}: {data}')
test('Error code is context_expired', data.get('error', {}).get('code') == 'context_expired', str(data))
print(f'    error_msg: {data.get("error", {}).get("message", "")}')

# Also test GET on expired context
status, data = api('GET', f'/api/v1/booking/context/{ctx3_uuid}/', token=access_token)
test('GET expired context returns 410', status == 410, f'got {status}')

# ═══════════════════════════════════════════════════════════════
print('\n=== TEST 8: REMOVE PROMO ===')
# Create fresh context with promo, then remove it
status, data = api('POST', '/api/v1/booking/context/', {
    'property_id': 118, 'room_type_id': 316,
    'checkin': str(date(2026, 3, 22)), 'checkout': str(date(2026, 3, 23)),
    'adults': 2, 'rooms': 1, 'meal_plan': 'R',
}, token=access_token)
ctx4_uuid = data.get('data', {}).get('uuid', '')
original_final = Decimal(str(data.get('data', {}).get('final_price', 0)))

# Apply promo
status, data = api('POST', f'/api/v1/booking/context/{ctx4_uuid}/apply-promo/', {'promo_code': 'WALLET500'}, token=access_token)
discounted = Decimal(str(data.get('data', {}).get('final_price', 0)))
test('WALLET500 discount applied', discounted < original_final, f'orig={original_final} disc={discounted}')

# Remove promo
status, data = api('POST', f'/api/v1/booking/context/{ctx4_uuid}/apply-promo/', {'promo_code': ''}, token=access_token)
restored = Decimal(str(data.get('data', {}).get('final_price', 0)))
test('Remove promo restores price', restored == original_final, f'restored={restored} orig={original_final}')
test('Promo code cleared', data.get('data', {}).get('promo_code') == '')

# ═══════════════════════════════════════════════════════════════
print(f'\n{"="*50}')
print(f'RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests')
if FAIL == 0:
    print('ALL TESTS PASSED ✓')
else:
    print(f'{FAIL} TESTS FAILED ✗')
