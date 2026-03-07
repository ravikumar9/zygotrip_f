"""
Hotel API endpoints for autocomplete and suggestions
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q, Count
from apps.core.models import City
from apps.hotels.models import Property


@require_GET
def suggest_hotels(request):
    """Autosuggest endpoint for hotel search

    Returns JSON with cities, areas, and properties matching the query.
    Uses annotated counts to avoid N+1 queries.

    URL: /api/hotels/suggest/?q=banger
    Returns: {
        cities: [{id, name, state, count}, ...],
        areas:  [{name, city, count}, ...],
        properties: [{id, name, city, area, rating, review_count}, ...]
    }
    """
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'cities': [], 'areas': [], 'properties': []})

    # Cities — annotate property count in one query (no N+1)
    cities = (
        City.objects.filter(Q(name__icontains=query), is_active=True)
        .annotate(
            property_count=Count(
                'hotels',
                filter=Q(hotels__status='approved', hotels__agreement_signed=True),
            )
        )
        .select_related('state')[:5]
    )

    cities_data = [
        {
            'id': city.id,
            'name': city.name,
            'state': city.state.name if city.state else '',
            'count': city.property_count,
        }
        for city in cities
    ]

    # Areas — group by area + city name, count in one query
    areas_raw = (
        Property.objects.filter(
            Q(area__icontains=query),
            status='approved',
            agreement_signed=True,
        )
        .exclude(area='')
        .select_related('city')
        .values('area', 'city__name')
        .annotate(count=Count('id'))
        .order_by('area')[:5]
    )

    areas_data = [
        {
            'name': row['area'],
            'city': row['city__name'] or '',
            'count': row['count'],
        }
        for row in areas_raw
    ]

    # Properties — select_related city to avoid N+1
    properties = (
        Property.objects.filter(
            Q(name__icontains=query) | Q(landmark__icontains=query),
            status='approved',
            agreement_signed=True,
        )
        .select_related('city')[:5]
    )

    properties_data = [
        {
            'id': prop.id,
            'name': prop.name,
            'city': prop.city.name if prop.city else '',
            'area': prop.area or '',
            'rating': float(prop.rating) if prop.rating else 0,
            'review_count': prop.review_count,
        }
        for prop in properties
    ]

    return JsonResponse({
        'cities': cities_data,
        'areas': areas_data,
        'properties': properties_data,
    })




@require_GET
def get_recent_searches(request):
    """Get user's recent hotel searches
    
    Returns last 5 searches for authenticated user
    or based on session key for anonymous users
    
    URL: /api/hotels/recent/
    Returns: {
        searches: [{location, checkin, checkout, guests, created_at}, ...]
    }
    """
    if request.user.is_authenticated:
        from apps.hotels.models import RecentSearch
        searches = RecentSearch.objects.filter(
            user=request.user
        ).distinct('location', 'checkin', 'checkout')[:5]
    else:
        # For anonymous users, use session
        session_key = request.session.session_key or ''
        from apps.hotels.models import RecentSearch
        searches = RecentSearch.objects.filter(
            session_key=session_key,
            user__isnull=True
        ).distinct('location', 'checkin', 'checkout')[:5]
    
    searches_data = [
        {
            'location': search.location or 'Any',
            'checkin': search.checkin.isoformat() if search.checkin else None,
            'checkout': search.checkout.isoformat() if search.checkout else None,
            'guests': search.guests,
            'created_at': search.created_at.isoformat(),
        }
        for search in searches
    ]
    
    return JsonResponse({
        'searches': searches_data
    })
