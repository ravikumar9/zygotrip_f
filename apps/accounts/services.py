from .models import Role, UserRole


def assign_customer_role(user):
    role = Role.objects.filter(code='customer').first()
    if role:
        UserRole.objects.get_or_create(user=user, role=role)
    return role


def assign_role(user, role_code):
    """Assign any role by code to a user (creates UserRole record)."""
    role = Role.objects.filter(code=role_code).first()
    if role:
        UserRole.objects.get_or_create(user=user, role=role)
    return role
