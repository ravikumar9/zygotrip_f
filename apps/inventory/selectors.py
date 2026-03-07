"""
Read-only database operations for inventory domain
PHASE 2: Domain standardization
"""
from django.utils import timezone

try:
    from apps.rooms.models import RoomInventory, RoomType
except Exception:
    RoomInventory = None
    RoomType = None


def get_inventory_for_range(room_type, start_date, end_date):
    """Get inventory for room type in date range"""
    if RoomInventory is None:
        return []
    return RoomInventory.objects.filter(
        room_type=room_type,
        date__gte=start_date,
        date__lt=end_date
    ).order_by('date')


def get_available_rooms_for_date(room_type, date):
    """Get available room count for specific date"""
    if RoomInventory is None:
        return 0
    try:
        inventory = RoomInventory.objects.get(room_type=room_type, date=date)
        return inventory.available
    except RoomInventory.DoesNotExist:
        return 0


def check_availability(room_type, start_date, end_date, quantity):
    """Check if quantity of rooms available for date range"""
    if RoomInventory is None:
        return False
    inventories = get_inventory_for_range(room_type, start_date, end_date)
    for inv in inventories:
        if inv.available < quantity:
            return False
    return True


def get_inventory_status(property_obj, start_date, end_date):
    """Get inventory status for all room types of property"""
    if RoomType is None:
        return []
    room_types = RoomType.objects.filter(property=property_obj, is_active=True)
    
    status = []
    for rt in room_types:
        inventories = get_inventory_for_range(rt, start_date, end_date)
        status.append({
            'room_type': rt,
            'inventories': list(inventories)
        })
    return status