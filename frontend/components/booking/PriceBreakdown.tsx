'use client';
import { useState } from 'react';
import { Tag, ChevronDown, ChevronUp, BadgeCheck, Loader2, X } from 'lucide-react';
import { clsx } from 'clsx';
import type { BookingContext, PromoResult } from '@/types';
import { bookingsService } from '@/services/bookings';

// ── Accepts either a BookingContext (new) or individual fields (legacy) ──
type ContextMode = {
  context: BookingContext;
  promoCode?: string;
  onPromoChange?: (code: string) => void;
  className?: string;
};

type FieldsMode = {
  basePrice: string | number;
  propertyDiscount?: string | number;
  platformDiscount?: string | number;
  couponDiscount?: string | number;
  serviceFee: string | number;
  gst: string | number;
  finalPrice: string | number;
  gstPercent?: string;
  nights?: number;
  rooms?: number;
  className?: string;
};

type PriceBreakdownProps = ContextMode | FieldsMode;

function fmt(val: string | number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(val) || 0);
}

function LineItem({
  label, value, muted, highlight, className,
}: {
  label: string; value: string; muted?: boolean; highlight?: boolean; className?: string;
}) {
  return (
    <div className={clsx(
      'flex items-center justify-between text-sm',
      muted && 'text-neutral-500',
      highlight && 'text-green-700 font-medium',
      className
    )}>
      <span>{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

export default function PriceBreakdown(props: PriceBreakdownProps) {
  const [showCoupon, setShowCoupon] = useState(false);
  const [promoApplying, setPromoApplying] = useState(false);
  const [promoResult, setPromoResult] = useState<PromoResult | null>(null);
  const [promoInputError, setPromoInputError] = useState('');

  // ── Context mode ─────────────────────────────────────────────────
  if ('context' in props) {
    const { context, promoCode, onPromoChange, className } = props;

    const basePrice = Number(context.base_price) || 0;
    const propDiscount = Number(context.property_discount) || 0;
    const platDiscount = Number(context.platform_discount) || 0;
    const promoDiscount = Number(context.promo_discount) || 0;
    const tax = Number(context.tax) || 0;
    const serviceFee = Number(context.service_fee) || 0;
    const finalPrice = Number(context.final_price) || 0;
    const totalDiscount = propDiscount + platDiscount + promoDiscount;

    return (
      <div className={clsx('bg-white rounded-2xl shadow-card p-5', className)}>
        <h3 className="font-bold text-neutral-900 mb-1 font-heading">
          Price Breakdown
        </h3>
        <p className="text-xs text-neutral-400 mb-4">
          {context.nights} night{context.nights !== 1 ? 's' : ''} × {context.rooms} room{context.rooms !== 1 ? 's' : ''}
        </p>

        <div className="space-y-2.5">
          <LineItem label="Room charge" value={fmt(basePrice)} />

          {Number(context.meal_amount) > 0 && (
            <LineItem label="Meal plan" value={fmt(context.meal_amount)} />
          )}

          {propDiscount > 0 && (
            <LineItem label="Property discount" value={`-${fmt(propDiscount)}`} highlight />
          )}
          {platDiscount > 0 && (
            <LineItem label="Platform discount" value={`-${fmt(platDiscount)}`} highlight />
          )}
          {promoDiscount > 0 && (
            <LineItem label={`Promo (${context.promo_code || 'code'})`} value={`-${fmt(promoDiscount)}`} highlight />
          )}

          <div className="border-t border-neutral-100 pt-2">
            <LineItem label="Service fee" value={fmt(serviceFee)} muted />
            <LineItem label="GST & taxes" value={fmt(tax)} muted />
          </div>

          <div className="pt-2.5 border-t border-neutral-200 flex items-center justify-between">
            <span className="font-bold text-neutral-900">Total payable</span>
            <span className="font-black text-xl text-neutral-900">{fmt(finalPrice)}</span>
          </div>
        </div>

        {totalDiscount > 0 && (
          <div className="mt-3 bg-green-50 rounded-xl px-3 py-2 text-xs text-green-700 font-semibold text-center">
            🎉 You save {fmt(totalDiscount)} on this booking!
          </div>
        )}

        {/* Promo Code — fully functional */}
        {onPromoChange && (
          <div className="mt-4 pt-4 border-t border-neutral-100">
            {promoResult?.valid ? (
              <div className="promo-applied">
                <BadgeCheck size={14} className="shrink-0" />
                <span className="flex-1 text-xs font-semibold text-green-700">
                  {promoResult.promo_code} — {fmt(promoResult.discount_amount ?? 0)} off applied!
                </span>
                <button
                  onClick={() => { setPromoResult(null); onPromoChange(''); setPromoInputError(''); }}
                  className="text-green-500 hover:text-green-700 shrink-0"
                  aria-label="Remove promo"
                >
                  <X size={13} />
                </button>
              </div>
            ) : (
              <>
                <button
                  onClick={() => setShowCoupon(!showCoupon)}
                  className="flex items-center gap-2 text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
                >
                  <Tag size={14} />
                  Have a promo code?
                  {showCoupon ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
                {showCoupon && (
                  <div className="mt-2">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={promoCode ?? ''}
                        onChange={(e) => { onPromoChange(e.target.value.toUpperCase()); setPromoInputError(''); }}
                        onKeyDown={async (e) => {
                          if (e.key === 'Enter' && promoCode?.trim()) {
                            setPromoApplying(true);
                            setPromoInputError('');
                            try {
                              const res = await bookingsService.applyPromo({ promo_code: promoCode.trim(), base_amount: String(finalPrice) });
                              if (res.valid) setPromoResult(res as PromoResult);
                              else setPromoInputError('Invalid or expired promo code');
                            } catch { setPromoInputError('Could not validate. Try again.'); }
                            finally { setPromoApplying(false); }
                          }
                        }}
                        placeholder="Enter promo code"
                        className="flex-1 input-field text-sm uppercase font-mono tracking-wider"
                      />
                      <button
                        disabled={promoApplying || !promoCode?.trim()}
                        onClick={async () => {
                          if (!promoCode?.trim()) return;
                          setPromoApplying(true);
                          setPromoInputError('');
                          try {
                            const res = await bookingsService.applyPromo({ promo_code: promoCode.trim(), base_amount: String(finalPrice) });
                            if (res.valid) setPromoResult(res as PromoResult);
                            else setPromoInputError('Invalid or expired promo code');
                          } catch { setPromoInputError('Could not validate. Try again.'); }
                          finally { setPromoApplying(false); }
                        }}
                        className="btn-primary text-sm px-4 py-2 flex items-center gap-1 disabled:opacity-50"
                      >
                        {promoApplying ? <Loader2 size={13} className="animate-spin" /> : <Tag size={13} />}
                        Apply
                      </button>
                    </div>
                    {promoInputError && <p className="promo-error mt-1">{promoInputError}</p>}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  // ── Legacy fields mode ────────────────────────────────────────────
  const {
    basePrice, propertyDiscount = 0, platformDiscount = 0, couponDiscount = 0,
    serviceFee, gst, finalPrice, gstPercent, nights, rooms, className,
  } = props as FieldsMode;

  const totalDiscount = Number(propertyDiscount) + Number(platformDiscount) + Number(couponDiscount);

  return (
    <div className={clsx('bg-white rounded-xl border border-neutral-200 p-4', className)}>
      <h3 className="font-semibold text-neutral-900 mb-3">Price Breakdown</h3>

      {nights && rooms && (
        <p className="text-xs text-neutral-500 mb-3">
          {nights} night{nights > 1 ? 's' : ''} × {rooms} room{rooms > 1 ? 's' : ''}
        </p>
      )}

      <div className="space-y-2">
        <LineItem label="Room charge" value={fmt(basePrice)} />
        {totalDiscount > 0 && (
          <LineItem label="Total discount" value={`-${fmt(totalDiscount)}`} highlight />
        )}
        <LineItem label="Service fee" value={fmt(serviceFee)} muted />
        <LineItem label={`GST ${gstPercent ? `(${gstPercent}%)` : ''}`} value={fmt(gst)} muted />
        <div className="pt-2 border-t border-neutral-200 flex items-center justify-between">
          <span className="font-bold text-neutral-900">Total payable</span>
          <span className="font-bold text-xl text-neutral-900">{fmt(finalPrice)}</span>
        </div>
      </div>

      {totalDiscount > 0 && (
        <p className="mt-2 text-xs text-green-700 font-medium">🎉 You save {fmt(totalDiscount)}!</p>
      )}
    </div>
  );
}
