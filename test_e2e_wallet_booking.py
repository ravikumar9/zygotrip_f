"""
E2E Test Script: Wallet Booking -> Cancel -> Refund
Tests the complete booking lifecycle via the Django REST API.
"""
import os
import sys
import json
import time
import requests
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zygotrip_project.settings')
import django
django.setup()

BASE = 'http://127.0.0.1:8000'
PASS_COUNT = 0
FAIL_COUNT = 0


def log_pass(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f'  PASS: {msg}')


def log_fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f'  FAIL: {msg}')


def assert_eq(actual, expected, label):
    if actual == expected:
        log_pass(f'{label}: {actual}')
    else:
        log_fail(f'{label}: expected={expected}, got={actual}')


def assert_true(val, label):
    if val:
        log_pass(label)
    else:
        log_fail(label)


def get_wallet_balance(headers):
    r = requests.get(f'{BASE}/api/v1/wallet/', headers=headers)
    d = r.json()
    if 'data' in d:
        return Decimal(str(d['data']['balance']))
    return Decimal(str(d.get('balance', 0)))


def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {}


def unwrap(resp):
    if isinstance(resp, dict) and 'data' in resp:
        return resp['data']
    return resp


print('\n' + '=' * 70)
print('  E2E WALLET BOOKING / CANCEL / REFUND TEST')
print('=' * 70)

# ================================================================
# STEP 1: Login
# ================================================================
print('\n-- Step 1: Login --')
r = requests.post(f'{BASE}/api/v1/auth/login/', json={
    'email': 'testuser@zygotrip.com',
    'password': 'Test@1234',
})
assert_eq(r.status_code, 200, 'Login status')
login_data = unwrap(r.json())
access = login_data.get('tokens', {}).get('access')
assert_true(bool(access), 'JWT token obtained')
headers = {'Authorization': f'Bearer {access}', 'Content-Type': 'application/json'}

# ================================================================
# STEP 2: Check initial wallet balance
# ================================================================
print('\n-- Step 2: Check initial wallet balance --')
initial_balance = get_wallet_balance(headers)
print(f'  Initial wallet balance: Rs{initial_balance}')
assert_true(initial_balance > 0, f'Wallet has funds (Rs{initial_balance})')

# ================================================================
# STEP 3: Get hotel + room type
# ================================================================
print('\n-- Step 3: Get hotel + room type --')
r = requests.get(f'{BASE}/api/v1/properties/')
props = r.json()
if isinstance(props, dict) and 'results' in props:
    hotel = props['results'][0]
elif isinstance(props, dict) and 'data' in props:
    inner = props['data']
    hotel = inner['results'][0] if isinstance(inner, dict) and 'results' in inner else inner[0]
else:
    hotel = props[0]

property_id = hotel['id']
slug = hotel.get('slug', str(property_id))
hotel_name = hotel.get('name', '?')
print(f'  Hotel: {hotel_name} (id={property_id})')

# Get room types
r = requests.get(f'{BASE}/api/v1/properties/{slug}/')
detail = unwrap(r.json())
rooms = detail.get('room_types', detail.get('rooms', []))
room_type_id = rooms[0]['id']
room_name = rooms[0].get('name', '?')
print(f'  Room type: {room_name} (id={room_type_id})')

# ================================================================
# TEST 1: WALLET BOOKING (HOLD -> CONFIRMED)
# ================================================================
print('\n' + '-' * 70)
print('  TEST 1: Wallet Booking (HOLD -> CONFIRMED)')
print('-' * 70)

from datetime import date, timedelta
checkin = (date.today() + timedelta(days=7)).isoformat()
checkout = (date.today() + timedelta(days=8)).isoformat()

# Create booking context
print('\n-- Step 4: Create booking context --')
r = requests.post(f'{BASE}/api/v1/booking/context/', json={
    'property_id': property_id,
    'room_type_id': room_type_id,
    'checkin': checkin,
    'checkout': checkout,
    'rooms': 1,
    'adults': 2,
    'meal_plan': 'breakfast',
}, headers=headers)
print(f'  Context status: {r.status_code}')
ctx = unwrap(safe_json(r))
context_uuid = ctx.get('uuid') or ctx.get('context_uuid')
final_price = ctx.get('final_price') or ctx.get('total_amount')
print(f'  Context UUID: {context_uuid}')
print(f'  Final price: Rs{final_price}')
assert_true(bool(context_uuid), 'Context UUID obtained')
assert_true(float(final_price or 0) > 0, f'Price is valid (Rs{final_price})')

# Confirm booking
print('\n-- Step 5: Confirm booking (wallet payment) --')
r = requests.post(f'{BASE}/api/v1/booking/', json={
    'context_uuid': context_uuid,
    'payment_method': 'wallet',
    'guest_name': 'Mr Test User',
    'guest_email': 'testuser@zygotrip.com',
    'guest_phone': '9876543210',
    'use_wallet': True,
    'idempotency_key': f'test-{int(time.time())}',
}, headers=headers)
print(f'  Booking status code: {r.status_code}')
if r.status_code not in (200, 201):
    print(f'  ERROR response: {r.text[:300]}')

booking = unwrap(safe_json(r))
booking_uuid = booking.get('uuid')
booking_id = booking.get('public_booking_id')
booking_status = booking.get('status')
total_amount = Decimal(str(booking.get('total_amount', 0)))

print(f'  Booking UUID: {booking_uuid}')
print(f'  Booking ID: {booking_id}')
print(f'  Status: {booking_status}')
print(f'  Total: Rs{total_amount}')

