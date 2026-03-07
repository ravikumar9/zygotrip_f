# apps/hotels/indexes.py
"""
Database indexes for optimal filter query performance.

IMPLEMENTATION: Use Django's Meta.indexes for declarative index management.
All indexes are DB-agnostic and will be created/managed by migrations.

INDEX STRATEGY:
1. Single-field indexes on frequently filtered columns
2. Composite indexes for common filter combinations
3. Index selectivity: prioritize columns with high cardinality
4. Avoid over-indexing; only index columns that hit disk heavily
"""

from django.db import models


# ============================================================================
# INDEX DEFINITIONS (for Meta.indexes in models)
# ============================================================================

# Property model indexes
PropertyIndexes = [
    # Single-field indexes
    models.Index(fields=['city'], name='hotel_city_idx'),
    models.Index(fields=['locality'], name='hotel_locality_idx'),
    models.Index(fields=['rating'], name='hotel_rating_idx'),
    models.Index(fields=['property_type'], name='hotel_property_type_idx'),
    models.Index(fields=['created_at'], name='hotel_created_date_idx'),
    models.Index(fields=['is_trending'], name='hotel_trending_idx'),
    models.Index(fields=['has_free_cancellation'], name='hotel_free_cancel_idx'),
    
    # Composite indexes for common filter combinations
    models.Index(
        fields=['city', 'rating'],
        name='hotel_city_rating_idx'
    ),
    models.Index(
        fields=['city', 'property_type', 'rating'],
        name='hotel_city_type_rating_idx'
    ),
    models.Index(
        fields=['rating', '-created_at'],
        name='hotel_rating_date_idx'
    ),
    models.Index(
        fields=['bookings_this_week', '-rating'],
        name='hotel_popularity_idx'
    ),
]

# RoomType model indexes (for price filtering)
RoomTypeIndexes = [
    models.Index(fields=['property'], name='room_property_idx'),
    models.Index(fields=['base_price'], name='room_price_idx'),
    models.Index(fields=['property', 'base_price'], name='room_property_price_idx'),
]

# PropertyAmenityFilter indexes
PropertyAmenityFilterIndexes = [
    models.Index(fields=['property'], name='amenity_filter_property_idx'),
    models.Index(fields=['amenity'], name='amenity_filter_amenity_idx'),
    models.Index(fields=['property', 'amenity'], name='amenity_filter_compound_idx'),
]

# PropertyPaymentSupport indexes
PropertyPaymentSupportIndexes = [
    models.Index(fields=['property'], name='payment_property_idx'),
    models.Index(fields=['method'], name='payment_method_idx'),
    models.Index(fields=['is_enabled'], name='payment_enabled_idx'),
]

# PropertyCancellationPolicy indexes
PropertyCancellationPolicyIndexes = [
    models.Index(fields=['property'], name='cancel_property_idx'),
    models.Index(fields=['policy'], name='cancel_policy_idx'),
    models.Index(fields=['is_primary'], name='cancel_primary_idx'),
]

# PropertyBrandRelation indexes
PropertyBrandRelationIndexes = [
    models.Index(fields=['property'], name='brand_property_idx'),
    models.Index(fields=['brand'], name='brand_idx'),
    models.Index(fields=['confidence'], name='brand_confidence_idx'),
]

# RoomInventory indexes (for availability filtering)
RoomInventoryIndexes = [
    models.Index(fields=['room_type', 'date'], name='inventory_room_date_idx'),
    models.Index(fields=['date', 'available_count'], name='inventory_date_available_idx'),
    models.Index(fields=['room_type', 'date', 'available_count'], name='inventory_compound_idx'),
]


# ============================================================================
# SQL INDEX CREATION HELPERS
# ============================================================================

# Raw SQL statements for creating indexes (if needed outside migrations)
RAW_SQL_INDEXES = """
-- Property main filtering indexes
CREATE INDEX CONCURRENTLY idx_property_city ON hotels_property(city_id) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_property_rating ON hotels_property(rating DESC) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_property_city_rating ON hotels_property(city_id, rating DESC) WHERE is_active = true;

-- Room pricing indexes  
CREATE INDEX CONCURRENTLY idx_roomtype_price ON rooms_roomtype(base_price) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_roomtype_property_price ON rooms_roomtype(property_id, base_price) WHERE is_active = true;

-- Filter relationship indexes
CREATE INDEX CONCURRENTLY idx_amenity_filter_property ON hotels_propertyamenityfilter(property_id);
CREATE INDEX CONCURRENTLY idx_payment_method_property ON hotels_propertypaymentsupport(property_id, is_enabled);
CREATE INDEX CONCURRENTLY idx_cancel_policy_property ON hotels_propertycancellationpolicy(property_id, is_primary);
CREATE INDEX CONCURRENTLY idx_brand_property ON hotels_propertybrandrelation(property_id, confidence DESC);

-- Availability (room inventory) indexes
CREATE INDEX CONCURRENTLY idx_room_inventory_date ON rooms_roominventory(room_type_id, date);
CREATE INDEX CONCURRENTLY idx_room_inventory_available ON rooms_roominventory(date, available_count) WHERE available_count > 0;
"""


# ============================================================================
# MIGRATION HELPER CLASS
# ============================================================================

class IndexMigrationHelper:
    """
    Helper to generate migration code for indexes.
    
    USAGE: In a migration file, add these indexes:
    
        from apps.hotels.indexes import PropertyIndexes, RoomTypeIndexes
        ...
        operations = [
            migrations.AddIndex(model_name='property', index=PropertyIndexes[0]),
            ...
        ]
    """
    
    @staticmethod
    def get_property_indexes():
        """Get all Property model indexes"""
        return PropertyIndexes
    
    @staticmethod
    def get_room_indexes():
        """Get all RoomType model indexes"""
        return RoomTypeIndexes
    
    @staticmethod
    def get_filter_relationship_indexes():
        """Get all filter relationship model indexes"""
        return (
            PropertyAmenityFilterIndexes +
            PropertyPaymentSupportIndexes +
            PropertyCancellationPolicyIndexes +
            PropertyBrandRelationIndexes
        )
    
    @staticmethod
    def get_all_indexes():
        """Get all indexes"""
        return (
            PropertyIndexes +
            RoomTypeIndexes +
            PropertyAmenityFilterIndexes +
            PropertyPaymentSupportIndexes +
            PropertyCancellationPolicyIndexes +
            PropertyBrandRelationIndexes +
            RoomInventoryIndexes
        )