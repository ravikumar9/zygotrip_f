"""
Unified Search Engine Package
Consolidates all search operations for hotels, autocomplete, and advanced filtering.
"""

from .search_engine import UnifiedSearchEngine, search_engine
from .autocomplete_engine import AutocompleteEngine

__all__ = [
    'UnifiedSearchEngine',
    'search_engine',
    'AutocompleteEngine',
]


