'use client';

import { Wifi, Car, Waves, Dumbbell, Coffee, AirVent, Tv, UtensilsCrossed, ShowerHead, Wind, Baby, PawPrint, Cigarette, Shield, Clock, Package, ChevronDown, ChevronUp, Check } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useState } from 'react';

interface Amenity {
  id?: number | string;
  name: string;
  category?: string;
  icon?: string;
}

interface AmenityBreakdownProps {
  amenities: Amenity[];
  className?: string;
}

const AMENITY_ICONS: Record<string, LucideIcon> = {
  'wifi': Wifi,
  'free wifi': Wifi,
  'wi-fi': Wifi,
  'parking': Car,
  'free parking': Car,
  'car park': Car,
  'pool': Waves,
  'swimming pool': Waves,
  'gym': Dumbbell,
  'fitness': Dumbbell,
  'breakfast': Coffee,
  'restaurant': UtensilsCrossed,
  'food': UtensilsCrossed,
  'air conditioning': AirVent,
  'ac': AirVent,
  'a/c': AirVent,
  'tv': Tv,
  'television': Tv,
  'hot water': ShowerHead,
  'geyser': ShowerHead,
  'laundry': Wind,
  'washer': Wind,
  'kids': Baby,
  'children': Baby,
  'pet': PawPrint,
  'pets': PawPrint,
  'smoking': Cigarette,
  'safe': Shield,
  'locker': Shield,
  '24 hours': Clock,
  '24/7': Clock,
  'luggage': Package,
};

const AMENITY_CATEGORIES: Record<string, string[]> = {
  'Essentials': ['wifi', 'free wifi', 'wi-fi', 'air conditioning', 'ac', 'a/c', 'hot water', 'geyser', 'power backup'],
  'Food & Drink': ['breakfast', 'restaurant', 'bar', 'room service', 'kitchen', 'kitchenette', 'minibar', 'dining', 'cafe'],
  'Recreation': ['pool', 'swimming pool', 'gym', 'fitness', 'spa', 'jacuzzi', 'sauna', 'tennis', 'sports'],
  'Transport': ['parking', 'free parking', 'car park', 'airport transfer', 'shuttle', 'taxi', 'valet'],
  'Entertainment': ['tv', 'television', 'netflix', 'streaming', 'game room', 'casino'],
  'Services': ['24 hours', '24/7', 'concierge', 'laundry', 'washer', 'iron', 'dry cleaning', 'luggage', 'safe', 'locker'],
  'Family': ['kids', 'children', 'babysitting', 'crib', 'baby', 'family'],
  'Other': [],
};

function categorizeAmenity(name: string): string {
  const lowerName = name.toLowerCase();
  for (const [category, keywords] of Object.entries(AMENITY_CATEGORIES)) {
    if (category === 'Other') continue;
    if (keywords.some(kw => lowerName.includes(kw))) {
      return category;
    }
  }
  return 'Other';
}

function getAmenityIcon(name: string) {
  const lowerName = name.toLowerCase();
  for (const [key, Icon] of Object.entries(AMENITY_ICONS)) {
    if (lowerName.includes(key)) return Icon;
  }
  return Check;
}

export default function AmenityBreakdown({ amenities, className = '' }: AmenityBreakdownProps) {
  const [expanded, setExpanded] = useState(false);
  const INITIAL_SHOW = 12;

  if (!amenities || amenities.length === 0) return null;

  // Group amenities by category
  const grouped: Record<string, Amenity[]> = {};
  for (const amenity of amenities) {
    const cat = amenity.category || categorizeAmenity(amenity.name);
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(amenity);
  }

  // Order categories (Essentials first, Other last)
  const categoryOrder = ['Essentials', 'Food & Drink', 'Recreation', 'Transport', 'Entertainment', 'Services', 'Family', 'Other'];
  const sortedCategories = categoryOrder.filter(c => grouped[c] && grouped[c].length > 0);

  // Flatten for "show more" logic
  const allAmenities = amenities;
  const visibleAmenities = expanded ? allAmenities : allAmenities.slice(0, INITIAL_SHOW);
  const hasMore = allAmenities.length > INITIAL_SHOW;

  // Count shown amenities per category in current view
  const shownNames = new Set(visibleAmenities.map(a => a.name));

  return (
    <div className={`bg-white rounded-2xl shadow-card p-6 ${className}`}>
      <h3 className="text-lg font-bold text-neutral-900 font-heading mb-5">Amenities</h3>

      <div className="space-y-5">
        {sortedCategories.map(category => {
          const categoryAmenities = (grouped[category] || []).filter(a => shownNames.has(a.name));
          if (categoryAmenities.length === 0) return null;

          return (
            <div key={category}>
              <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2.5">{category}</h4>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {categoryAmenities.map(amenity => {
                  const Icon = getAmenityIcon(amenity.name);
                  return (
                    <div
                      key={amenity.id ?? amenity.name}
                      className="flex items-center gap-2.5 text-sm text-neutral-700 bg-neutral-50 rounded-lg px-3 py-2.5"
                    >
                      <Icon size={15} className="text-primary-500 shrink-0" />
                      <span className="truncate">{amenity.name}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-4 flex items-center gap-1.5 text-sm font-semibold text-primary-600 hover:text-primary-700 transition-colors"
        >
          {expanded ? (
            <><ChevronUp size={16} /> Show less</>
          ) : (
            <><ChevronDown size={16} /> Show all {allAmenities.length} amenities</>
          )}
        </button>
      )}
    </div>
  );
}
