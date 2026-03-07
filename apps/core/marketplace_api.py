"""
Marketplace API endpoints for enterprise UX features.
"""
from django.http import JsonResponse
from django.views import View
from django.db.models import Q
from django.utils import timezone
from .marketplace_models import Destination, Category, Offer, SearchIndex


class SearchAutocompleteAPI(View):
    """Autocomplete suggestions for global search."""
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'results': []})
        
        # Search across all index types
        results = SearchIndex.objects.filter(
            Q(normalized_name__istartswith=query.lower()) |
            Q(normalized_name__icontains=query.lower()),
            is_active=True
        )[:10]
        
        suggestions = []
        for item in results:
            suggestions.append({
                'type': item.search_type,
                'name': item.name,
                'city': item.city,
                'state': item.state,
                'count': item.search_count,
            })
        
        return JsonResponse({'results': suggestions})


class TrendingDestinationsAPI(View):
    """Trending destinations for homepage."""
    
    def get(self, request):
        destinations = Destination.objects.filter(
            is_trending=True
        )[:6]
        
        data = []
        for dest in destinations:
            data.append({
                'id': dest.id,
                'name': dest.name,
                'country': dest.country,
                'state': dest.state,
                'description': dest.description[:100],
                'image': dest.image.url if dest.image else None,
                'slug': dest.slug,
            })
        
        return JsonResponse({'destinations': data})


class CategoriesAPI(View):
    """Active service categories."""
    
    def get(self, request):
        categories = Category.objects.filter(is_active=True)
        
        data = []
        for cat in categories:
            data.append({
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'icon': cat.icon,
                'description': cat.description,
                'url': cat.get_absolute_url(),
            })
        
        return JsonResponse({'categories': data})


class OffersAPI(View):
    """Active promotional offers."""
    
    def get(self, request):
        now = timezone.now()
        offers = Offer.objects.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        )[:5]
        
        data = []
        for offer in offers:
            data.append({
                'id': offer.id,
                'title': offer.title,
                'subtitle': offer.subtitle,
                'type': offer.offer_type,
                'discount': str(offer.discount_value),
                'code': offer.code,
                'image': offer.image.url if offer.image else None,
                'valid_until': offer.valid_until.isoformat(),
                'category': offer.category.name if offer.category else None,
            })
        
        return JsonResponse({'offers': data})