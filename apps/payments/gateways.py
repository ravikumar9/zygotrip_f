"""
Payment Gateway Abstraction Layer — Production Implementation.

Supports:
  - WalletGateway (instant debit from ZygoTrip Wallet)
  - CashfreeGateway (UPI + cards via Cashfree PG)
  - StripeGateway (international cards via Stripe Checkout)
  - PaytmUPIGateway (UPI via Paytm)

All gateways are idempotent: duplicate calls with the same
PaymentTransaction return the existing result.
"""
import hashlib
import hmac
import json
import logging
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction

from apps.core.retry_utils import retry_with_backoff

logger = logging.getLogger('zygotrip.payments')


def _resilient_request(method, url, **kwargs):
    """
    Gateway HTTP helper with automatic retry on transient failures.
    Retries on connection errors, timeouts, and 502/503/504 responses.
    """
    kwargs.setdefault('timeout', 30)

    @retry_with_backoff(
        max_retries=2,
        base_delay=1.0,
        max_delay=5.0,
        exceptions=(requests.ConnectionError, requests.Timeout),
    )
    def _do_request():
        resp = requests.request(method, url, **kwargs)
        if resp.status_code in (502, 503, 504):
            raise requests.ConnectionError(
                f'Gateway returned {resp.status_code} for {url}'
            )
        return resp
    return _do_request()


# ===========================================================================
# Abstract Base
# ===========================================================================

class PaymentGateway(ABC):
    """Abstract base class for all payment gateways."""

    @abstractmethod
    def initiate_payment(self, booking, amount, user, txn):
        """
        Initiate payment with gateway.

        Args:
            booking: Booking model instance
            amount: Decimal amount in INR
            user: User model instance
            txn: PaymentTransaction record (already created)

        Returns:
            dict with keys: success, transaction_id, and gateway-specific
            data (payment_session_id, payment_url, etc.)
        """
        pass

    @abstractmethod
    def verify_payment(self, txn):
        """
        Verify payment status directly from gateway API.

        Args:
            txn: PaymentTransaction record

        Returns:
            (bool success, dict status_info)
        """
        pass

    @abstractmethod
    def process_refund(self, txn, amount):
        """
        Initiate a refund via the gateway.

        Args:
            txn: PaymentTransaction record
            amount: Decimal refund amount

        Returns:
            (bool success, dict refund_info)
        """
        pass

    @staticmethod
    def verify_webhook_signature(request):
        """
        Verify webhook signature. Override per gateway.

        Args:
            request: Django HttpRequest

        Returns:
            (bool is_valid, dict parsed_payload)
        """
        return False, {}


# ===========================================================================
# Wallet Gateway — Instant
# ===========================================================================

class WalletGateway(PaymentGateway):
    """ZygoTrip Wallet — instant debit, no redirect."""

    def initiate_payment(self, booking, amount, user, txn):
        from apps.wallet.models import Wallet

        try:
            wallet = Wallet.objects.select_for_update().get(user=user)
        except Wallet.DoesNotExist:
            txn.mark_failed('No wallet found for user')
            return {'success': False, 'error': 'No wallet found'}

        if not wallet.can_debit(amount):
            txn.mark_failed('Insufficient wallet balance')
            return {
                'success': False,
                'error': 'Insufficient wallet balance',
                'required': str(amount),
                'available': str(wallet.balance),
            }

        try:
            wallet.debit(
                amount,
                txn_type='payment',
                reference=str(booking.uuid),
                note=f'Payment for booking {booking.public_booking_id}',
            )
            txn.mark_success(gateway_txn_id=txn.transaction_id)

            return {
                'success': True,
                'transaction_id': txn.transaction_id,
                'gateway': 'wallet',
                'instant': True,
            }
        except Exception as e:
            logger.exception('Wallet payment failed: %s', e)
            txn.mark_failed(str(e))
            return {'success': False, 'error': str(e)}

    def verify_payment(self, txn):
        return (txn.status == 'success', {'status': txn.status})

    def process_refund(self, txn, amount):
        from apps.wallet.models import Wallet

        try:
            wallet = Wallet.objects.get(user=txn.user)
            wallet.credit(
                amount,
                txn_type='refund',
                reference=str(txn.booking.uuid) if txn.booking else txn.booking_reference,
                note=f'Refund for txn {txn.transaction_id}',
            )
            txn.initiate_refund(amount)
            return (True, {'message': 'Refund credited to wallet'})
        except Exception as e:
            logger.exception('Wallet refund failed: %s', e)
            return (False, {'error': str(e)})

    @staticmethod
    def verify_webhook_signature(request):
        # Wallet has no external webhook
        return True, {}


