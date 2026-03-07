from django.urls import path
from .views import approve_property, dashboard, reject_property

app_name = 'dashboard_admin'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('approvals/<int:approval_id>/approve/', approve_property, name='approve'),
    path('approvals/<int:approval_id>/reject/', reject_property, name='reject'),
]