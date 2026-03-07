/**
 * Shared price formatting utility for INR currency.
 * Replaces duplicated `formatPrice` / `fmt` functions across:
 *   - HotelCard.tsx, PropertyCard.tsx, RoomSelector.tsx,
 *   - PriceBreakdown.tsx, [slug]/page.tsx
 */
export function formatPrice(price: number | string): string {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num || 0);
}

/**
 * Format a price with compact notation for large values.
 * e.g. ₹1,500 → "₹1.5K", ₹25,000 → "₹25K"
 */
export function formatPriceCompact(price: number | string): string {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (num >= 100_000) return `₹${(num / 100_000).toFixed(1)}L`;
  if (num >= 1_000) return `₹${(num / 1_000).toFixed(num % 1_000 === 0 ? 0 : 1)}K`;
  return formatPrice(num);
}
