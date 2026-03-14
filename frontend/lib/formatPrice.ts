/**
 * Shared price formatting utility.
 * Supports multi-currency via optional currency parameter.
 * Default: INR (backward-compatible with existing code).
 */

const SYMBOLS: Record<string, string> = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£', AED: 'د.إ',
  SGD: 'S$', THB: '฿', MYR: 'RM', AUD: 'A$', CAD: 'C$',
  JPY: '¥', KRW: '₩', SAR: '﷼', QAR: 'ر.ق', BDT: '৳',
  LKR: 'Rs', NPR: 'रू',
};

export function formatPrice(price: number | string, currency: string = 'INR'): string {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (currency === 'INR') {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(num || 0);
  }
  // Zero-decimal currencies
  if (currency === 'JPY' || currency === 'KRW') {
    const symbol = SYMBOLS[currency] || currency;
    return `${symbol}${Math.round(num || 0).toLocaleString()}`;
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(num || 0);
  } catch {
    const symbol = SYMBOLS[currency] || currency + ' ';
    return `${symbol}${(num || 0).toFixed(2)}`;
  }
}

/**
 * Format a price with compact notation for large values.
 * e.g. ₹1,500 → "₹1.5K", ₹25,000 → "₹25K"
 */
export function formatPriceCompact(price: number | string, currency: string = 'INR'): string {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  const symbol = SYMBOLS[currency] || currency + ' ';
  if (currency === 'INR') {
    if (num >= 100_000) return `₹${(num / 100_000).toFixed(1)}L`;
    if (num >= 1_000) return `₹${(num / 1_000).toFixed(num % 1_000 === 0 ? 0 : 1)}K`;
    return formatPrice(num, 'INR');
  }
  if (num >= 1_000_000) return `${symbol}${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${symbol}${(num / 1_000).toFixed(num % 1_000 === 0 ? 0 : 1)}K`;
  return formatPrice(num, currency);
}
