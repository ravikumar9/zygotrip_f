"""ViewModel layer for hotel data presentation.

This layer sits between the service layer and templates.
Its sole responsibility: transform data into presentation objects.

Rule: Templates NEVER receive ORM instances. Only ViewModels.
"""

from .hotel_card_vm import HotelCardVM
from .hotel_detail_vm import HotelDetailVM
from .filters_vm import FiltersVM, FilterOptionVM

__all__ = [
    'HotelCardVM',
    'HotelDetailVM',
    'FiltersVM',
    'FilterOptionVM',
]