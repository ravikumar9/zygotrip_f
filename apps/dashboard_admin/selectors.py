from django.shortcuts import get_object_or_404
from .models import PropertyApproval


def get_pending_approvals():
    return PropertyApproval.objects.filter(status=PropertyApproval.STATUS_PENDING)


def get_approval_or_404(approval_id):
    return get_object_or_404(PropertyApproval, id=approval_id)