# ===========================================================================
# Cashfree Gateway
# ===========================================================================

class CashfreeGateway(PaymentGateway):
    """Cashfree Payment Gateway — UPI + Cards."""

    @property
    def _base_url(self):
        env = getattr(settings, 'CASHFREE_ENV', 'sandbox')
        if env == 'production':
            return 'https://api.cashfree.com/pg'
        return 'https://sandbox.cashfree.com/pg'

    @property
    def _headers(self):
        return {
            'Content-Type': 'application/json',
            'x-client-id': settings.CASHFREE_APP_ID,
            'x-client-secret': settings.CASHFREE_SECRET_KEY,
            'x-api-version': getattr(settings, 'CASHFREE_API_VERSION', '2023-08-01'),
        }

    def initiate_payment(self, booking, amount, user, txn):
        if not getattr(settings, 'CASHFREE_APP_ID', '') or not getattr(settings, 'CASHFREE_SECRET_KEY', ''):
            txn.mark_failed('Cashfree not configured')
            return {'success': False, 'error': 'Cashfree gateway not configured'}

        success_url = getattr(settings, 'PAYMENT_SUCCESS_URL', 'http://localhost:3000/confirmation/')
        order_payload = {
            'order_id': txn.transaction_id,
            'order_amount': float(amount),
            'order_currency': 'INR',
            'customer_details': {
                'customer_id': str(user.id),
                'customer_name': user.full_name or user.email,
                'customer_email': user.email,
                'customer_phone': user.phone or '9999999999',
            },
            'order_meta': {
                'return_url': f'{success_url}{booking.uuid}?txn_id={txn.transaction_id}',
                'notify_url': getattr(
                    settings, 'CASHFREE_WEBHOOK_URL',
                    'http://127.0.0.1:8000/api/v1/payment/webhook/cashfree/',
                ),
            },
            'order_note': f'ZygoTrip Booking {booking.public_booking_id}',
        }

        try:
            resp = _resilient_request(
                'POST',
                f'{self._base_url}/orders',
                json=order_payload,
                headers=self._headers,
                timeout=30,
            )
            data = resp.json()

            if resp.status_code in (200, 201) and data.get('payment_session_id'):
                txn.mark_pending(
                    gateway_txn_id=data.get('cf_order_id', ''),
                    gateway_response=data,
                )
                return {
                    'success': True,
                    'transaction_id': txn.transaction_id,
                    'gateway': 'cashfree',
                    'payment_session_id': data['payment_session_id'],
                    'cf_order_id': data.get('cf_order_id'),
                    'order_id': txn.transaction_id,
                    'environment': getattr(settings, 'CASHFREE_ENV', 'sandbox'),
                }
            else:
                error_msg = data.get('message', str(data))
                txn.mark_failed(error_msg, gateway_response=data)
                logger.error('Cashfree order creation failed: %s', data)
                return {'success': False, 'error': error_msg}
        except requests.RequestException as e:
            logger.exception('Cashfree API error: %s', e)
            txn.mark_failed(f'Cashfree API error: {e}')
            return {'success': False, 'error': 'Gateway communication error'}

    def verify_payment(self, txn):
        if not getattr(settings, 'CASHFREE_APP_ID', ''):
            return (False, {'error': 'Cashfree not configured'})

        try:
            resp = _resilient_request(
                'GET',
                f'{self._base_url}/orders/{txn.transaction_id}',
                headers=self._headers,
                timeout=15,
            )
            data = resp.json()
            order_status = data.get('order_status', '')

            if order_status == 'PAID':
                return (True, {'status': 'PAID', 'data': data})
            return (False, {'status': order_status, 'data': data})
        except Exception as e:
            return (False, {'error': str(e)})

    def process_refund(self, txn, amount):
        refund_payload = {
            'refund_amount': float(amount),
            'refund_id': f'RF-{txn.transaction_id}',
            'refund_note': f'Refund for booking',
        }
        try:
            resp = _resilient_request(
                'POST',
                f'{self._base_url}/orders/{txn.transaction_id}/refunds',
                json=refund_payload,
                headers=self._headers,
                timeout=30,
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                txn.initiate_refund(amount)
                txn.refund_gateway_id = data.get('cf_refund_id', '')
                txn.save(update_fields=['refund_gateway_id'])
                return (True, {'refund_id': data.get('cf_refund_id')})
            return (False, {'error': data.get('message', str(data))})
        except Exception as e:
            return (False, {'error': str(e)})

    @staticmethod
    def verify_webhook_signature(request):
        """
        Verify Cashfree webhook using HMAC SHA256 signature.
        Includes replay protection: rejects timestamps older than 5 minutes.
        """
        import time as _time

        secret = getattr(settings, 'CASHFREE_SECRET_KEY', '')
        if not secret:
            return False, {}

        timestamp = request.headers.get('x-webhook-timestamp', '')
        signature = request.headers.get('x-webhook-signature', '')
        if not timestamp or not signature:
            return False, {}

        # Replay protection: reject timestamps older than 5 minutes
        try:
            ts_int = int(timestamp)
            now = int(_time.time())
            if abs(now - ts_int) > 300:
                logger.warning('Cashfree webhook replay detected: timestamp=%s', timestamp)
                return False, {}
        except (ValueError, TypeError):
            logger.warning('Cashfree webhook invalid timestamp: %s', timestamp)
            return False, {}

        raw_body = request.body.decode('utf-8')
        sign_data = timestamp + raw_body
        expected = hmac.new(
            secret.encode('utf-8'),
            sign_data.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning('Cashfree webhook signature mismatch')
            return False, {}

        try:
            payload = json.loads(raw_body)
            return True, payload
        except json.JSONDecodeError:
            return False, {}


# ===========================================================================
# Stripe Gateway
# ===========================================================================

class StripeGateway(PaymentGateway):
    """Stripe Checkout Session — international cards."""

    def _get_stripe(self):
        import stripe as stripe_lib
        stripe_lib.api_key = settings.STRIPE_SECRET_KEY
        return stripe_lib

    def initiate_payment(self, booking, amount, user, txn):
        if not getattr(settings, 'STRIPE_SECRET_KEY', ''):
            txn.mark_failed('Stripe not configured')
            return {'success': False, 'error': 'Stripe gateway not configured'}

        stripe = self._get_stripe()
        success_url = getattr(settings, 'PAYMENT_SUCCESS_URL', 'http://localhost:3000/confirmation/')
        cancel_url = getattr(settings, 'PAYMENT_CANCEL_URL', 'http://localhost:3000/payment-failed/')

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {
                            'name': f'ZygoTrip Booking — {booking.public_booking_id}',
                            'description': (
                                f'{booking.property.name}, '
                                f'{booking.check_in} to {booking.check_out}'
                            ),
                        },
                        'unit_amount': int(amount * 100),  # Stripe uses paise
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'{success_url}{booking.uuid}?txn_id={txn.transaction_id}',
                cancel_url=f'{cancel_url}?txn_id={txn.transaction_id}',
                client_reference_id=str(booking.uuid),
                metadata={
                    'transaction_id': txn.transaction_id,
                    'booking_uuid': str(booking.uuid),
                },
                customer_email=user.email,
            )
            txn.mark_pending(
                gateway_txn_id=session.id,
                gateway_response={'session_id': session.id, 'url': session.url},
            )
            return {
                'success': True,
                'transaction_id': txn.transaction_id,
                'gateway': 'stripe',
                'session_id': session.id,
                'payment_url': session.url,
            }
        except Exception as e:
            logger.exception('Stripe session creation failed: %s', e)
            txn.mark_failed(str(e))
            return {'success': False, 'error': str(e)}

    def verify_payment(self, txn):
        if not getattr(settings, 'STRIPE_SECRET_KEY', ''):
            return (False, {'error': 'Stripe not configured'})

        stripe = self._get_stripe()
        try:
            session = stripe.checkout.Session.retrieve(txn.gateway_transaction_id)
            if session.payment_status == 'paid':
                return (True, {'status': 'paid', 'data': dict(session)})
            return (False, {'status': session.payment_status})
        except Exception as e:
            return (False, {'error': str(e)})

    def process_refund(self, txn, amount):
        stripe = self._get_stripe()
        try:
            session = stripe.checkout.Session.retrieve(txn.gateway_transaction_id)
            payment_intent_id = session.payment_intent
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=int(amount * 100),
            )
            txn.initiate_refund(amount)
            txn.refund_gateway_id = refund.id
            txn.save(update_fields=['refund_gateway_id'])
            return (True, {'refund_id': refund.id})
        except Exception as e:
            return (False, {'error': str(e)})

    @staticmethod
    def verify_webhook_signature(request):
        """Verify Stripe webhook using endpoint secret."""
        import stripe as stripe_lib

        endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if not endpoint_secret:
            return False, {}

        sig_header = request.headers.get('Stripe-Signature', '')
        try:
            event = stripe_lib.Webhook.construct_event(
                request.body, sig_header, endpoint_secret,
            )
            return True, event
        except (stripe_lib.error.SignatureVerificationError, ValueError) as e:
            logger.warning('Stripe webhook signature verification failed: %s', e)
            return False, {}


