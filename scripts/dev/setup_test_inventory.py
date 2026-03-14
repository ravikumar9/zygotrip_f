"""Add calendar inventory for testing."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zygotrip_project.settings')
django.setup()

from datetime import date, timedelta
from apps.inventory.models import CalendarInventory
from apps.rooms.models import RoomType

checkin = date.today() + timedelta(days=7)
checkout = date.today() + timedelta(days=8)

# Get all room types for property 250
rts = RoomType.objects.filter(property_id=250)
for rt in rts:
    print(f'RT {rt.id}: {rt.name} (total_rooms={rt.total_rooms})')
    # Add inventory for checkin date
    for d in [checkin, checkout]:
        obj, created = CalendarInventory.objects.get_or_create(
            room_type=rt,
            date=d,
            defaults={
                'available': max(rt.total_rooms, 5),
                'total_rooms': max(rt.total_rooms, 5),
                'base_price': rt.base_price if hasattr(rt, 'base_price') and rt.base_price else 5000,
            }
        )
        if not created and obj.available < 1:
            obj.available = max(rt.total_rooms, 5)
            obj.save()
            print(f'  Updated {d}: available={obj.available}')
        else:
            print(f'  {"Created" if created else "Exists"} {d}: available={obj.available}')

print('\nInventory setup complete!')
