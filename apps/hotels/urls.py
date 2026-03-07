from django.urls import path
from .views import hotel_home, hotel_listing, hotel_details, hotel_booking, legacy_property_booking
from .api import suggest_hotels, get_recent_searches

app_name = "hotels"

urlpatterns = [
	path("", hotel_home, name="home"),  # /hotels/ - Landing page
	path("hotel-listing/", hotel_listing, name="listing"),  # /hotels/hotel-listing/ - Search results
	path("hotel-details/", hotel_details, name="details"),  # /hotels/hotel-details/?property=<slug>
	path("nhotel-booking/", hotel_booking, name="booking"),  # /hotels/nhotel-booking/?property=<slug>
	path("<int:property_id>/", legacy_property_booking, name="legacy_booking"),  # /hotels/<id>/ - legacy booking
	
	# API endpoints
	path("api/suggest/", suggest_hotels, name="api_suggest"),
	path("api/recent/", get_recent_searches, name="api_recent"),
]