'use client';
import { useState, useEffect, useRef } from 'react';
import { Tag, ChevronDown, BadgeCheck, Loader2, X, Info } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import type { BookingContext } from '@/types';
import { fetchFeaturedOffers } from '@/services/offers';
import { bookingsService } from '@/services/bookings';
import { analytics } from '@/lib/analytics';

/* ──────────────────────────────────────────────────────────────────
   TYPES
   ────────────────────────────────────────────────────────────────── */

type ContextMode = {
  context: BookingContext;
  promoCode?: string;
  onPromoChange?: (code: string) => void;
  walletDeduction?: number;
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

/* ──────────────────────────────────────────────────────────────────
   HELPERS
   ────────────────────────────────────────────────────────────────── */

function fmt(val: string | number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency: 'INR', maximumFractionDigits: 0,
  }).format(Number(val) || 0);
}

function LineItem({
  label, value, muted, highlight, green, className,
}: {
  label: string; value: string; muted?: boolean; highlight?: boolean; green?: boolean; className?: string;
}) {
  return (
    <div className={clsx(
      'flex items-center justify-between text-sm',
      muted && 'text-neutral-500',
      highlight && 'text-green-700 font-medium',
      green && 'text-green-600',
      className,
    )}>
      <span>{label}</span>
      <span className={clsx('font-medium', green && 'font-semibold')}>{value}</span>
    </div>
  );
}

