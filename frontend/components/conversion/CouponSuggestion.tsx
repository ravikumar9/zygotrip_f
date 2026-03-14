'use client';

import { BadgePercent, Sparkles, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import { useFormatPrice } from '@/hooks/useFormatPrice';

interface CouponSuggestion {
  code: string;
  description: string;
  discount_amount?: number;
  discount_percent?: number;
  max_discount?: number;
  min_order?: number;
}

interface CouponSuggestionCardProps {
  coupon: CouponSuggestion;
  onApply: (code: string) => void;
  isApplied?: boolean;
  isLoading?: boolean;
  className?: string;
}

/**
 * Auto-suggested coupon card — replaces manual coupon hunting.
 *
 * Usage:
 * <CouponSuggestionCard coupon={bestCoupon} onApply={handleApply} />
 */
export function CouponSuggestionCard({
  coupon,
  onApply,
  isApplied = false,
  isLoading = false,
  className,
}: CouponSuggestionCardProps) {
  const { formatPrice } = useFormatPrice();
  const savingsText = coupon.discount_amount
    ? `Save ${formatPrice(coupon.discount_amount)}`
    : coupon.discount_percent
      ? `${coupon.discount_percent}% off${coupon.max_discount ? ` (up to ${formatPrice(coupon.max_discount)})` : ''}`
      : coupon.description;

  return (
    <div
      className={clsx(
        'flex items-center gap-3 rounded-xl border-2 border-dashed px-4 py-3 transition-all',
        isApplied
          ? 'bg-green-50 border-green-300'
          : 'bg-white border-primary-200 hover:border-primary-400 hover:shadow-sm',
        className,
      )}
    >
      <div className={clsx(
        'flex items-center justify-center w-10 h-10 rounded-lg shrink-0',
        isApplied ? 'bg-green-100' : 'bg-primary-50',
      )}>
        {isApplied ? (
          <Sparkles className="w-5 h-5 text-green-600" />
        ) : (
          <BadgePercent className="w-5 h-5 text-primary-500" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-black text-xs tracking-wider text-neutral-800">
            {coupon.code}
          </span>
          {isApplied && (
            <span className="text-2xs font-bold text-green-600 bg-green-100 px-1.5 py-0.5 rounded-full">
              Applied
            </span>
          )}
        </div>
        <p className="text-2xs text-neutral-500 mt-0.5 truncate">{savingsText}</p>
      </div>

      {!isApplied && (
        <button
          onClick={() => onApply(coupon.code)}
          disabled={isLoading}
          className="shrink-0 text-primary-500 hover:text-primary-600 font-black text-xs flex items-center gap-0.5 disabled:opacity-50"
        >
          APPLY
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

interface SavingsSummaryProps {
  /** Total savings amount in INR */
  totalSavings: number;
  /** Breakdown items (e.g., "Coupon ZYGO20: ₹500", "Wallet: ₹150") */
  items?: { label: string; amount: number }[];
  className?: string;
}

/**
 * Savings celebration banner — reinforces "smart purchase" decision.
 *
 * Usage:
 * <SavingsSummary totalSavings={780} items={[{label: 'Coupon', amount: 500}, {label: 'Cashback', amount: 280}]} />
 */
export function SavingsSummary({ totalSavings, items, className }: SavingsSummaryProps) {
  const { formatPrice } = useFormatPrice();
  if (totalSavings <= 0) return null;

  return (
    <div className={clsx(
      'rounded-xl bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 p-4',
      className,
    )}>
      <div className="flex items-center gap-2 mb-1">
        <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-green-600" />
        </div>
        <div>
          <p className="text-xs text-green-600 font-bold">Total Savings</p>
          <p className="text-lg font-black text-green-700">{formatPrice(totalSavings)}</p>
        </div>
      </div>
      {items && items.length > 0 && (
        <div className="mt-2 pt-2 border-t border-green-200 space-y-1">
          {items.map((item) => (
            <div key={item.label} className="flex justify-between text-2xs text-green-600">
              <span>{item.label}</span>
              <span className="font-bold">-{formatPrice(item.amount)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
