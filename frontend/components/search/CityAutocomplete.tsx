'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { MapPin, Loader2 } from 'lucide-react';
import { fetchAutosuggest } from '@/services/apiClient';
import { useDebounce } from '@/hooks/useDebounce';

export interface SuggestionItem {
  type: 'city' | 'area' | 'property' | 'bus_city' | 'cab_city' | 'landmark';
  label: string;
  sublabel?: string;
  count?: number;
  slug?: string;
  id?: number | string | null;
}

interface CityAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onSelect?: (item: SuggestionItem) => void;
  placeholder?: string;
  /** Filter suggestions to only cities (default: true) */
  citiesOnly?: boolean;
  className?: string;
  icon?: React.ReactNode;
  name?: string;
  required?: boolean;
}

export default function CityAutocomplete({
  value,
  onChange,
  onSelect,
  placeholder = 'Search city or area...',
  citiesOnly = true,
  className = '',
  icon,
  name,
  required,
}: CityAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debouncedQuery = useDebounce(value, 250);

  // Fetch suggestions when debounced query changes
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);

    fetchAutosuggest(debouncedQuery, 8).then((items) => {
      if (cancelled) return;
      const filtered = citiesOnly
        ? items.filter((s) => ['city', 'area', 'bus_city', 'cab_city', 'landmark'].includes(s.type))
        : items;
      setSuggestions(filtered);
      setIsOpen(filtered.length > 0);
      setActiveIndex(-1);
      setIsLoading(false);
    });

    return () => { cancelled = true; };
  }, [debouncedQuery, citiesOnly]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = useCallback((item: SuggestionItem) => {
    onChange(item.label);
    setIsOpen(false);
    setSuggestions([]);
    onSelect?.(item);
  }, [onChange, onSelect]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < suggestions.length) {
          handleSelect(suggestions[activeIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setActiveIndex(-1);
        break;
    }
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case 'city': return '🏙️';
      case 'area': return '📍';
      case 'property': return '🏨';
      case 'bus_city': return '🚌';
      case 'cab_city': return '🚕';
      case 'landmark': return '🏛️';
      default: return '📌';
    }
  };

  return (
    <div ref={wrapperRef} className={`relative ${className}`}>
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none">
            {icon}
          </div>
        )}
        <input
          ref={inputRef}
          type="text"
          name={name}
          value={value}
          required={required}
          placeholder={placeholder}
          autoComplete="off"
          onChange={(e) => {
            onChange(e.target.value);
            if (e.target.value.length >= 2) setIsOpen(true);
          }}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          className={`w-full border border-neutral-200 rounded-xl py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent ${
            icon ? 'pl-10 pr-8' : 'pl-3 pr-8'
          }`}
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-haspopup="listbox"
        />
        {isLoading && (
          <Loader2 size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 animate-spin" />
        )}
      </div>

      {/* Suggestions dropdown */}
      {isOpen && suggestions.length > 0 && (
        <ul
          className="absolute z-50 left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-xl shadow-lg max-h-60 overflow-y-auto"
          role="listbox"
        >
          {suggestions.map((item, idx) => (
            <li
              key={`${item.type}-${item.label}-${idx}`}
              role="option"
              aria-selected={idx === activeIndex}
              className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors text-sm ${
                idx === activeIndex
                  ? 'bg-green-50 text-green-700'
                  : 'hover:bg-neutral-50 text-neutral-700'
              }`}
              onMouseEnter={() => setActiveIndex(idx)}
              onMouseDown={(e) => {
                e.preventDefault(); // prevent blur before click
                handleSelect(item);
              }}
            >
              <span className="text-base shrink-0">{typeIcon(item.type)}</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium truncate">{item.label}</p>
                {item.sublabel && (
                  <p className="text-xs text-neutral-400 truncate">{item.sublabel}</p>
                )}
              </div>
              {item.count != null && item.count > 0 && (
                <span className="text-xs text-neutral-400 shrink-0">
                  {item.count} {item.type === 'bus_city' ? 'routes' : item.type === 'cab_city' ? 'cabs' : 'properties'}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
