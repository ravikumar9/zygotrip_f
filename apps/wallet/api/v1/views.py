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

    Initiates a wallet top-up. Does NOT credit directly — creates a pending
    payment transaction. Wallet is credited ONLY after payment gateway callback
    confirms the payment was successful (webhook/callback flow).

    Body: { amount: Decimal, note?: str, payment_reference?: str }
    """
    serializer = TopUpSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'success': False, 'error': {'code': 'validation_error', 'message': serializer.errors}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    amount = serializer.validated_data['amount']
    note = serializer.validated_data.get('note', 'Wallet top-up')
    payment_reference = request.data.get('payment_reference', '')

    # ── DEV MODE: Direct credit without payment gateway ──────────────
    # In development (DEBUG=True), skip payment verification and credit directly.
    # In production, require payment_reference from a completed gateway transaction.
    from django.conf import settings as django_settings
    if not payment_reference and getattr(django_settings, 'DEBUG', False):
        wallet = get_or_create_wallet(request.user)
        txn = wallet.credit(
            amount=amount,
            txn_type=WalletTransaction.TYPE_CREDIT,
            reference=f'dev_topup_{request.user.id}_{amount}',
            note=note or 'Wallet top-up (dev mode)',
        )
        cache.delete(f'wallet_balance_{request.user.id}')
        logger.info('DEV wallet top-up: user=%s amount=%s', request.user.email, amount)
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

    if not payment_reference:
        # No payment reference: return a pending status, instruct client to
        # complete payment via gateway then call back with reference.
        return Response(
            {
                'success': True,
                'data': {
                    'status': 'pending_payment',
                    'amount': str(amount),
                    'message': 'Complete payment via gateway, then confirm with payment_reference.',
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )

    # With a payment reference, verify and credit.
    try:
        from apps.payments.models import PaymentTransaction
        payment = PaymentTransaction.objects.get(
            transaction_id=payment_reference,
            user=request.user,
            status=PaymentTransaction.STATUS_SUCCESS if hasattr(PaymentTransaction, 'STATUS_SUCCESS') else 'success',
        )
        if payment.amount != amount:
            return Response(
                {'success': False, 'error': {'code': 'amount_mismatch',
                    'message': 'Payment amount does not match topup amount.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except ImportError:
        logger.error('wallet_topup: PaymentTransaction model not available')
        return Response(
            {'success': False, 'error': {'code': 'payment_verification_unavailable',
                'message': 'Payment verification system unavailable. Try again later.'}},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as e:
        logger.error('wallet_topup: Payment verification failed for ref=%s: %s', payment_reference, e)
        return Response(
            {'success': False, 'error': {'code': 'payment_verification_failed',
                'message': 'Could not verify payment. Ensure the payment reference is valid and completed.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    wallet = get_or_create_wallet(request.user)
    txn = wallet.credit(
        amount=amount,
        txn_type=WalletTransaction.TYPE_CREDIT,
        reference=f'topup_{payment_reference}',
        note=note,
    )

    # Invalidate cache
    cache.delete(f'wallet_balance_{request.user.id}')

    logger.info('Wallet top-up confirmed: user=%s amount=%s ref=%s', request.user.email, amount, payment_reference)

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
