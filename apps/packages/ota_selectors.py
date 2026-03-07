"""
OTA FILTER ENGINE FOR PACKAGES - Backend-Driven QuerySet Logic
Enforces 8 Rules with strict data integrity
"""
from django.db.models import (
    Q, Count, Min, Max, F, Value, DecimalField, IntegerField
)
from apps.packages.models import Package


def ota_visible_packages():
    """RULE 1: ZERO HARDCODED COUNTS
    
    Returns base queryset with all visible packages.
    ALL counts must come from database, not strings or constants.
    """
    return (
        Package.objects
        .filter(status='active')
        .select_related('category', 'owner')
        .prefetch_related('itineraries', 'images')
    )


def get_filter_counts(queryset):
    """RULE 1: Compute all filter counts from queryset
    
    Returns dict with dynamic counts for each filter section.
    NOT hardcoded. NOT preset. Recomputed per request.
    """
    base_qs = queryset
    counts = {
        # Category counts
        'categories': dict(
            base_qs.values('category__name')
            .annotate(count=Count('id', distinct=True))
            .filter(category__name__isnull=False)
            .values_list('category__name', 'count')
        ),
        
        # Duration-based filtering
        'duration_1_to_3': base_qs.filter(duration_days__gte=1, duration_days__lte=3).count(),
        'duration_4_to_7': base_qs.filter(duration_days__gte=4, duration_days__lte=7).count(),
        'duration_8_plus': base_qs.filter(duration_days__gt=7).count(),
        
        # Price ranges
        'price_budget': base_qs.filter(price__lt=15000).count(),
        'price_mid': base_qs.filter(price__gte=15000, price__lt=50000).count(),
        'price_premium': base_qs.filter(price__gte=50000).count(),
    }
    return counts


def apply_search_filters(queryset, params):
    """RULE 2: URL-STATEFUL SEARCH
    
    Binds request.GET parameters to QuerySet filtering.
    All search values come from query string, never hardcoded.
    """
    import sys
    
    # DESTINATION FILTER
    destination = (params.get('destination', '') or '').strip()
    if destination:
        print(f"[PACKAGES_FILTER] Filtering by destination: {destination}", file=sys.stderr)
        queryset = queryset.filter(
            Q(title__icontains=destination) |
            Q(description__icontains=destination)
        )
        print(f"[PACKAGES_FILTER] After destination filter: {queryset.count()}", file=sys.stderr)
    
    # DURATION FILTER
    duration = params.get('duration', '')
    if duration:
        try:
            duration_val = int(duration)
            print(f"[PACKAGES_FILTER] Filtering duration = {duration_val} days", file=sys.stderr)
            queryset = queryset.filter(duration_days=duration_val)
            print(f"[PACKAGES_FILTER] After duration filter: {queryset.count()}", file=sys.stderr)
        except (ValueError, TypeError):
            pass
    
    # PRICE FILTER
    min_price = params.get('min_price', '')
    max_price = params.get('max_price', '')
    
    if min_price:
        try:
            min_val = int(min_price)
            print(f"[PACKAGES_FILTER] Filtering min_price >= {min_val}", file=sys.stderr)
            queryset = queryset.filter(price__gte=min_val)
            print(f"[PACKAGES_FILTER] After min_price filter: {queryset.count()}", file=sys.stderr)
        except (ValueError, TypeError):
            pass
    
    if max_price:
        try:
            max_val = int(max_price)
            print(f"[PACKAGES_FILTER] Filtering max_price <= {max_val}", file=sys.stderr)
            queryset = queryset.filter(price__lte=max_val)
            print(f"[PACKAGES_FILTER] After max_price filter: {queryset.count()}", file=sys.stderr)
        except (ValueError, TypeError):
            pass
    
    # CATEGORY FILTER
    categories = params.getlist('category')
    if categories:
        print(f"[PACKAGES_FILTER] Filtering categories: {categories}", file=sys.stderr)
        queryset = queryset.filter(category__name__in=categories)
        print(f"[PACKAGES_FILTER] After category filter: {queryset.count()}", file=sys.stderr)
    
    return queryset


