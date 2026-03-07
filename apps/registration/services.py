from django.apps import apps


def ensure_role(user, role_code, role_name):
    role_model = apps.get_model('accounts', 'Role')
    user_role_model = apps.get_model('accounts', 'UserRole')
    role, _ = role_model.objects.get_or_create(code=role_code, defaults={'name': role_name})
    user_role_model.objects.get_or_create(user=user, role=role)
    return role


def create_property_from_form(form, user):
    from django.utils import timezone
    from apps.dashboard_admin.models import PropertyApproval
    property_obj = form.save(commit=False)
    property_obj.owner = user
    property_obj.save()
    PropertyApproval.objects.get_or_create(
        property=property_obj,
        defaults={
            "status": PropertyApproval.STATUS_APPROVED,
            "decided_by": user,
            "decided_at": timezone.now(),
            "notes": "Auto-approved registration",
        },
    )
    return property_obj


def create_bus_from_form(form, user):
    bus_model = apps.get_model('buses', 'Bus')
    bus = bus_model.objects.create(
        operator=user,
        name=form.cleaned_data['bus_name'],
        registration_number=form.cleaned_data['registration_number'],
        capacity=form.cleaned_data['capacity'],
        route_from=form.cleaned_data['route_from'],
        route_to=form.cleaned_data['route_to'],
        base_fare=form.cleaned_data['base_fare'],
    )
    return bus


def create_cab_from_form(form, user):
    cab_model = apps.get_model('cabs', 'Cab')
    cab = cab_model.objects.create(
        operator=user,
        vehicle_type=form.cleaned_data['vehicle_type'],
        registration_number=form.cleaned_data['registration_number'],
        city_coverage=form.cleaned_data['city_coverage'],
        base_fare=form.cleaned_data['base_fare'],
    )
    return cab
