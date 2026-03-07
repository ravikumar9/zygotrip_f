'use client';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { clsx } from 'clsx';

const DEFAULT_AMENITIES = ['WiFi', 'Pool', 'Parking', 'Gym', 'Spa', 'Restaurant', 'AC', 'Breakfast'];

interface AmenityFilterProps {
  amenities?: string[];
  filterCounts?: Record<string, number>;
}

/**
 * Amenity checkbox filter — URL-driven.
 * Supports multi-select via repeated `amenity` search params.
 */
export default function AmenityFilter({
  amenities = DEFAULT_AMENITIES,
  filterCounts,
}: AmenityFilterProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const toggleAmenity = (amenity: string) => {
    const p = new URLSearchParams(searchParams.toString());
    const existing = p.getAll('amenity').filter((a) => a !== amenity);
    p.delete('amenity');
    if (!p.getAll('amenity').includes(amenity) && !existing.includes(amenity)) {
      existing.push(amenity);
    }
    existing.forEach((a) => p.append('amenity', a));
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  return (
    <div className="mb-5 pb-5 border-b border-neutral-100">
      <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
        Amenities
      </h4>
      <div className="space-y-2">
        {amenities.map((amenity) => {
          const active = searchParams.getAll('amenity').includes(amenity);
          const cnt = filterCounts?.[amenity] ?? filterCounts?.[amenity.toLowerCase()];
          return (
            <label key={amenity} className="flex items-center gap-2.5 cursor-pointer group">
              <input
                type="checkbox"
                checked={active}
                onChange={() => toggleAmenity(amenity)}
                className="rounded border-neutral-300 text-primary-600 accent-primary-600"
              />
              <span className={clsx(
                'text-sm flex-1',
                active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900'
              )}>
                {amenity}
              </span>
              {cnt != null && (
                <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">{cnt}</span>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}
