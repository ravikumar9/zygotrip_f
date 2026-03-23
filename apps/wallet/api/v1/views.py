"""
Wallet REST API v1.

Endpoints:
  GET  /api/v1/wallet/                       — Customer wallet balance
  GET  /api/v1/wallet/transactions/          — Transaction history (paginated)
  POST /api/v1/wallet/topup/                 — Add money to wallet
  GET  /api/v1/wallet/owner/                 — Owner wallet balance (property_owner role)
  GET  /api/v1/wallet/owner/transactions/    — Owner transaction history

All endpoints require authentication (IsAuthenticated).
"""
import logging
from decimal import Decimal

from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.wallet.services import (
    get_or_create_wallet,
    get_or_create_owner_wallet,
    get_transaction_history,
)
from apps.wallet.models import WalletTransaction, OwnerWalletTransaction

from .serializers import (
    WalletSerializer,
    WalletTransactionSerializer,
    TopUpSerializer,
    OwnerWalletSerializer,
    OwnerTransactionSerializer,
)

logger = logging.getLogger('zygotrip.api.wallet')

WALLET_BALANCE_CACHE_TTL = 300  # 5 minutes


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_balance(request):
    """
    GET /api/v1/wallet/

    Returns current wallet balance + locked balance.
    Cached for 5 minutes per user (invalidated on transaction).
    """
    cache_key = f'wallet_balance_{request.user.id}'
    cached = cache.get(cache_key)
    if cached:
        return Response({'success': True, 'data': cached})

    wallet = get_or_create_wallet(request.user)
    data = WalletSerializer(wallet).data
    cache.set(cache_key, data, WALLET_BALANCE_CACHE_TTL)

    return Response({'success': True, 'data': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_transactions(request):
    """
    GET /api/v1/wallet/transactions/

    Paginated transaction history for the authenticated user's wallet.
    """
    wallet = get_or_create_wallet(request.user)
    qs = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(qs, request)
    serializer = WalletTransactionSerializer(page, many=True)

    return Response({
        'success': True,
        'data': {
            'results': serializer.data,
            'pagination': {
                'count': qs.count(),
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wallet_topup(request):
    """
    POST /api/v1/wallet/topup/
    Step 1: { amount } → returns cashfree payment_session_id + order_id
    Step 2: { amount, order_id, payment_reference } → verify + credit wallet
    """
    from django.conf import settings as _s
    from apps.core.models import PlatformSettings

    # Check platform settings
    try:
        ps = PlatformSettings.objects.first()
        if ps and not getattr(ps, 'wallet_topup_enabled', True):
            return Response({'success': False, 'error': 'Wallet top-up is currently disabled.'}, status=400)
        min_topup = float(getattr(ps, 'min_wallet_topup', 100))
        max_topup = float(getattr(ps, 'max_wallet_topup', 50000))
    except Exception:
        min_topup, max_topup = 100, 50000

    serializer = TopUpSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    amount = serializer.validated_data['amount']
    note = serializer.validated_data.get('note', 'Wallet top-up')
    order_id = request.data.get('order_id', '')
    payment_reference = request.data.get('payment_reference', '')

    # Validate amount limits
    if float(amount) < min_topup:
        return Response({'success': False, 'error': f'Minimum top-up amount is ₹{min_topup}'}, status=400)
    if float(amount) > max_topup:
        return Response({'success': False, 'error': f'Maximum top-up amount is ₹{max_topup}'}, status=400)

    # ── STEP 2: Verify payment and credit wallet ──────────────────────
    if order_id and payment_reference:
        try:
            import requests as _req
            env = getattr(_s, 'CASHFREE_ENV', 'sandbox')
            base_url = 'https://api.cashfree.com/pg' if env == 'production' else 'https://sandbox.cashfree.com/pg'
            headers = {
                'x-client-id': getattr(_s, 'CASHFREE_APP_ID', ''),
                'x-client-secret': getattr(_s, 'CASHFREE_SECRET_KEY', ''),
                'x-api-version': getattr(_s, 'CASHFREE_API_VERSION', '2025-01-01'),
            }
            resp = _req.get(f'{base_url}/orders/{order_id}', headers=headers, timeout=15)
            cf_data = resp.json()
            order_status = cf_data.get('order_status')
            logger.info('Wallet topup verify: order_id=%s status=%s', order_id, order_status)

            if order_status != 'PAID':
                return Response({'success': False, 'error': f'Payment not confirmed. Status: {order_status}'}, status=400)

            # Check not already credited
            wallet = get_or_create_wallet(request.user)
            if wallet.transactions.filter(reference=f'topup_{order_id}').exists():
                return Response({'success': False, 'error': 'This payment has already been credited.'}, status=400)

            # Credit wallet
            txn = wallet.credit(
                amount=amount,
                txn_type=WalletTransaction.TYPE_CREDIT,
                reference=f'topup_{order_id}',
                note=f'Wallet top-up via Cashfree ({order_id})',
            )
            cache.delete(f'wallet_balance_{request.user.id}')
            logger.info('Wallet top-up credited: user=%s amount=%s order=%s', request.user.email, amount, order_id)

            # Send SMS notification
            try:
                from apps.accounts.sms_service import get_sms_backend
                if request.user.phone:
                    get_sms_backend().send(request.user.phone, f'ZygoTrip wallet credited with Rs{amount}. New balance: Rs{wallet.balance}.')
            except Exception:
                pass

        except Exception as e:
            logger.error('Wallet topup verify failed: %s', e)
            return Response({'success': False, 'error': 'Payment verification failed. Contact support.'}, status=400)

        return Response({
            'success': True,
            'data': {
                'transaction_uid': str(txn.uid),
                'amount_credited': str(amount),
                'new_balance': str(wallet.balance),
                'currency': wallet.currency,
                'message': f'₹{amount} added to your ZygoWallet successfully!',
            },
        }, status=status.HTTP_201_CREATED)

    # ── STEP 1: Create Cashfree order for wallet topup ────────────────
    try:
        import requests as _req, uuid
        env = getattr(_s, 'CASHFREE_ENV', 'sandbox')
        base_url = 'https://api.cashfree.com/pg' if env == 'production' else 'https://sandbox.cashfree.com/pg'
        headers = {
            'x-client-id': getattr(_s, 'CASHFREE_APP_ID', ''),
            'x-client-secret': getattr(_s, 'CASHFREE_SECRET_KEY', ''),
            'x-api-version': getattr(_s, 'CASHFREE_API_VERSION', '2025-01-01'),
            'Content-Type': 'application/json',
        }
        wallet_order_id = f'WLT{str(uuid.uuid4()).replace("-","").upper()[:20]}'
        site_url = getattr(_s, 'PAYMENT_SUCCESS_URL', 'https://goexplorer-dev.cloud/payment-return/')
        payload = {
            'order_id': wallet_order_id,
            'order_amount': float(amount),
            'order_currency': 'INR',
            'order_note': 'ZygoTrip Wallet Top-up',
            'customer_details': {
                'customer_id': str(request.user.id),
                'customer_name': request.user.full_name or request.user.email,
                'customer_email': request.user.email,
                'customer_phone': request.user.phone or '9999999999',
            },
            'order_meta': {
                'return_url': f'https://goexplorer-dev.cloud/wallet/topup-return?order_id={wallet_order_id}&amount={amount}',
                'notify_url': getattr(_s, 'CASHFREE_WEBHOOK_URL', ''),
            },
        }
        resp = _req.post(f'{base_url}/orders', json=payload, headers=headers, timeout=15)
        cf_order = resp.json()
        logger.info('Wallet topup order created: %s', cf_order)

        if not cf_order.get('payment_session_id'):
            return Response({'success': False, 'error': 'Could not create payment order.'}, status=500)

        return Response({
            'success': True,
            'data': {
                'status': 'payment_required',
                'order_id': wallet_order_id,
                'payment_session_id': cf_order['payment_session_id'],
                'amount': str(amount),
                'cashfree_env': env,
            },
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error('Wallet topup order creation failed: %s', e)
        return Response({'success': False, 'error': 'Could not initiate payment. Try again.'}, status=500)

    wallet = get_or_create_wallet(request.user)
    logger.info('Wallet top-up confirmed: user=%s amount=%s', request.user.email, amount)

    return Response(
        {
            'success': True,
            'data': {
                'transaction_uid': str(txn.uid),
                'amount_credited': str(amount),
                'new_balance': str(wallet.balance),
                'currency': wallet.currency,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_wallet_balance(request):
    """
    GET /api/v1/wallet/owner/

    Returns the owner wallet balance (available + pending).
    Only accessible to users with property_owner role.
    """
    if not request.user.is_property_owner():
        return Response(
            {'success': False, 'error': {'code': 'forbidden', 'message': 'Only property owners can access the owner wallet.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    owner_wallet = get_or_create_owner_wallet(request.user)
    return Response({'success': True, 'data': OwnerWalletSerializer(owner_wallet).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def owner_wallet_transactions(request):
    """
    GET /api/v1/wallet/owner/transactions/

    Owner settlement transaction history.
    """
    if not request.user.is_property_owner():
        return Response(
            {'success': False, 'error': {'code': 'forbidden', 'message': 'Only property owners can access this resource.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    owner_wallet = get_or_create_owner_wallet(request.user)
    qs = OwnerWalletTransaction.objects.filter(owner_wallet=owner_wallet).order_by('-created_at')

    paginator = PageNumberPagination()
    paginator.page_size = 20
    page = paginator.paginate_queryset(qs, request)
    serializer = OwnerTransactionSerializer(page, many=True)

    return Response({
        'success': True,
        'data': {
            'results': serializer.data,
            'pagination': {
                'count': qs.count(),
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
        },
    })
