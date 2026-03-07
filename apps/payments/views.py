from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
import hashlib
import hmac
import json
import logging
import time

from apps.accounts.selectors import user_has_role
from apps.booking.selectors import get_booking_or_403
from .selectors import InvoiceDTO
from .services import handle_payment_webhook

logger = logging.getLogger('zygotrip.payments')

# Webhook security constants
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300  # 5 minutes
WEBHOOK_REPLAY_CACHE_TTL = 3600  # 1 hour


@login_required
def invoice_detail(request, invoice_uuid):
	if not user_has_role(request.user, "customer"):
		raise PermissionDenied
	booking = get_booking_or_403(request.user, invoice_uuid)
	invoice = InvoiceDTO(
		booking=booking,
		status="paid",
		issued_at=booking.updated_at or booking.created_at,
	)
	return render(request, "payments/invoice.html", {"invoice": invoice})


@csrf_exempt  # Payment gateways can't send CSRF tokens
@require_POST
def payment_webhook(request):
	"""
	Hardened payment gateway webhook handler.
	
	Security layers:
	  1. HMAC signature verification (X-Webhook-Signature header)
	  2. Timestamp freshness check (X-Webhook-Timestamp, ±5 min)
	  3. Replay protection (per payment_reference_id dedup via cache)
	  4. Device fingerprint collection (non-blocking)
	
	Expected headers:
	  X-Webhook-Signature: HMAC-SHA256 of request body
	  X-Webhook-Timestamp: Unix timestamp (seconds)
	
	Expected payload:
	{
		"payment_reference_id": "gateway-txn-123",
		"status": "success|failed|pending",
		"amount": 10000.00,
		"...": "other gateway data"
	}
	"""
	# --- Step 1: HMAC Signature Verification ---
	webhook_secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
	signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
	
	if webhook_secret:
		if not signature:
			logger.warning('Webhook rejected: missing signature header')
			return JsonResponse({'error': 'Missing signature'}, status=401)
		
		expected_sig = hmac.new(
			webhook_secret.encode(),
			request.body,
			hashlib.sha256,
		).hexdigest()
		
		if not hmac.compare_digest(signature, expected_sig):
			logger.warning('Webhook rejected: invalid HMAC signature')
			return JsonResponse({'error': 'Invalid signature'}, status=401)
	
	# --- Step 2: Timestamp Freshness ---
	timestamp_header = request.META.get('HTTP_X_WEBHOOK_TIMESTAMP', '')
	if timestamp_header:
		try:
			ts = int(timestamp_header)
			now = int(time.time())
			if abs(now - ts) > WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
				logger.warning(
					'Webhook rejected: stale timestamp (%d, now=%d, delta=%ds)',
					ts, now, abs(now - ts),
				)
				return JsonResponse({'error': 'Stale webhook timestamp'}, status=400)
		except (ValueError, TypeError):
			logger.warning('Webhook rejected: invalid timestamp format')
			return JsonResponse({'error': 'Invalid timestamp'}, status=400)
	
	# --- Parse JSON body ---
	try:
		payload = json.loads(request.body)
	except json.JSONDecodeError:
		return JsonResponse({'error': 'Invalid JSON'}, status=400)
	
	payment_ref = payload.get('payment_reference_id', '')
	
	# --- Step 3: Replay Protection (cache-based dedup) ---
	if payment_ref:
		from django.core.cache import cache
		dedup_key = f'webhook:dedup:{payment_ref}'
		if cache.get(dedup_key):
			logger.info('Webhook duplicate ignored: %s', payment_ref)
			return JsonResponse({
				'success': True,
				'message': 'Duplicate webhook — already processed',
				'idempotent': True,
			}, status=200)
		# Mark as seen (TTL 1 hour)
		cache.set(dedup_key, True, WEBHOOK_REPLAY_CACHE_TTL)
	
	# --- Step 4: Device fingerprint (non-blocking) ---
	try:
		from apps.core.device_fingerprint import FingerprintService
		FingerprintService.collect_from_request(request)
	except Exception:
		pass
	
	# --- Step 5: Delegate to service ---
	try:
		result = handle_payment_webhook(
			payment_reference_id=payment_ref,
			status=payload.get('status'),
			amount=payload.get('amount'),
			**payload
		)
		logger.info('Webhook processed: ref=%s result=%s', payment_ref, result.get('success', 'unknown'))
		return JsonResponse(result, status=200)
	
	except ValidationError as e:
		return JsonResponse({'error': str(e)}, status=400)
	except Exception as e:
		if settings.DEBUG:
			raise
		logger.exception('Webhook processing failed: ref=%s error=%s', payment_ref, e)
		return JsonResponse({'error': 'Webhook processing failed'}, status=500)

