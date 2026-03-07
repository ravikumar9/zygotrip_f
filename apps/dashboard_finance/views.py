from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from apps.accounts.selectors import user_has_role
from django.contrib.auth.decorators import login_required
from .selectors import get_recent_payments, get_recent_wallets


@login_required
def dashboard(request):
	if not user_has_role(request.user, 'finance_admin'):
		raise PermissionDenied
	payments = get_recent_payments()
	wallets = get_recent_wallets()
	return render(request, 'dashboard_finance/dashboard.html', {'payments': payments, 'wallets': wallets})

# Create your views here.