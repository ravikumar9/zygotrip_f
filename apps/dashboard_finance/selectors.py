from django.apps import apps


def get_recent_payments(limit=20):
    payment_model = apps.get_model('payments', 'Payment')
    return payment_model.objects.order_by('-created_at')[:limit]


def get_recent_wallets(limit=20):
    wallet_model = apps.get_model('wallet', 'Wallet')
    return wallet_model.objects.order_by('-updated_at')[:limit]
