"""
E2E Test Script: Payment Gateway Flow (Wallet + Card/Dev-Simulate + Cancel + Refund)
Tests every payment path through the Django REST API.
"""
import os
import sys
import json
import time
import requests
from decimal import Decimal
from datetime import date, timedelta

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


def assert_in(item, collection, label):
    if item in collection:
        log_pass(f'{label}: {item} found')
    else:
        log_fail(f'{label}: {item} not in {collection}')


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


def login():
    r = requests.post(f'{BASE}/api/v1/auth/login/', json={
        'email': 'testuser@zygotrip.com',
        'password': 'Test@1234',
    })
    assert_eq(r.status_code, 200, 'Login status')
    login_data = unwrap(r.json())
    access = login_data.get('tokens', {}).get('access')
    assert_true(bool(access), 'JWT token obtained')
    return {'Authorization': f'Bearer {access}', 'Content-Type': 'application/json'}


def get_hotel_and_room():
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

    r = requests.get(f'{BASE}/api/v1/properties/{slug}/')
    detail = unwrap(r.json())
    rooms = detail.get('room_types', detail.get('rooms', []))
    room_type_id = rooms[0]['id']

    return property_id, slug, room_type_id, hotel.get('name', '?'), rooms[0].get('name', '?')


def create_booking_context(property_id, room_type_id, headers=None):
    checkin = (date.today() + timedelta(days=7)).isoformat()
    checkout = (date.today() + timedelta(days=8)).isoformat()
    r = requests.post(f'{BASE}/api/v1/booking/context/', json={
        'property_id': property_id,
        'room_type_id': room_type_id,
        'checkin': checkin,
        'checkout': checkout,
        'rooms': 1,
        'adults': 2,
        'meal_plan': 'breakfast',
    }, headers=headers or {})
    ctx = unwrap(safe_json(r))
    return ctx.get('uuid') or ctx.get('context_uuid'), ctx.get('final_price') or ctx.get('total_amount')


print('\n' + '=' * 70)
print('  E2E PAYMENT GATEWAY TEST')
print('  Tests: wallet, dev-simulate card, available gateways, cancel+refund')
print('=' * 70)

# ================================================================
# SETUP: Login + get hotel/room
# ================================================================
print('\n-- Setup: Login + get hotel/room --')
headers = login()
property_id, slug, room_type_id, hotel_name, room_name = get_hotel_and_room()
print(f'  Hotel: {hotel_name} | Room: {room_name}')

initial_balance = get_wallet_balance(headers)
print(f'  Initial wallet balance: Rs{initial_balance}')

# ================================================================
# TEST 1: WALLET BOOKING (HOLD -> CONFIRMED via booking endpoint)
# ================================================================
print('\n' + '-' * 70)
print('  TEST 1: Wallet Booking via booking endpoint')
print('-' * 70)

print('\n-- Create booking context --')
ctx_uuid, final_price = create_booking_context(property_id, room_type_id, headers)
print(f'  Context: {ctx_uuid}, Price: Rs{final_price}')
assert_true(bool(ctx_uuid), 'Context UUID obtained')

print('\n-- Confirm booking (wallet) --')
r = requests.post(f'{BASE}/api/v1/booking/', json={
    'context_uuid': ctx_uuid,
    'payment_method': 'wallet',
    'guest_name': 'Mr Test User',
    'guest_email': 'testuser@zygotrip.com',
    'guest_phone': '9876543210',
    'use_wallet': True,
    'idempotency_key': f'wallet-{int(time.time())}',
}, headers=headers)
assert_eq(r.status_code, 201, 'Booking HTTP 201')

booking = unwrap(safe_json(r))
wallet_booking_uuid = booking.get('uuid')
assert_eq(booking.get('status'), 'confirmed', 'Wallet booking = confirmed')
wallet_total = Decimal(str(booking.get('total_amount', 0)))
print(f'  Wallet booking UUID: {wallet_booking_uuid}, status: {booking.get("status")}, total: Rs{wallet_total}')

# Verify wallet deducted
balance_after_wallet = get_wallet_balance(headers)
deducted = initial_balance - balance_after_wallet
print(f'  Wallet deducted: Rs{deducted}')
assert_eq(deducted, wallet_total, f'Wallet deducted correctly (Rs{wallet_total})')

# ================================================================
# TEST 2: GATEWAY BOOKING (HOLD -> PAYMENT PAGE -> CONFIRMED)
# ================================================================
print('\n' + '-' * 70)
print('  TEST 2: Gateway Booking (Card/UPI via payment API)')
print('-' * 70)

print('\n-- Create booking context for gateway --')
ctx_uuid2, final_price2 = create_booking_context(property_id, room_type_id, headers)
print(f'  Context: {ctx_uuid2}, Price: Rs{final_price2}')
assert_true(bool(ctx_uuid2), 'Context UUID obtained')

