"""
Supplier Adapter Classes for Real Channel Manager Integration
Handles real API connections to booking platforms and inventory reconciliation.
"""

import logging
import json
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import requests
from django.core.cache import cache
from django.utils import timezone
from apps.core.logging_service import OperationLogger

logger = logging.getLogger('zygotrip')


class SupplierAdapterBase(ABC):
    """Abstract base class for supplier adapters"""
    
    def __init__(self, supplier_id: str, api_key: str, cache_ttl: int = 3600):
        self.supplier_id = supplier_id
        self.api_key = api_key
        self.cache_ttl = cache_ttl
        self.request_timeout = 10
        self.last_sync_time = None
        self.last_sync_status = None
        
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with supplier API"""
        pass
    
    @abstractmethod
    def fetch_inventory(self, start_date: str, end_date: str) -> Dict:
        """Fetch inventory from supplier"""
        pass
    
    @abstractmethod
    def push_availability(self, availability_data: Dict) -> bool:
        """Push availability back to supplier"""
        pass
    
    @abstractmethod
    def fetch_rates(self, property_id: str) -> Dict:
        """Fetch rate information"""
        pass
    
    def _cache_key(self, operation: str, property_id: str) -> str:
        """Generate cache key"""
        return f"supplier_{self.supplier_id}_{operation}_{property_id}"
    
    def _get_cached(self, key: str):
        """Get from cache"""
        return cache.get(key)
    
    def _set_cached(self, key: str, value, ttl: Optional[int] = None):
        """Set cache with TTL"""
        cache.set(key, value, ttl or self.cache_ttl)
    
    def log_sync(self, property_id: str, status: str, details: Dict):
        """Log sync operation"""
        OperationLogger.log_operation(
            operation_type='inventory_sync',
            status=status,
            details={
                'supplier': self.supplier_id,
                'property_id': property_id,
                'timestamp': timezone.now().isoformat(),
                **details
            }
        )
        self.last_sync_status = status


class BookingComAdapter(SupplierAdapterBase):
    """Adapter for Booking.com API integration"""
    
    API_BASE = "https://api.booking.com/v2/"
    
    def authenticate(self) -> bool:
        """Verify API credentials with Booking.com"""
        try:
            # Test endpoint to verify API key
            response = requests.post(
                f"{self.API_BASE}authentication/oauth/token",
                json={"api_key": self.api_key},
                timeout=self.request_timeout
            )
            if response.status_code == 200:
                logger.info(f"Booking.com authentication successful for {self.supplier_id}")
                return True
            else:
                logger.error(f"Booking.com auth failed: {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"Booking.com connection error: {str(e)}")
            return False
    
    def fetch_inventory(self, start_date: str, end_date: str) -> Dict:
        """Fetch room availability from apps.booking.com"""
        cache_key = self._cache_key('inventory', start_date)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            response = requests.get(
                f"{self.API_BASE}properties/availability",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={
                    "date_from": start_date,
                    "date_to": end_date,
                },
                timeout=self.request_timeout
            )
            response.raise_for_status()
            data = response.json()
            self._set_cached(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Booking.com inventory fetch failed: {str(e)}")
            return {}
    
    def push_availability(self, availability_data: Dict) -> bool:
        """Push availability updates back to Booking.com"""
        try:
            response = requests.put(
                f"{self.API_BASE}properties/availability/push",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=availability_data,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            logger.info(f"Pushed availability to Booking.com: {availability_data.get('property_id')}")
            return True
        except Exception as e:
            logger.error(f"Booking.com push failed: {str(e)}")
            return False
    
    def fetch_rates(self, property_id: str) -> Dict:
        """Fetch current rates from apps.booking.com"""
        cache_key = self._cache_key('rates', property_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            response = requests.get(
                f"{self.API_BASE}properties/{property_id}/rates",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            rates = response.json()
            self._set_cached(cache_key, rates)
            return rates
        except Exception as e:
            logger.error(f"Booking.com rates fetch failed: {str(e)}")
            return {}


class AirbnbAdapter(SupplierAdapterBase):
    """Adapter for Airbnb API integration"""
    
    API_BASE = "https://api.airbnb.com/v2/"
    
    def authenticate(self) -> bool:
        """Verify API credentials with Airbnb"""
        try:
            response = requests.post(
                f"{self.API_BASE}authorize",
                json={"client_id": self.api_key},
                timeout=self.request_timeout
            )
            if response.status_code == 200:
                logger.info(f"Airbnb authentication successful for {self.supplier_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Airbnb auth error: {str(e)}")
            return False
    
    def fetch_inventory(self, start_date: str, end_date: str) -> Dict:
        """Fetch availability from Airbnb"""
        cache_key = self._cache_key('inventory', start_date)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            response = requests.get(
                f"{self.API_BASE}listings/availability",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"calendar_months": 3},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            data = response.json()
            self._set_cached(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Airbnb inventory fetch failed: {str(e)}")
            return {}
    
    def push_availability(self, availability_data: Dict) -> bool:
        """Push availability to Airbnb"""
        try:
            response = requests.post(
                f"{self.API_BASE}listings/availability/update",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=availability_data,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            logger.info(f"Pushed availability to Airbnb")
            return True
        except Exception as e:
            logger.error(f"Airbnb push failed: {str(e)}")
            return False
    
    def fetch_rates(self, property_id: str) -> Dict:
        """Fetch rates from Airbnb"""
        cache_key = self._cache_key('rates', property_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            response = requests.get(
                f"{self.API_BASE}listings/{property_id}/pricing",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            rates = response.json()
            self._set_cached(cache_key, rates)
            return rates
        except Exception as e:
            logger.error(f"Airbnb rates fetch failed: {str(e)}")
            return {}


class InventoryReconciliationEngine:
    """Reconciliation logic between supplier and local inventory"""
    
    MISMATCH_THRESHOLD = 0.05  # 5% difference tolerance
    
    def __init__(self):
        self.mismatches = []
        self.reconciliation_log = []
    
    def reconcile(self, supplier_inventory: Dict, local_inventory: Dict) -> Tuple[bool, List[Dict]]:
        """
        Compare supplier inventory with local inventory.
        Returns (all_match, list_of_mismatches)
        """
        mismatches = []
        
        for property_id, supplier_data in supplier_inventory.items():
            local_data = local_inventory.get(property_id, {})
            
            # Compare room counts
            supplier_rooms = supplier_data.get('available_rooms', 0)
            local_rooms = local_data.get('available_rooms', 0)
            
            if supplier_rooms == 0 and local_rooms == 0:
                continue  # Both empty, no mismatch
            
            # Calculate percentage difference
            diff_percent = abs(supplier_rooms - local_rooms) / max(supplier_rooms, local_rooms, 1)
            
            if diff_percent > self.MISMATCH_THRESHOLD:
                mismatch = {
                    'property_id': property_id,
                    'supplier_rooms': supplier_rooms,
                    'local_rooms': local_rooms,
                    'diff_percent': round(diff_percent * 100, 2),
                    'detected_at': timezone.now().isoformat(),
                }
                mismatches.append(mismatch)
                self.reconciliation_log.append(mismatch)
                
                logger.warning(f"Inventory mismatch: {property_id} - "
                             f"Supplier: {supplier_rooms}, Local: {local_rooms} "
                             f"({mismatch['diff_percent']}%)")
        
        self.mismatches = mismatches
        return len(mismatches) == 0, mismatches
    
    def auto_correct(self, mismatches: List[Dict], source_of_truth: str = 'supplier') -> List[Dict]:
        """
        Automatically correct inventory based on source of truth.
        source_of_truth: 'supplier' or 'local'
        """
        corrections = []
        
        for mismatch in mismatches:
            correction = {
                'property_id': mismatch['property_id'],
                'previous_value': mismatch['local_rooms'],
                'new_value': mismatch['supplier_rooms'],
                'action': 'sync_from_supplier' if source_of_truth == 'supplier' else 'keep_local',
                'timestamp': timezone.now().isoformat(),
            }
            
            if source_of_truth == 'supplier':
                # Update local to match supplier
                from apps.hotels.models import Property
                try:
                    prop = Property.objects.get(external_id=mismatch['property_id'])
                    prop.rooms_available = mismatch['supplier_rooms']
                    prop.save(update_fields=['rooms_available'])
                    correction['status'] = 'corrected'
                except Property.DoesNotExist:
                    correction['status'] = 'property_not_found'
            
            corrections.append(correction)
            logger.info(f"Corrected inventory for {mismatch['property_id']}: "
                       f"{mismatch['local_rooms']} → {mismatch['supplier_rooms']}")
        
        return corrections


class SupplierAdapterFactory:
    """Factory for creating supplier adapters"""
    
    _adapters = {
        'booking_com': BookingComAdapter,
        'airbnb': AirbnbAdapter,
        'expedia': None,  # Note: Implement Expedia adapter
        'agoda': None,    # Note: Implement Agoda adapter
    }
    
    @classmethod
    def create(cls, supplier_name: str, supplier_id: str, api_key: str) -> Optional[SupplierAdapterBase]:
        """Factory method to create adapter instances"""
        adapter_class = cls._adapters.get(supplier_name)
        if adapter_class:
            return adapter_class(supplier_id, api_key)
        else:
            logger.error(f"Unknown supplier: {supplier_name}")
            return None
    
    @classmethod
    def get_adapter_names(cls) -> List[str]:
        """Get list of available adapters"""
        return list(cls._adapters.keys())


def create_sync_report(property_id: str, sync_results: Dict) -> Dict:
    """Create detailed sync report for audit trail"""
    return {
        'property_id': property_id,
        'timestamp': timezone.now().isoformat(),
        'rooms_synced': sync_results.get('rooms_synced', 0),
        'prices_synced': sync_results.get('prices_synced', 0),
        'mismatches_found': sync_results.get('mismatches_found', 0),
        'mismatches_corrected': sync_results.get('mismatches_corrected', 0),
        'status': sync_results.get('status', 'unknown'),
        'raw_response': sync_results.get('raw_response', {}),
    }