assert_eq(r.status_code, 201, 'Booking HTTP 201')
assert_eq(booking_status, 'confirmed', 'Booking status = confirmed')
assert_true(bool(booking_uuid), 'Booking UUID present')

# Check wallet deduction
print('\n-- Step 6: Verify wallet deduction --')
new_balance = get_wallet_balance(headers)
deducted = initial_balance - new_balance
print(f'  Old balance: Rs{initial_balance}')
print(f'  New balance: Rs{new_balance}')
print(f'  Deducted: Rs{deducted}')
assert_eq(deducted, total_amount, f'Wallet deducted Rs{total_amount}')

# Verify booking detail
print('\n-- Step 7: Verify booking detail --')
if booking_uuid:
    r = requests.get(f'{BASE}/api/v1/booking/{booking_uuid}/', headers=headers)
    if r.status_code == 200:
        detail = unwrap(r.json())
        assert_eq(detail.get('status'), 'confirmed', 'Detail status = confirmed')
    else:
        log_fail(f'Booking detail fetch HTTP {r.status_code}')
else:
    log_fail('No booking UUID to verify detail')

# ================================================================
# TEST 2: CANCEL + WALLET REFUND
# ================================================================
print('\n' + '-' * 70)
print('  TEST 2: Cancel Booking + Wallet Refund')
print('-' * 70)

if not booking_uuid:
    log_fail('Skipping cancel test - no booking UUID')
else:
    balance_before_cancel = new_balance

    print('\n-- Step 8: Cancel booking --')
    r = requests.post(f'{BASE}/api/v1/booking/{booking_uuid}/cancel/', json={
        'reason': 'E2E testing - cancel and refund',
    }, headers=headers)
    print(f'  Cancel status code: {r.status_code}')
    cancel_data = unwrap(safe_json(r))
    print(f'  Cancel response: {json.dumps(cancel_data, indent=2)}')

    assert_eq(cancel_data.get('status'), 'cancelled', 'Booking status = cancelled')
    refund_info = cancel_data.get('refund', {})
    refund_amount = Decimal(str(refund_info.get('amount', 0)))
    print(f'  Refund amount: Rs{refund_amount}')
    print(f'  Refund tier: {refund_info.get("tier", "N/A")}')
    print(f'  Wallet credited: {refund_info.get("wallet_credited", "N/A")}')

    assert_true(refund_amount > 0, f'Refund amount > 0 (Rs{refund_amount})')
    assert_true(refund_info.get('wallet_credited', False), 'Wallet credited flag = True')

    # Verify wallet refund
    print('\n-- Step 9: Verify wallet refund --')
    after_cancel_balance = get_wallet_balance(headers)
    refunded = after_cancel_balance - balance_before_cancel
    print(f'  Balance before cancel: Rs{balance_before_cancel}')
    print(f'  Balance after cancel: Rs{after_cancel_balance}')
    print(f'  Refunded: Rs{refunded}')
    assert_eq(refunded, refund_amount, f'Wallet refunded Rs{refund_amount}')

    # Verify booking after cancel
    print('\n-- Step 10: Verify booking detail after cancel --')
    r = requests.get(f'{BASE}/api/v1/booking/{booking_uuid}/', headers=headers)
    if r.status_code == 200:
        detail = unwrap(r.json())
        assert_eq(detail.get('status'), 'cancelled', 'Booking detail status = cancelled')
    else:
        log_fail(f'Booking detail fetch HTTP {r.status_code}')

# ================================================================
# TEST 3: GUEST BOOKING (no auth, stays HOLD)
# ================================================================
print('\n' + '-' * 70)
print('  TEST 3: Guest Booking (no auth, stays HOLD)')
print('-' * 70)

print('\n-- Step 11: Create guest booking context --')
r = requests.post(f'{BASE}/api/v1/booking/context/', json={
    'property_id': property_id,
    'room_type_id': room_type_id,
    'checkin': checkin,
    'checkout': checkout,
    'rooms': 1,
    'adults': 2,
})
print(f'  Guest context status: {r.status_code}')
if r.status_code in (200, 201):
    guest_ctx = unwrap(safe_json(r))
    guest_context_uuid = guest_ctx.get('uuid') or guest_ctx.get('context_uuid')
    print(f'  Guest context UUID: {guest_context_uuid}')

    print('\n-- Step 12: Confirm guest booking --')
    r = requests.post(f'{BASE}/api/v1/booking/', json={
        'context_uuid': guest_context_uuid,
        'payment_method': 'gateway',
        'guest_name': 'Guest User',
        'guest_email': 'guest@example.com',
        'guest_phone': '9876543211',
        'idempotency_key': f'guest-{int(time.time())}',
    })
    print(f'  Guest booking status code: {r.status_code}')
    guest_booking = unwrap(safe_json(r))
    guest_status = guest_booking.get('status')
    print(f'  Guest booking status: {guest_status}')
    assert_eq(guest_status, 'hold', 'Guest booking stays in HOLD')
else:
    print(f'  Guest context response: {r.status_code} - {r.text[:200]}')
    print('  (Creating guest context may require different handling)')

# ================================================================
# SUMMARY
# ================================================================
print('\n' + '=' * 70)
print(f'  RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed')
print('=' * 70)

if FAIL_COUNT > 0:
    sys.exit(1)
else:
    print('\n  ALL E2E TESTS PASSED!')
    sys.exit(0)
