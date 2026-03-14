from django.urls import include, path
from .views import approve_property, dashboard, reject_property
from .ops_api import get_urls as ops_urls

app_name = 'dashboard_admin'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('approvals/<int:approval_id>/approve/', approve_property, name='approve'),
    path('approvals/<int:approval_id>/reject/', reject_property, name='reject'),
    path('api/ops/', include((ops_urls(), 'ops'))),
]