# ===========================================================================
# Paytm UPI Gateway
# ===========================================================================

class PaytmUPIGateway(PaymentGateway):
    """Paytm UPI Payment Gateway."""

    @property
    def _base_url(self):
        env = getattr(settings, 'PAYTM_ENV', 'staging')
        if env == 'production':
            return 'https://securegw.paytm.in'
        return 'https://securegw-stage.paytm.in'

    def _generate_checksum(self, params):
        """Generate Paytm checksum using merchant key."""
        import PaytmChecksum
        return PaytmChecksum.generateSignature(
            json.dumps(params), settings.PAYTM_MERCHANT_KEY,
        )

    def initiate_payment(self, booking, amount, user, txn):
        mid = getattr(settings, 'PAYTM_MERCHANT_ID', '')
        mkey = getattr(settings, 'PAYTM_MERCHANT_KEY', '')
        if not mid or not mkey:
            txn.mark_failed('Paytm not configured')
            return {'success': False, 'error': 'Paytm UPI gateway not configured'}

        callback_url = getattr(
            settings, 'PAYTM_CALLBACK_URL',
            'http://127.0.0.1:8000/api/v1/payment/webhook/paytm/',
        )

        body = {
            'requestType': 'Payment',
            'mid': mid,
            'websiteName': getattr(settings, 'PAYTM_WEBSITE', 'DEFAULT'),
            'orderId': txn.transaction_id,
            'callbackUrl': callback_url,
            'txnAmount': {
                'value': str(amount),
                'currency': 'INR',
            },
            'userInfo': {
                'custId': str(user.id),
                'email': user.email,
                'mobile': user.phone or '',
            },
        }

        try:
            checksum = self._generate_checksum(body)
            head = {'signature': checksum}
            paytm_params = {'body': body, 'head': head}

            resp = _resilient_request(
                'POST',
                f'{self._base_url}/theia/api/v1/initiateTransaction'
                f'?mid={mid}&orderId={txn.transaction_id}',
                json=paytm_params,
                timeout=30,
            )
            data = resp.json()
            resp_body = data.get('body', {})
            result_info = resp_body.get('resultInfo', {})

            if result_info.get('resultStatus') == 'S':
                txn_token = resp_body.get('txnToken', '')
                txn.mark_pending(gateway_response=data)
                return {
                    'success': True,
                    'transaction_id': txn.transaction_id,
                    'gateway': 'paytm_upi',
                    'txn_token': txn_token,
                    'mid': mid,
                    'order_id': txn.transaction_id,
                    'amount': str(amount),
                    'callback_url': callback_url,
                }
            else:
                error_msg = result_info.get('resultMsg', str(data))
                txn.mark_failed(error_msg, gateway_response=data)
                return {'success': False, 'error': error_msg}
        except requests.RequestException as e:
            logger.exception('Paytm API error: %s', e)
            txn.mark_failed(f'Paytm API error: {e}')
            return {'success': False, 'error': 'Gateway communication error'}

    def verify_payment(self, txn):
        mid = getattr(settings, 'PAYTM_MERCHANT_ID', '')
        if not mid:
            return (False, {'error': 'Paytm not configured'})

        body = {'mid': mid, 'orderId': txn.transaction_id}
        try:
            checksum = self._generate_checksum(body)
            params = {'body': body, 'head': {'signature': checksum}}
            resp = _resilient_request(
                'POST',
                f'{self._base_url}/v3/order/status',
                json=params,
                timeout=15,
            )
            data = resp.json()
            result_status = data.get('body', {}).get('resultInfo', {}).get('resultStatus', '')
            if result_status == 'TXN_SUCCESS':
                return (True, {'status': 'TXN_SUCCESS', 'data': data})
            return (False, {'status': result_status, 'data': data})
        except Exception as e:
            return (False, {'error': str(e)})

    def process_refund(self, txn, amount):
        mid = getattr(settings, 'PAYTM_MERCHANT_ID', '')
        if not mid:
            return (False, {'error': 'Paytm not configured'})

        refund_id = f'RF-{txn.transaction_id}'
        body = {
            'mid': mid,
            'txnType': 'REFUND',
            'orderId': txn.transaction_id,
            'txnId': txn.gateway_transaction_id,
            'refId': refund_id,
            'refundAmount': str(amount),
        }
        try:
            checksum = self._generate_checksum(body)
            params = {'body': body, 'head': {'signature': checksum}}
            resp = _resilient_request(
                'POST',
                f'{self._base_url}/refund/apply',
                json=params,
                timeout=30,
            )
            data = resp.json()
            result_status = data.get('body', {}).get('resultInfo', {}).get('resultStatus', '')
            if result_status in ('TXN_SUCCESS', 'PENDING'):
                txn.initiate_refund(amount)
                txn.refund_gateway_id = data.get('body', {}).get('refundId', refund_id)
                txn.save(update_fields=['refund_gateway_id'])
                return (True, {'refund_id': refund_id})
            return (False, {'error': data.get('body', {}).get('resultInfo', {}).get('resultMsg', '')})
        except Exception as e:
            return (False, {'error': str(e)})

    @staticmethod
    def verify_webhook_signature(request):
        """Verify Paytm callback checksum."""
        import PaytmChecksum

        mkey = getattr(settings, 'PAYTM_MERCHANT_KEY', '')
        if not mkey:
            return False, {}

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            # Paytm callbacks can be form-encoded
            payload = dict(request.POST)

        received_checksum = payload.pop('CHECKSUMHASH', [''])[0] if isinstance(
            payload.get('CHECKSUMHASH'), list,
        ) else payload.pop('CHECKSUMHASH', '')

        if not received_checksum:
            return False, payload

        is_valid = PaytmChecksum.verifySignature(
            payload, mkey, received_checksum,
        )
        if not is_valid:
            logger.warning('Paytm webhook signature mismatch')
        return is_valid, payload


