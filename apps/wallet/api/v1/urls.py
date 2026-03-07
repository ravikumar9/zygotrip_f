"""Wallet API URLs — mounted at /api/v1/wallet/"""
from django.urls import path
from . import views

urlpatterns = [
    # Customer wallet
    path('', views.wallet_balance, name='api_wallet_balance'),
    path('transactions/', views.wallet_transactions, name='api_wallet_transactions'),
    path('topup/', views.wallet_topup, name='api_wallet_topup'),

    # Owner wallet
    path('owner/', views.owner_wallet_balance, name='api_owner_wallet_balance'),
    path('owner/transactions/', views.owner_wallet_transactions, name='api_owner_wallet_transactions'),
]
