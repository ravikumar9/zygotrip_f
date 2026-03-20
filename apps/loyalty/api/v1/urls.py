from django.urls import path
from . import views

urlpatterns = [
    path('account/', views.LoyaltyAccountView.as_view(), name='loyalty-account'),
    path('history/', views.PointsHistoryView.as_view(), name='loyalty-history'),
    path('redeem-estimate/', views.RedeemEstimateView.as_view(), name='loyalty-redeem-estimate'),
    path('redeem/', views.RedeemView.as_view(), name='loyalty-redeem'),
]
