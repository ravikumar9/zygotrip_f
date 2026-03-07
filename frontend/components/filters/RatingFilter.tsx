'use client';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { clsx } from 'clsx';

const STAR_OPTIONS = [5, 4, 3, 2];
const GUEST_RATING_OPTIONS = [
  { value: '4.5', label: '4.5+ Exceptional', countKey: 'rating_4_5plus' },
  { value: '4',   label: '4.0+ Very Good',   countKey: 'rating_4_0plus' },
  { value: '3.5', label: '3.5+ Good',         countKey: 'rating_3_5plus' },
];

interface RatingFilterProps {
  /** Backend-computed filter counts */
  filterCounts?: {
    ratings?: Record<string, number>;
    user_ratings?: Record<string, number>;
  };
}

/**
 * Combined star rating + guest rating filter.
 * URL-driven — reads/writes searchParams directly.
 */
export default function RatingFilter({ filterCounts }: RatingFilterProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const updateParam = (key: string, value: string | null) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value === null || value === '') p.delete(key);
    else p.set(key, value);
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  return (
    <>
      {/* Star Rating */}
      <div className="mb-5 pb-5 border-b border-neutral-100">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
          Star Rating
        </h4>
        <div className="space-y-2">
          {STAR_OPTIONS.map((stars) => {
            const active = searchParams.get('stars') === String(stars);
            const countKey = stars === 5 ? 'rating_5' : `rating_${stars}plus`;
            const cnt = filterCounts?.ratings?.[countKey];
            return (
              <label key={stars} className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => updateParam('stars', active ? null : String(stars))}
                  className="rounded border-neutral-300 accent-primary-600"
                />
                <span className="text-sm text-neutral-700 flex-1">
                  {'★'.repeat(stars)}{stars === 5 ? ' Luxury' : ''}
                </span>
                {cnt != null && (
                  <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">{cnt}</span>
                )}
              </label>
            );
          })}
        </div>
      </div>

      {/* Guest Rating */}
      <div className="mb-5 pb-5 border-b border-neutral-100">
        <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
          Guest Rating
        </h4>
        <div className="space-y-2">
          {GUEST_RATING_OPTIONS.map(({ value, label, countKey }) => {
            const active = searchParams.get('user_rating') === value;
            const cnt = filterCounts?.user_ratings?.[countKey];
            return (
              <label key={value} className="flex items-center gap-2.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => updateParam('user_rating', active ? null : value)}
                  className="rounded border-neutral-300 accent-primary-600"
                />
                <span className={clsx(
                  'text-sm flex-1',
                  active ? 'text-primary-700 font-semibold' : 'text-neutral-700'
                )}>
                  {label}
                </span>
                {cnt != null && (
                  <span className="ml-auto text-xs text-neutral-400 font-medium tabular-nums">{cnt}</span>
                )}
              </label>
            );
          })}
        </div>
      </div>
    </>
  );
}