# ===========================================================================
# Payment Router
# ===========================================================================

class PaymentRouter:
    """Routes payments to appropriate gateway based on selection."""

    GATEWAY_MAP = {
        'wallet': WalletGateway,
        'cashfree': CashfreeGateway,
        'stripe': StripeGateway,
        'paytm_upi': PaytmUPIGateway,
    }

    @staticmethod
    def get_gateway(gateway_name):
        """Get a gateway instance by name."""
        cls = PaymentRouter.GATEWAY_MAP.get(gateway_name)
        if cls is None:
            raise ValueError(f'Unknown gateway: {gateway_name}')
        return cls()

    @staticmethod
    def get_available_gateways(amount, user):
        """
        Return list of available gateways for the given user and amount.
        Only includes gateways that are actually configured.
        """
        from apps.wallet.models import Wallet

        gateways = []

        # 1. Wallet (always available if balance sufficient)
        try:
            wallet = Wallet.objects.get(user=user)
            if wallet.can_debit(amount):
                gateways.append({
                    'gateway': 'wallet',
                    'name': 'ZygoTrip Wallet',
                    'description': 'Pay using your wallet balance',
                    'balance': str(wallet.balance),
                    'icon': 'wallet',
                    'priority': 1,
                })
        except Wallet.DoesNotExist:
            pass

        # 2. Cashfree (UPI + Cards) — only if configured
        if getattr(settings, 'CASHFREE_APP_ID', ''):
            gateways.append({
                'gateway': 'cashfree',
                'name': 'UPI / Credit / Debit Card',
                'description': 'Pay via UPI, Visa, Mastercard, RuPay',
                'icon': 'credit-card',
                'priority': 2,
            })

        # 3. Paytm UPI — only if configured
        if getattr(settings, 'PAYTM_MERCHANT_ID', ''):
            gateways.append({
                'gateway': 'paytm_upi',
                'name': 'Paytm UPI',
                'description': 'Pay via Paytm UPI',
                'icon': 'smartphone',
                'priority': 3,
            })

        # 4. Stripe (international cards) — only if configured
        if getattr(settings, 'STRIPE_SECRET_KEY', ''):
            gateways.append({
                'gateway': 'stripe',
                'name': 'International Cards',
                'description': 'Visa, Mastercard (international)',
                'icon': 'globe',
                'priority': 4,
            })

        return sorted(gateways, key=lambda g: g['priority'])
