from django.contrib import admin
from .models import AuditLog, PropertyApproval


admin.site.register(PropertyApproval)
admin.site.register(AuditLog)

# Register your models here.