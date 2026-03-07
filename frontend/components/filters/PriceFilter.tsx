'use client';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { clsx } from 'clsx';

const PRICE_BUCKETS = [
  { label: '₹0 – ₹1,000',   min: '',     max: '1000'  },
  { label: '₹1k – ₹2k',     min: '1000', max: '2000'  },
  { label: '₹2k – ₹3k',     min: '2000', max: '3000'  },
  { label: '₹3k – ₹5k',     min: '3000', max: '5000'  },
  { label: '₹5k – ₹10k',    min: '5000', max: '10000' },
  { label: '₹10,000+',       min: '10000', max: ''     },
];

interface PriceFilterProps {
  filterCounts?: Record<string, number>;
}

/**
 * OTA-grade price filter with Goibibo-style predefined buckets
 * plus custom min/max range inputs.
 */
export default function PriceFilter({ filterCounts }: PriceFilterProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentMin = searchParams.get('min_price') || '';
  const currentMax = searchParams.get('max_price') || '';

  const activeBucket = PRICE_BUCKETS.find(
    (b) => (b.min || '') === currentMin && (b.max || '') === currentMax
  );

  const updateParam = (key: string, value: string | null) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value === null || value === '') p.delete(key);
    else p.set(key, value);
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  const applyBucket = (min: string, max: string) => {
    const p = new URLSearchParams(searchParams.toString());
    if (min) p.set('min_price', min); else p.delete('min_price');
    if (max) p.set('max_price', max); else p.delete('max_price');
    p.delete('page');
    router.push(`${pathname}?${p.toString()}`);
  };

  return (
    <div className="mb-5 pb-5 border-b border-neutral-100">
      <h4 className="text-xs font-bold text-neutral-600 uppercase tracking-wider mb-3">
        Price per night
      </h4>
      <div className="space-y-1.5">
        {PRICE_BUCKETS.map((bucket) => {
          const active = activeBucket?.label === bucket.label;
          return (
            <label key={bucket.label} className="flex items-center gap-2.5 cursor-pointer group">
              <input
                type="radio"
                name="price_bucket"
                checked={active}
                onChange={() =>
                  active
                    ? (() => { updateParam('min_price', null); updateParam('max_price', null); })()
                    : applyBucket(bucket.min, bucket.max)
                }
                className="accent-primary-600"
              />
              <span className={clsx(
                'text-sm flex-1',
                active ? 'text-primary-700 font-semibold' : 'text-neutral-700 group-hover:text-neutral-900'
              )}>
                {bucket.label}
              </span>
            </label>
          );
        })}
      </div>
      {/* Custom range */}
      <div className="flex items-center gap-2 mt-3">
        <input
          type="number"
          placeholder="Min ₹"
          value={currentMin}
          onChange={(e) => updateParam('min_price', e.target.value || null)}
          className="w-full text-xs border border-neutral-200 rounded-lg px-2 py-1.5 outline-none focus:border-primary-400"
        />
        <span className="text-neutral-400 text-xs">—</span>
        <input
          type="number"
          placeholder="Max ₹"
          value={currentMax}
          onChange={(e) => updateParam('max_price', e.target.value || null)}
          className="w-full text-xs border border-neutral-200 rounded-lg px-2 py-1.5 outline-none focus:border-primary-400"
        />
      </div>
    </div>
  );
}
