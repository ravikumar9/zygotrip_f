"""Payments URLs."""
from django.urls import path

from .views import invoice_detail, payment_webhook

urlpatterns = [
	path("<uuid:invoice_uuid>/", invoice_detail, name="invoice_detail"),
	path("webhook/", payment_webhook, name="payment_webhook"),
]