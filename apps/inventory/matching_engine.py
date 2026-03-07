"""
Supplier Property Matching Engine

Matches supplier properties to internal properties with strict validation rules:
- Name similarity must be > 80% (using token_sort_ratio)
- Geographic distance must be < 1km
- Confidence threshold for automatic matching: > 0.85
- Confidence threshold for manual review: 0.7-0.85
- Confidence < 0.7: Rejection
"""

from decimal import Decimal
import logging
from typing import Tuple, Optional
from fuzzywuzzy import fuzz
from django.db import transaction
from django.utils import timezone
from apps.core.models import OperationLog
from apps.hotels.models import Property
from apps.inventory.models import SupplierPropertyMap

logger = logging.getLogger('zygotrip')

# Configuration constants
CONFIG = {
    'MIN_NAME_SIMILARITY': 80,           # Minimum name match %
    'MAX_DISTANCE_KM': 1.0,              # Maximum geographic distance in km
    'AUTO_MATCH_THRESHOLD': 0.85,        # Auto-match confidence
    'MANUAL_REVIEW_THRESHOLD': 0.70,     # Manual review range
    'MIN_VIABLE_CONFIDENCE': 0.70,       # Minimum acceptable confidence
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two geographic points using Haversine formula.
    
    Returns distance in kilometers.
    """
    from math import radians, cos, sin, asin, sqrt
    
    # Convert to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of Earth in kilometers
    r = 6371
    
    return c * r


def calculate_match_score(
    internal_property: Property,
    supplier_name: str,
    supplier_city: str,
    supplier_lat: Optional[float] = None,
    supplier_lng: Optional[float] = None
) -> Tuple[float, str]:
    """
    Calculate matching confidence score between internal and supplier property.
    
    Scoring breakdown:
    - Name similarity: 50% weight (must be > 80% to proceed)
    - Location match: 50% weight (must be < 1km to proceed)
    
    Args:
        internal_property: Internal Property object
        supplier_name: Supplier's property name
        supplier_city: Supplier's city
        supplier_lat: Supplier's latitude
        supplier_lng: Supplier's longitude
    
    Returns:
        Tuple of (confidence_score: float, reason: str)
        confidence_score: 0.0-1.0
        reason: Explanation of score
    """
    
    reasons = []
    
    # Step 1: City match (quick filter)
    city_match = internal_property.city.lower().strip() == supplier_city.lower().strip()
    if not city_match:
        return 0.0, "City mismatch"
    
    # Step 2: Name similarity (token_sort_ratio handles reordering)
    name_similarity = fuzz.token_sort_ratio(
        internal_property.name.lower(),
        supplier_name.lower()
    ) / 100.0  # Convert to 0-1 scale
    
    reasons.append(f"Name similarity: {name_similarity*100:.1f}%")
    
    if name_similarity < CONFIG['MIN_NAME_SIMILARITY'] / 100:
        return 0.0, f"Name similarity {name_similarity*100:.1f}% < {CONFIG['MIN_NAME_SIMILARITY']}%"
    
    # Step 3: Geographic distance (if coordinates available)
    if supplier_lat and supplier_lng and internal_property.latitude and internal_property.longitude:
        distance_km = haversine_distance(
            float(internal_property.latitude),
            float(internal_property.longitude),
            supplier_lat,
            supplier_lng
        )
        
        reasons.append(f"Distance: {distance_km:.2f}km")
        
        if distance_km > CONFIG['MAX_DISTANCE_KM']:
            return 0.0, f"Distance {distance_km:.2f}km > {CONFIG['MAX_DISTANCE_KM']}km"
        
        # Distance score: closer is better (0-1)
        distance_score = max(0, 1 - (distance_km / CONFIG['MAX_DISTANCE_KM']))
    else:
        # No coordinates available, use conservative estimate
        distance_score = 0.5
        reasons.append("Distance: no coordinates")
    
    # Step 4: Combined scoring
    # Weights: name (50%) + distance (50%)
    confidence = (name_similarity * 0.5) + (distance_score * 0.5)
    
    reasons.append(f"Final score: {confidence:.2f}")
    
    return confidence, " | ".join(reasons)


def match_supplier_property(
    supplier_name: str,
    external_id: str,
    supplier_property_name: str,
    supplier_city: str,
    supplier_lat: Optional[float] = None,
    supplier_lng: Optional[float] = None,
    force_verify: bool = False
) -> Tuple[Optional[Property], float, str]:
    """
    Find best matching internal property for a supplier property.
    
    Matching algorithm:
    1. Filter internal properties by city
    2. Calculate confidence score for each
    3. Return best match if confidence >= threshold
    
    Validation rules:
    - Confidence < 0.70: Reject with error
    - Confidence 0.70-0.85: Flag for manual review
    - Confidence > 0.85: Auto-approve if force_verify=False
    
    Args:
        supplier_name: Supplier identifier (e.g., 'booking', 'airbnb')
        external_id: Supplier's property ID
        supplier_property_name: Property name from supplier
        supplier_city: Property city from supplier
        supplier_lat: Property latitude from supplier
        supplier_lng: Property longitude from supplier
        force_verify: If True, skip manual review for 0.70-0.85 range
    
    Returns:
        Tuple of:
        - matched_property: Property object or None
        - confidence_score: 0.0-1.0
        - status: 'approved', 'manual_review', or 'rejected'
    """
    
    # Check for duplicate external ID (strict rule)
    existing = SupplierPropertyMap.objects.filter(
        supplier_name=supplier_name,
        external_id=external_id
    ).first()
    
    if existing:
        OperationLog.objects.create(
            operation_type='mapping_decision',
            status='failed',
            details=str({
                'supplier_name': supplier_name,
                'external_id': external_id,
                'reason': 'duplicate_external_id',
            }),
            timestamp=timezone.now(),
        )
        return None, 0.0, f"Duplicate external ID already mapped to {existing.property.name}"
    
    # Find candidate properties by city
    candidates = Property.objects.filter(
        city__iexact=supplier_city
    )
    
    if not candidates.exists():
        OperationLog.objects.create(
            operation_type='mapping_decision',
            status='failed',
            details=str({
                'supplier_name': supplier_name,
                'external_id': external_id,
                'reason': 'city_no_candidates',
                'supplier_city': supplier_city,
            }),
            timestamp=timezone.now(),
        )
        return None, 0.0, f"No properties found in {supplier_city}"
    
    # Calculate scores for all candidates
    best_property = None
    best_score = 0.0
    best_reason = ""
    
    for candidate in candidates:
        confidence, reason = calculate_match_score(
            candidate,
            supplier_property_name,
            supplier_city,
            supplier_lat,
            supplier_lng
        )
        
        logger.debug(f"Candidate {candidate.name}: {reason}")
        
        if confidence > best_score:
            best_score = confidence
            best_property = candidate
            best_reason = reason
    
    # Determine action based on confidence
    if best_score < CONFIG['MIN_VIABLE_CONFIDENCE']:
        OperationLog.objects.create(
            operation_type='mapping_decision',
            status='failed',
            details=str({
                'supplier_name': supplier_name,
                'external_id': external_id,
                'status': 'rejected',
                'confidence': round(best_score, 2),
                'reason': best_reason,
            }),
            timestamp=timezone.now(),
        )
        return None, best_score, f"rejected: {best_reason}"
    
    if best_score < CONFIG['MANUAL_REVIEW_THRESHOLD']:
        OperationLog.objects.create(
            operation_type='mapping_decision',
            status='failed',
            details=str({
                'supplier_name': supplier_name,
                'external_id': external_id,
                'status': 'rejected',
                'confidence': round(best_score, 2),
                'reason': best_reason,
            }),
            timestamp=timezone.now(),
        )
        return best_property, best_score, f"rejected: {best_reason} (below threshold)"
    
    if CONFIG['MANUAL_REVIEW_THRESHOLD'] <= best_score < CONFIG['AUTO_MATCH_THRESHOLD']:
        status = "manual_review"
    else:  # best_score >= AUTO_MATCH_THRESHOLD
        status = "approved"
    
    logger.info(
        f"Match: {supplier_property_name} ({external_id}) -> "
        f"{best_property.name} | Score: {best_score:.2f} | Status: {status}"
    )

    OperationLog.objects.create(
        operation_type='mapping_decision',
        status='success',
        details=str({
            'supplier_name': supplier_name,
            'external_id': external_id,
            'status': status,
            'confidence': round(best_score, 2),
            'property_id': best_property.id if best_property else None,
        }),
        timestamp=timezone.now(),
    )
    
    return best_property, best_score, status


@transaction.atomic
def create_supplier_mapping(
    supplier_name: str,
    external_id: str,
    supplier_property_name: str,
    supplier_city: str,
    supplier_lat: Optional[float] = None,
    supplier_lng: Optional[float] = None,
    auto_approve_high_confidence: bool = True
) -> Tuple[SupplierPropertyMap, str, bool]:
    """
    Create a new supplier property mapping with validation.
    
    Returns:
        Tuple of:
        - mapping: SupplierPropertyMap object (created or for review)
        - status: 'created_approved', 'created_pending_review', 'rejected'
        - success: True if mapping created
    """
    
    # Step 1: Match supplier property to internal property
    matched_property, confidence, match_status = match_supplier_property(
        supplier_name=supplier_name,
        external_id=external_id,
        supplier_property_name=supplier_property_name,
        supplier_city=supplier_city,
        supplier_lat=supplier_lat,
        supplier_lng=supplier_lng,
    )
    
    if match_status.startswith('rejected'):
        logger.warning(f"Mapping rejected: {match_status}")
        return None, match_status, False
    
    # Step 2: Create mapping
    mapping = SupplierPropertyMap.objects.create(
        property=matched_property,
        supplier_name=supplier_name,
        external_id=external_id,
        supplier_property_name=supplier_property_name,
        supplier_city=supplier_city,
        supplier_lat=supplier_lat,
        supplier_lng=supplier_lng,
        confidence_score=confidence,
        verified=False
    )
    
    # Step 3: Auto-verify if high confidence and enabled
    if confidence >= CONFIG['AUTO_MATCH_THRESHOLD'] and auto_approve_high_confidence:
        mapping.verified = True
        mapping.save()
        return mapping, "created_approved", True
    
    return mapping, "created_pending_review", True


def get_or_create_supplier_mapping(
    supplier_name: str,
    external_id: str,
    **kwargs
) -> Tuple[SupplierPropertyMap, bool]:
    """
    Get existing mapping or create new one if not found.
    
    Returns:
        Tuple of (mapping, created)
    """
    try:
        mapping = SupplierPropertyMap.objects.get(
            supplier_name=supplier_name,
            external_id=external_id
        )
        return mapping, False
    except SupplierPropertyMap.DoesNotExist:
        mapping, status, success = create_supplier_mapping(
            supplier_name=supplier_name,
            external_id=external_id,
            **kwargs
        )
        return mapping, success