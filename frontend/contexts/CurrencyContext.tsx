'use client';

/**
 * CurrencyContext — provides multi-currency conversion across the app.
 *
 * Wrap your layout with <CurrencyProvider> and use useCurrency() hook anywhere
 * to convert/format prices in the user's preferred currency.
 */

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import {
  fetchExchangeRates,
  fetchSupportedCurrencies,
  detectUserCurrency,
  type SupportedCurrency,
} from '../services/currency';

interface CurrencyContextValue {
  /** Currently selected currency code, e.g. "USD" */
  currency: string;
  /** Switch the active currency */
  setCurrency: (code: string) => void;
  /** Convert an INR amount to the user's selected currency */
  convert: (amountInr: number) => number;
  /** Format a price in the current currency (e.g. "$120.00") */
  format: (amountInr: number) => string;
  /** List of supported currencies for the picker */
  currencies: SupportedCurrency[];
  /** Whether rates are still loading */
  loading: boolean;
}

const CurrencyContext = createContext<CurrencyContextValue>({
  currency: 'INR',
  setCurrency: () => {},
  convert: (a) => a,
  format: (a) => `₹${a.toLocaleString('en-IN')}`,
  currencies: [],
  loading: true,
});

// Currency symbols for formatting
const SYMBOLS: Record<string, string> = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£', AED: 'د.إ',
  SGD: 'S$', THB: '฿', MYR: 'RM', AUD: 'A$', CAD: 'C$',
  JPY: '¥', KRW: '₩', SAR: '﷼', QAR: 'ر.ق', BDT: '৳',
  LKR: 'Rs', NPR: 'रू',
};

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [currency, setCurrencyState] = useState('INR');
  const [rates, setRates] = useState<Record<string, number>>({});
  const [currencies, setCurrencies] = useState<SupportedCurrency[]>([]);
  const [loading, setLoading] = useState(true);

  // Load rates + supported currencies on mount
  useEffect(() => {
    let mounted = true;
    async function init() {
      const [ratesData, currList, detected] = await Promise.all([
        fetchExchangeRates('INR'),
        fetchSupportedCurrencies(),
        detectUserCurrency(undefined, navigator?.language),
      ]);
      if (!mounted) return;
      if (ratesData?.rates) setRates(ratesData.rates);
      if (currList.length) setCurrencies(currList);

      // Restore preference from localStorage, or use detected
      const saved = localStorage.getItem('zygo_currency');
      if (saved) {
        setCurrencyState(saved);
      } else if (detected && detected !== 'INR') {
        setCurrencyState(detected);
      }
      setLoading(false);
    }
    init();
    return () => { mounted = false; };
  }, []);

  const setCurrency = useCallback((code: string) => {
    setCurrencyState(code);
    localStorage.setItem('zygo_currency', code);
  }, []);

  const convert = useCallback(
    (amountInr: number): number => {
      if (currency === 'INR' || !rates[currency]) return amountInr;
      return amountInr * rates[currency];
    },
    [currency, rates],
  );

  const format = useCallback(
    (amountInr: number): string => {
      const converted = currency === 'INR' ? amountInr : amountInr * (rates[currency] || 1);
      const symbol = SYMBOLS[currency] || currency;
      // Use appropriate locale for formatting
      if (currency === 'INR') {
        return new Intl.NumberFormat('en-IN', {
          style: 'currency',
          currency: 'INR',
          maximumFractionDigits: 0,
        }).format(converted);
      }
      if (currency === 'JPY' || currency === 'KRW') {
        return `${symbol}${Math.round(converted).toLocaleString()}`;
      }
      return `${symbol}${converted.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
    },
    [currency, rates],
  );

  const value = useMemo(
    () => ({ currency, setCurrency, convert, format, currencies, loading }),
    [currency, setCurrency, convert, format, currencies, loading],
  );

  return (
    <CurrencyContext.Provider value={value}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency() {
  return useContext(CurrencyContext);
}