/** Smooth collapsible wrapper */
function Collapsible({ open, children }: { open: boolean; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    if (ref.current) {
      // Add 4px buffer to prevent text clipping at the bottom
      setHeight(ref.current.scrollHeight + 4);
    }
  }, [open, children]);

  return (
    <div
      className="overflow-hidden transition-all duration-300 ease-in-out"
      style={{ maxHeight: open ? height : 0, opacity: open ? 1 : 0 }}
    >
      <div ref={ref}>{children}</div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════
   COMPONENT
   ══════════════════════════════════════════════════════════════════ */

export default function PriceBreakdown(props: PriceBreakdownProps) {
  const [promoOpen, setPromoOpen] = useState(false);
  const [taxOpen, setTaxOpen] = useState(false);
  const [promoApplying, setPromoApplying] = useState(false);
  const [promoInputError, setPromoInputError] = useState('');
  const [availableCoupons, setAvailableCoupons] = useState<Array<{
    code: string; description: string; discount_amount?: number; discount_percent?: number;
  }>>([]);
  const queryClient = useQueryClient();

  // Fetch coupons (only shown when promo section is opened)
  useEffect(() => {
    let cancelled = false;
    fetchFeaturedOffers().then(offers => {
      if (cancelled) return;
      setAvailableCoupons(offers
        .filter(o => o.coupon_code)
        .map(o => ({
          code: o.coupon_code,
          description: o.description || o.title,
          discount_percent: o.discount_percentage ? Number(o.discount_percentage) : undefined,
          discount_amount: o.discount_flat ? Number(o.discount_flat) : undefined,
        }))
      );
    }).catch(() => {
      if (!cancelled) {
        setAvailableCoupons([
          { code: 'ZYGO20', description: '20% off (up to ₹2,000)', discount_percent: 20 },
          { code: 'WALLET500', description: 'Save ₹500', discount_amount: 500 },
        ]);
      }
    });
    return () => { cancelled = true; };
  }, []);

  /* ═══ Context mode (primary) ═══════════════════════════════════ */
  if ('context' in props) {
    const { context, promoCode, onPromoChange, walletDeduction = 0, className } = props;

    const basePrice    = Number(context.base_price) || 0;
    const mealAmount   = Number(context.meal_amount) || 0;
    const propDiscount = Number(context.property_discount) || 0;
    const platDiscount = Number(context.platform_discount) || 0;
    const promoDiscount= Number(context.promo_discount) || 0;
    const tax          = Number(context.tax) || 0;
    const serviceFee   = Number(context.service_fee) || 0;
    const finalPrice   = Number(context.final_price) || 0;
    const totalDiscount= propDiscount + platDiscount + promoDiscount;
    const totalTaxes   = serviceFee + tax;

    const handleApplyPromo = async (code: string) => {
      if (!code.trim()) return;
      setPromoApplying(true);
      setPromoInputError('');
      try {
        await bookingsService.applyPromoToContext(context.uuid, code.trim());
        queryClient.invalidateQueries({ queryKey: ['booking-context', context.uuid] });
        analytics.track('coupon_applied', { coupon_code: code.trim(), context_uuid: context.uuid });
      } catch (err) {
        setPromoInputError(err instanceof Error ? err.message : 'Could not apply promo. Try again.');
        analytics.track('coupon_failed', { coupon_code: code.trim(), context_uuid: context.uuid });
      } finally {
        setPromoApplying(false);
      }
    };

    const handleRemovePromo = async () => {
      setPromoApplying(true);
      try {
        await bookingsService.applyPromoToContext(context.uuid, '');
        if (onPromoChange) onPromoChange('');
        queryClient.invalidateQueries({ queryKey: ['booking-context', context.uuid] });
        analytics.track('coupon_applied', { action: 'removed', context_uuid: context.uuid });
      } catch { /* silent */ }
      finally { setPromoApplying(false); }
    };

    return (
      <div className={clsx('bg-white rounded-2xl shadow-card p-5', className)}>
        <h3 className="font-bold text-neutral-900 mb-1 font-heading">Price Breakdown</h3>
        <p className="text-xs text-neutral-400 mb-4">
          {context.nights} night{context.nights !== 1 ? 's' : ''} × {context.rooms} room{context.rooms !== 1 ? 's' : ''}
        </p>

        <div className="space-y-2.5">
          {/* 1. Room price */}
          <LineItem label="Room charge" value={fmt(basePrice)} />

          {/* 2. Meal plan */}
          {mealAmount > 0 && <LineItem label="Meal plan" value={fmt(mealAmount)} />}

          {/* 3. Discounts (green) */}
          {propDiscount > 0 && (
            <LineItem label="Property discount" value={`-${fmt(propDiscount)}`} highlight green />
          )}
          {platDiscount > 0 && (
            <LineItem label="Platform discount" value={`-${fmt(platDiscount)}`} highlight green />
          )}
          {promoDiscount > 0 && (
            <LineItem label={`Promo (${context.promo_code || 'code'})`} value={`-${fmt(promoDiscount)}`} highlight green />
          )}

          {/* 4. Taxes & Fees — collapsible */}
          <div className="border-t border-neutral-100 pt-2">
            <button
              onClick={() => setTaxOpen(!taxOpen)}
              className="w-full flex items-center justify-between text-sm group"
            >
              <span className="flex items-center gap-1.5 text-neutral-600 font-medium">
                Taxes &amp; Fees
                <Info size={12} className="text-neutral-400 group-hover:text-neutral-600 transition-colors" />
              </span>
              <span className="flex items-center gap-1.5">
                <span className="font-medium text-neutral-700">{fmt(totalTaxes)}</span>
                <ChevronDown size={14} className={clsx(
                  'text-neutral-400 transition-transform duration-200',
                  taxOpen && 'rotate-180'
                )} />
              </span>
            </button>
            <Collapsible open={taxOpen}>
              <div className="mt-2 ml-2 space-y-2 border-l-2 border-neutral-100 pl-3 pb-1">
                <div className="flex items-center justify-between text-sm text-neutral-500">
                  <span className="whitespace-nowrap">Service fee</span>
                  <span className="font-medium tabular-nums">{fmt(serviceFee)}</span>
                </div>
                {tax > 0 ? (
                  <div className="flex items-center justify-between text-sm text-neutral-500">
                    <span className="whitespace-nowrap">GST</span>
                    <span className="font-medium tabular-nums">{fmt(tax)}</span>
                  </div>
                ) : (
                  <div className="flex items-center justify-between text-sm text-neutral-400">
                    <span className="whitespace-nowrap">GST</span>
                    <span className="font-medium tabular-nums text-green-600">Exempt</span>
                  </div>
                )}
              </div>
            </Collapsible>
          </div>

          {/* 5. Total */}
          <div className="pt-3 border-t-2 border-neutral-200 flex items-center justify-between">
            <span className="font-bold text-neutral-900">Total payable</span>
            <span className="font-black text-xl text-neutral-900">{fmt(finalPrice)}</span>
          </div>

          {/* Wallet deduction (if applicable) */}
          {walletDeduction > 0 && (
            <div className="space-y-2 pt-2">
              <LineItem label="Wallet deduction" value={`-${fmt(walletDeduction)}`} highlight green />
              <div className="pt-2 border-t border-dashed border-neutral-200 flex items-center justify-between">
                <span className="text-sm font-semibold text-neutral-700">Pay via Card/UPI</span>
                <span className="font-bold text-lg text-primary-700">{fmt(Math.max(0, finalPrice - walletDeduction))}</span>
              </div>
            </div>
          )}
        </div>

        {/* Savings banner */}
        {totalDiscount > 0 && (
          <div className="mt-3 bg-green-50 rounded-xl px-3 py-2 text-xs text-green-700 font-semibold text-center">
            🎉 You save {fmt(totalDiscount)} on this booking!
          </div>
        )}

        {/* ═══ Promo code section — collapsed by default ═══ */}
        {onPromoChange && (
          <div className="mt-4 pt-4 border-t border-neutral-100">
            {context.promo_code ? (
              /* ── Applied state ── */
              <div className="flex items-start gap-3 bg-green-50 border border-green-200 rounded-xl p-3 transition-all">
                <BadgeCheck size={16} className="text-green-600 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-green-800 font-mono tracking-wider">
                    {context.promo_code}
                  </p>
                  <p className="text-[11px] text-green-600 mt-0.5">
                    Discount: {fmt(promoDiscount)}
                  </p>
                </div>
                <button
                  onClick={handleRemovePromo}
                  disabled={promoApplying}
                  className="text-[11px] font-bold text-red-500 hover:text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 px-2.5 py-1 rounded-lg shrink-0 transition-colors disabled:opacity-50"
                  aria-label="Remove promo"
                >
                  {promoApplying ? <Loader2 size={11} className="animate-spin" /> : 'Remove'}
                </button>
              </div>
            ) : (
              /* ── Collapsed "Have a promo code?" ── */
              <>
                <button
                  onClick={() => {
                    const next = !promoOpen;
                    setPromoOpen(next);
                    if (next) analytics.track('cta_clicked', { element: 'promo_section_opened' });
                  }}
                  className="flex items-center gap-2 text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors w-full"
                >
                  <Tag size={14} />
                  <span className="flex-1 text-left">Have a promo code?</span>
                  <ChevronDown size={14} className={clsx(
                    'transition-transform duration-200',
                    promoOpen && 'rotate-180'
                  )} />
                </button>

                <Collapsible open={promoOpen}>
                  <div className="mt-3 space-y-3">
                    {/* Input + Apply */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={promoCode ?? ''}
                        onChange={(e) => { onPromoChange(e.target.value.toUpperCase()); setPromoInputError(''); }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && promoCode?.trim()) handleApplyPromo(promoCode);
                        }}
                        placeholder="Enter promo code"
                        className="flex-1 input-field text-sm uppercase font-mono tracking-wider"
                      />
                      <button
                        disabled={promoApplying || !promoCode?.trim()}
                        onClick={() => promoCode?.trim() && handleApplyPromo(promoCode)}
                        className="btn-primary text-sm px-4 py-2 flex items-center gap-1 disabled:opacity-50"
                      >
                        {promoApplying ? <Loader2 size={13} className="animate-spin" /> : <Tag size={13} />}
                        Apply
                      </button>
                    </div>
                    {promoInputError && (
                      <p className="text-[11px] text-red-600 font-medium">{promoInputError}</p>
                    )}

                    {/* Suggested coupons (only inside expanded section) */}
                    {availableCoupons.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[11px] text-neutral-400 font-semibold uppercase tracking-wider">Suggested coupons</p>
                        {availableCoupons.map(c => (
                          <div
                            key={c.code}
                            className="flex items-center justify-between gap-3 p-3 rounded-xl border border-dashed border-neutral-200 bg-neutral-50/50 hover:border-primary-200 transition-all"
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-bold text-neutral-800 font-mono tracking-wider">{c.code}</p>
                              <p className="text-[11px] text-neutral-500 truncate">{c.description}</p>
                            </div>
                            <button
                              onClick={() => {
                                if (onPromoChange) onPromoChange(c.code);
                                handleApplyPromo(c.code);
                              }}
                              disabled={promoApplying}
                              className="text-[11px] font-bold text-primary-600 hover:text-primary-700 bg-primary-50 hover:bg-primary-100 px-2.5 py-1 rounded-lg shrink-0 transition-colors"
                            >
                              Apply
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </Collapsible>
              </>
            )}
          </div>
        )}
      </div>
    );
  }

  /* ═══ Legacy fields mode ═══════════════════════════════════════ */
  const {
    basePrice, propertyDiscount = 0, platformDiscount = 0, couponDiscount = 0,
    serviceFee, gst, finalPrice, gstPercent, nights, rooms, className,
  } = props as FieldsMode;

  const totalDiscount = Number(propertyDiscount) + Number(platformDiscount) + Number(couponDiscount);
  const totalTaxes = Number(serviceFee) + Number(gst);

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
          <LineItem label="Total discount" value={`-${fmt(totalDiscount)}`} highlight green />
        )}

        {/* Collapsible taxes */}
        <button
          onClick={() => setTaxOpen(!taxOpen)}
          className="w-full flex items-center justify-between text-sm pt-2 border-t border-neutral-100"
        >
          <span className="flex items-center gap-1.5 text-neutral-500 font-medium">
            Taxes &amp; Fees
            <Info size={12} className="text-neutral-400" />
          </span>
          <span className="flex items-center gap-1.5">
            <span className="font-medium text-neutral-600">{fmt(totalTaxes)}</span>
            <ChevronDown size={14} className={clsx('text-neutral-400 transition-transform duration-200', taxOpen && 'rotate-180')} />
          </span>
        </button>
        <Collapsible open={taxOpen}>
          <div className="ml-2 space-y-1.5 border-l-2 border-neutral-100 pl-3 pb-1">
            <LineItem label="Service fee" value={fmt(serviceFee)} muted />
            {Number(gst) > 0 ? (
              <LineItem label="GST" value={fmt(gst)} muted />
            ) : (
              <div className="flex items-center justify-between text-sm text-neutral-400">
                <span>GST</span>
                <span className="font-medium text-green-600">Exempt</span>
              </div>
            )}
          </div>
        </Collapsible>

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
