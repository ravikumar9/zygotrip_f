from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import Permission, Role, RolePermission, User, UserRole


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
	model = User
	list_display = ('email', 'full_name', 'is_staff', 'is_active')
	search_fields = ('email', 'full_name')
	ordering = ('email',)
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Profile', {'fields': ('full_name', 'phone')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
	)
	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'full_name', 'password1', 'password2', 'is_staff', 'is_active'),
		}),
	)


admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(UserRole)
admin.site.register(RolePermission)

# Register your models here.