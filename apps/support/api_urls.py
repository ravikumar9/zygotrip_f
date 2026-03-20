from django.urls import path

from . import api_views

app_name = 'support'

urlpatterns = [
    path('tickets/', api_views.support_ticket_list_create, name='support_ticket_list_create'),
    path('tickets/<int:ticket_id>/', api_views.support_ticket_detail, name='support_ticket_detail'),
    path('tickets/<int:ticket_id>/messages/', api_views.support_ticket_add_message, name='support_ticket_add_message'),
]