print('\n-- Confirm booking (gateway method -> stays HOLD) --')
r = requests.post(f'{BASE}/api/v1/booking/', json={
    'context_uuid': ctx_uuid2,
    'payment_method': 'gateway',
    'guest_name': 'Mr Test User',
    'guest_email': 'testuser@zygotrip.com',
    'guest_phone': '9876543210',
    'idempotency_key': f'gateway-{int(time.time())}',
}, headers=headers)
assert_eq(r.status_code, 201, 'Gateway booking HTTP 201')

gw_booking = unwrap(safe_json(r))
gw_booking_uuid = gw_booking.get('uuid')
gw_status = gw_booking.get('status')
gw_total = Decimal(str(gw_booking.get('total_amount', 0)))
print(f'  Gateway booking UUID: {gw_booking_uuid}, status: {gw_status}, total: Rs{gw_total}')
assert_eq(gw_status, 'hold', 'Gateway booking starts in HOLD')

# ================================================================
# TEST 3: AVAILABLE GATEWAYS API
# ================================================================
print('\n' + '-' * 70)
print('  TEST 3: Available Gateways API')
print('-' * 70)

print('\n-- GET /api/v1/payment/gateways/<booking_uuid>/ --')
r = requests.get(f'{BASE}/api/v1/payment/gateways/{gw_booking_uuid}/', headers=headers)
assert_eq(r.status_code, 200, 'Gateways endpoint 200')
gw_data = unwrap(safe_json(r))
gateways = gw_data.get('gateways', [])
gateway_names = [g['name'] for g in gateways]
print(f'  Available gateways: {gateway_names}')
print(f'  Gateway data: {json.dumps(gateways, indent=2)}')

assert_true(len(gateways) > 0, f'At least one gateway available ({len(gateways)})')

# In dev mode, dev_simulate should be present
assert_in('dev_simulate', gateway_names, 'dev_simulate gateway available in dev mode')

# Each gateway should have correct shape
for gw in gateways:
    assert_true('name' in gw, f'Gateway {gw.get("name","?")} has "name" key')
    assert_true('display_name' in gw, f'Gateway {gw.get("name","?")} has "display_name" key')
    assert_true('available' in gw, f'Gateway {gw.get("name","?")} has "available" key')
    assert_true(gw['available'] is True, f'Gateway {gw.get("name","?")} is available')

# ================================================================
# TEST 4: INITIATE PAYMENT VIA dev_simulate GATEWAY
# ================================================================
print('\n' + '-' * 70)
print('  TEST 4: Initiate Payment via dev_simulate gateway')
print('-' * 70)

balance_before_payment = get_wallet_balance(headers)

print('\n-- POST /api/v1/payment/initiate/ (dev_simulate) --')
r = requests.post(f'{BASE}/api/v1/payment/initiate/', json={
    'booking_uuid': gw_booking_uuid,
    'gateway': 'dev_simulate',
    'idempotency_key': f'pay-dev-{int(time.time())}',
}, headers=headers)
print(f'  Payment initiate status: {r.status_code}')
pay_data = unwrap(safe_json(r))
print(f'  Payment response: {json.dumps(pay_data, indent=2)}')

assert_eq(r.status_code, 201, 'Payment initiate HTTP 201')
assert_true(pay_data.get('instant', False), 'dev_simulate is instant')
assert_eq(pay_data.get('gateway'), 'dev_simulate', 'Gateway = dev_simulate')
txn_id = pay_data.get('transaction_id')
assert_true(bool(txn_id), f'Transaction ID obtained: {txn_id}')

# Verify booking is now CONFIRMED
print('\n-- Verify booking status after payment --')
if gw_booking_uuid:
    r = requests.get(f'{BASE}/api/v1/booking/{gw_booking_uuid}/', headers=headers)
    assert_eq(r.status_code, 200, 'Booking detail 200')
    detail = unwrap(safe_json(r))
    print(f'  Booking status: {detail.get("status")}')
    assert_eq(detail.get('status'), 'confirmed', 'Booking confirmed after dev_simulate payment')
else:
    log_fail('No gateway booking UUID to verify')

# Wallet should NOT be deducted for dev_simulate
balance_after_payment = get_wallet_balance(headers)
wallet_diff = balance_before_payment - balance_after_payment
print(f'  Wallet diff after dev_simulate: Rs{wallet_diff} (should be 0)')
assert_eq(wallet_diff, Decimal('0'), 'Wallet NOT deducted for dev_simulate')

# ================================================================
# TEST 5: PAYMENT STATUS API
# ================================================================
print('\n' + '-' * 70)
print('  TEST 5: Payment Status API')
print('-' * 70)