def apply_sorting(queryset, sort_param):
    """RULE 3: SORT PILLS MUST MODIFY QUERYSET
    
    All sorting is QuerySet.order_by(), not UI cosmetics.
    Results actually reorder based on sort selection.
    
    Valid values: popular, price_asc, price_desc, rating, newest
    """
    import sys
    
    if not sort_param:
        sort_param = 'popular'
    
    sort_param = sort_param.lower().strip()
    
    ids_before = list(queryset.values_list("id", flat=True)[:5])
    print(f"[PACKAGES_SORT] IDs before sort (param={sort_param}): {ids_before}", file=sys.stderr)
    
    if sort_param == 'price_asc':
        queryset = queryset.order_by('price')
        ids_after = list(queryset.values_list("id", flat=True)[:5])
        print(f"[PACKAGES_SORT] IDs after sort (price_asc): {ids_after}", file=sys.stderr)
        return queryset
    
    elif sort_param == 'price_desc':
        queryset = queryset.order_by('-price')
        ids_after = list(queryset.values_list("id", flat=True)[:5])
        print(f"[PACKAGES_SORT] IDs after sort (price_desc): {ids_after}", file=sys.stderr)
        return queryset
    
    elif sort_param == 'newest':
        queryset = queryset.order_by('-created_at')
        return queryset
    
    elif sort_param == 'rating':
        queryset = queryset.order_by('-rating')
        return queryset
    
    else:  # popular (default)
        queryset = queryset.order_by('-popularity_score')
        return queryset


def serialize_package_card(package_obj):
    """RULE 4: SERIALIZE HOTEL CARD DATA
    
    Convert package object to frontend-ready dict.
    NO hardcoded product names.
    All data from database fields.
    """
    
    return {
        'id': package_obj.id,
        'title': package_obj.title,
        'slug': getattr(package_obj, 'slug', ''),
        'description': package_obj.description or '',
        'category': package_obj.category.name if package_obj.category else 'Uncategorized',
        'price': int(package_obj.price) if package_obj.price else 0,
        'duration_days': package_obj.duration_days,
        'rating': float(getattr(package_obj, 'rating', 0)),
        'review_count': getattr(package_obj, 'review_count', 0),
        'popularity_score': getattr(package_obj, 'popularity_score', 0),
        'image_url': (package_obj.images.first().image.url 
                      if (package_obj.images.exists() and 
                          package_obj.images.first().image and 
                          package_obj.images.first().image.name)
                      else '/static/placeholder.jpg'),
    }


def get_ota_context(request):
    """RULE 7: BUILD COMPLETE CONTEXT WITH VALIDATED DATA
    
    Returns context dict with:
    - listings: Queryset filtered by request params
    - filter_counts: Dynamic counts from database
    - selected_filters: Current filter state
    - sort: Current sort param
    - total_count: Actual result count
    """
    import sys
    params = request.GET
    
    print("[PACKAGES_OTA] Incoming params:", dict(params), file=sys.stderr)
    
    # Start with base queryset
    base_qs = ota_visible_packages()
    base_count = base_qs.count()
    print(f"[PACKAGES_OTA] Base queryset count: {base_count}", file=sys.stderr)
    
    # Apply all filters
    filtered_qs = apply_search_filters(base_qs, params)
    filtered_count = filtered_qs.count()
    print(f"[PACKAGES_OTA] After filters count: {filtered_count}", file=sys.stderr)
    
    # Apply sorting
    sort_param = params.get('sort', 'popular')
    sorted_qs = apply_sorting(filtered_qs, sort_param)
    
    # Compute filter counts from filtered queryset
    filter_options = get_filter_counts(filtered_qs)
    
    # Serialize cards from database
    packages = [serialize_package_card(pkg) for pkg in sorted_qs]
    
    # Track selected filters
    selected_filters = {
        'destination': params.get('destination', ''),
        'min_price': params.get('min_price', ''),
        'max_price': params.get('max_price', ''),
        'duration': params.get('duration', ''),
        'categories': params.getlist('category'),
    }
    
    # Empty state messaging
    if len(packages) == 0:
        if base_count == 0:
            empty_state_message = "No packages available right now."
        else:
            empty_state_message = "No packages match your filters. Try adjusting your search."
    else:
        empty_state_message = ""
    
    return {
        'packages': packages,
        'empty_state': len(packages) == 0,
        'empty_state_message': empty_state_message,
        'total_count': len(packages),
        'filter_options': filter_options,
        'selected_filters': selected_filters,
        'current_sort': sort_param,
        'current_query': dict(params),
    }
