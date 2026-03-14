'use client';

/**
 * useFormatPrice — hook that returns a currency-aware price formatter.
 *
 * All prices in the DB and API are in INR. This hook reads the user's
 * selected currency + exchange rates from CurrencyContext and returns
 * a `formatPrice(inrAmount)` function that converts + formats automatically.
 *
 * Usage:
 *   const { formatPrice } = useFormatPrice();
 *   <span>{formatPrice(hotel.min_price)}</span>
 *
 * This is the ONLY thing components need to change to support multi-currency.
 */

import { useCallback } from 'react';
import { useCurrency } from '@/contexts/CurrencyContext';
import {
  formatPrice as rawFormatPrice,
  formatPriceCompact as rawFormatPriceCompact,
} from '@/lib/formatPrice';

export function useFormatPrice() {
  const { currency, convert } = useCurrency();

  const formatPrice = useCallback(
    (price: number | string): string => {
      const num = typeof price === 'string' ? parseFloat(price) : price;
      if (!num && num !== 0) return rawFormatPrice(0, currency);
      // Convert from INR to selected currency, then format
      const converted = convert(num);
      return rawFormatPrice(converted, currency);
    },
    [currency, convert],
  );

  const formatPriceCompact = useCallback(
    (price: number | string): string => {
      const num = typeof price === 'string' ? parseFloat(price) : price;
      if (!num && num !== 0) return rawFormatPrice(0, currency);
      const converted = convert(num);
      return rawFormatPriceCompact(converted, currency);
    },
    [currency, convert],
  );

  return { formatPrice, formatPriceCompact, currency };
}