if txn_id:
    print(f'\n-- GET /api/v1/payment/status/{txn_id}/ --')
    r = requests.get(f'{BASE}/api/v1/payment/status/{txn_id}/', headers=headers)
    assert_eq(r.status_code, 200, 'Payment status 200')
    status_data = unwrap(safe_json(r))
    print(f'  Status: {status_data.get("status")}')
    print(f'  Booking status: {status_data.get("booking_status")}')
    assert_eq(status_data.get('status'), 'success', 'Transaction status = success')
    assert_eq(status_data.get('booking_status'), 'confirmed', 'Booking status = confirmed')
else:
    log_fail('No transaction ID to check status')

# ================================================================
# TEST 6: CANCEL GATEWAY BOOKING + REFUND
# ================================================================
print('\n' + '-' * 70)
print('  TEST 6: Cancel gateway-paid booking')
print('-' * 70)

balance_before_cancel = get_wallet_balance(headers)

print('\n-- Cancel the dev_simulate booking --')
r = requests.post(f'{BASE}/api/v1/booking/{gw_booking_uuid}/cancel/', json={
    'reason': 'E2E test — cancel gateway booking',
}, headers=headers)
print(f'  Cancel status: {r.status_code}')
cancel_data = unwrap(safe_json(r))
assert_eq(cancel_data.get('status'), 'cancelled', 'Booking cancelled')
refund_info = cancel_data.get('refund', {})
refund_amount = Decimal(str(refund_info.get('amount', 0)))
print(f'  Refund amount: Rs{refund_amount}')
print(f'  Wallet credited: {refund_info.get("wallet_credited")}')
assert_true(refund_amount > 0, f'Refund amount > 0 (Rs{refund_amount})')

# ================================================================
# TEST 7: CANCEL WALLET BOOKING + VERIFY WALLET REFUND
# ================================================================
print('\n' + '-' * 70)
print('  TEST 7: Cancel wallet booking + verify wallet refund')
print('-' * 70)

balance_before_wallet_cancel = get_wallet_balance(headers)

print('\n-- Cancel wallet booking --')
r = requests.post(f'{BASE}/api/v1/booking/{wallet_booking_uuid}/cancel/', json={
    'reason': 'E2E test — cancel wallet booking',
}, headers=headers)
print(f'  Cancel status: {r.status_code}')
cancel_data2 = unwrap(safe_json(r))
assert_eq(cancel_data2.get('status'), 'cancelled', 'Wallet booking cancelled')
refund_info2 = cancel_data2.get('refund', {})
refund_amount2 = Decimal(str(refund_info2.get('amount', 0)))
print(f'  Refund amount: Rs{refund_amount2}')
print(f'  Wallet credited: {refund_info2.get("wallet_credited")}')
assert_true(refund_amount2 > 0, f'Refund amount > 0 (Rs{refund_amount2})')
assert_true(refund_info2.get('wallet_credited', False), 'Wallet credited flag = True')

balance_after_wallet_cancel = get_wallet_balance(headers)
wallet_refunded = balance_after_wallet_cancel - balance_before_wallet_cancel
print(f'  Wallet refunded: Rs{wallet_refunded}')
assert_eq(wallet_refunded, refund_amount2, f'Wallet correctly refunded Rs{refund_amount2}')

# ================================================================
# TEST 8: GUEST BOOKING (no auth, stays HOLD)
# ================================================================
print('\n' + '-' * 70)
print('  TEST 8: Guest Booking (no auth, stays HOLD)')
print('-' * 70)

print('\n-- Create guest context --')
r = requests.post(f'{BASE}/api/v1/booking/context/', json={
    'property_id': property_id,
    'room_type_id': room_type_id,
    'checkin': (date.today() + timedelta(days=7)).isoformat(),
    'checkout': (date.today() + timedelta(days=8)).isoformat(),
    'rooms': 1,
    'adults': 2,
})
print(f'  Guest context status: {r.status_code}')
if r.status_code in (200, 201):
    guest_ctx = unwrap(safe_json(r))
    guest_uuid = guest_ctx.get('uuid') or guest_ctx.get('context_uuid')

    print('\n-- Create guest booking --')
    r = requests.post(f'{BASE}/api/v1/booking/', json={
        'context_uuid': guest_uuid,
        'payment_method': 'gateway',
        'guest_name': 'Guest User',
        'guest_email': 'guest@example.com',
        'guest_phone': '9876543211',
        'idempotency_key': f'guest-{int(time.time())}',
    })
    guest_bk = unwrap(safe_json(r))
    print(f'  Guest booking status: {guest_bk.get("status")}')
    assert_eq(guest_bk.get('status'), 'hold', 'Guest booking stays HOLD')
else:
    log_fail(f'Guest context failed: {r.status_code}')

# ================================================================
# SUMMARY
# ================================================================
print('\n' + '=' * 70)
print(f'  RESULTS: {PASS_COUNT} passed, {FAIL_COUNT} failed')
print('=' * 70)

if FAIL_COUNT > 0:
    print(f'\n  {FAIL_COUNT} TEST(S) FAILED!')
    sys.exit(1)
else:
    print('\n  ALL E2E TESTS PASSED!')
    sys.exit(0)
