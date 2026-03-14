"""Gateway service registry and request routing helpers."""

import re


DEFAULT_API_VERSION = 'v1'
REGISTRY_VERSION = 1

SERVICE_DEFINITIONS = (
    {
        'service': 'gateway',
        'category': 'platform',
        'public_prefixes': ['/api/v1/gateway/'],
        'health_path': '/api/health/',
        'extraction_stage': 'edge-control-plane',
    },
    {
        'service': 'core-platform',
        'category': 'platform',
        'public_prefixes': [
            '/api/v1/places/',
            '/api/v1/currency/',
            '/api/v1/geo-search/',
            '/api/v1/map/',
            '/api/v1/analytics/',
            '/api/v1/ab-test/',
            '/api/v1/recommendations/',
            '/api/v1/devices/',
            '/api/v1/admin/monitoring/',
            '/api/v1/route/',
            '/api/v1/email/',
        ],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'shared-platform-services',
    },
    {
        'service': 'search',
        'category': 'discovery',
        'public_prefixes': ['/api/v1/seo/', '/api/search/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'search-service-ready',
    },
    {
        'service': 'hotels',
        'category': 'vertical',
        'public_prefixes': ['/api/v1/properties/', '/api/v1/search/', '/api/hotels/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'vertical-service-ready',
    },
    {
        'service': 'pricing',
        'category': 'commerce',
        'public_prefixes': ['/api/v1/rate-plans/', '/api/v1/pricing/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'domain-service-ready',
    },
    {
        'service': 'booking',
        'category': 'commerce',
        'public_prefixes': ['/api/v1/booking/', '/booking/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'orchestrator-service-ready',
    },
    {
        'service': 'payments',
        'category': 'commerce',
        'public_prefixes': ['/api/v1/payment/', '/invoice/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'regulated-service-ready',
    },
    {
        'service': 'wallet',
        'category': 'commerce',
        'public_prefixes': ['/api/v1/wallet/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'ledger-service-ready',
    },
    {
        'service': 'checkout',
        'category': 'commerce',
        'public_prefixes': ['/api/v1/checkout/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'bundle-service-ready',
    },
    {
        'service': 'promotions',
        'category': 'growth',
        'public_prefixes': ['/api/v1/promo/', '/api/v1/offers/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'campaign-service-ready',
    },
    {
        'service': 'supplier-sync',
        'category': 'integration',
        'public_prefixes': ['/api/v1/supplier/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'integration-service-ready',
    },
    {
        'service': 'notifications',
        'category': 'platform',
        'public_prefixes': ['/api/v1/notifications/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'channel-service-ready',
    },
    {
        'service': 'dashboard-owner',
        'category': 'operations',
        'public_prefixes': ['/api/v1/dashboard/owner/', '/owner/dashboard/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'read-optimized-service',
    },
    {
        'service': 'flights',
        'category': 'vertical',
        'public_prefixes': ['/api/v1/flights/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'vertical-service-ready',
    },
    {
        'service': 'buses',
        'category': 'vertical',
        'public_prefixes': ['/api/v1/buses/', '/buses/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'vertical-service-ready',
    },
    {
        'service': 'cabs',
        'category': 'vertical',
        'public_prefixes': ['/api/v1/cabs/', '/cabs/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'vertical-service-ready',
    },
    {
        'service': 'packages',
        'category': 'vertical',
        'public_prefixes': ['/api/v1/packages/', '/packages/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'vertical-service-ready',
    },
    {
        'service': 'activities',
        'category': 'vertical',
        'public_prefixes': ['/api/v1/activities/'],
        'health_path': '/api/health/detailed/',
        'extraction_stage': 'vertical-service-ready',
    },
)

_VERSION_RE = re.compile(r'^/api/(?P<version>v\d+)/')
_ROUTE_INDEX = sorted(
    (
        (prefix.rstrip('/') + '/', definition['service'])
        for definition in SERVICE_DEFINITIONS
        for prefix in definition['public_prefixes']
    ),
    key=lambda item: len(item[0]),
    reverse=True,
)


def resolve_api_version(path: str) -> str:
    """Resolve an API version tag from a request path."""
    normalized = path or ''
    match = _VERSION_RE.match(normalized)
    if match:
        return match.group('version')
    if normalized.startswith('/api/'):
        return 'legacy'
    return 'web'


def resolve_service_name(path: str) -> str:
    """Resolve the owning public service boundary for a request path."""
    normalized = (path or '/').rstrip('/') + '/'
    for prefix, service in _ROUTE_INDEX:
        if normalized.startswith(prefix):
            return service
    if normalized.startswith('/api/'):
        return 'core-platform'
    return 'web'


def get_service_registry():
    """Return a serializable copy of the public gateway registry."""
    return [
        {
            **definition,
            'api_version': DEFAULT_API_VERSION,
        }
        for definition in SERVICE_DEFINITIONS
    ]


def build_gateway_registry_payload(path: str = '') -> dict:
    """Build the discovery payload exposed by the gateway registry endpoint."""
    request_path = path or ''
    request_service = resolve_service_name(request_path) if request_path else ''
    request_version = resolve_api_version(request_path) if request_path else ''
    services = get_service_registry()
    return {
        'gateway': {
            'registry_version': REGISTRY_VERSION,
            'default_api_version': DEFAULT_API_VERSION,
            'service_count': len(services),
        },
        'request': {
            'path': request_path,
            'service': request_service,
            'api_version': request_version,
        },
        'services': services,
    }