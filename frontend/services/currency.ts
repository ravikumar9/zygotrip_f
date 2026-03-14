/**
 * Currency API client — multi-currency support for global OTA.
 *
 * Endpoints:
 *   GET /api/v1/currency/rates/?base=INR
 *   GET /api/v1/currency/convert/?amount=1000&from=INR&to=USD
 *   GET /api/v1/currency/supported/
 *   GET /api/v1/currency/detect/
 */

import apiClient from './apiClient';

export interface SupportedCurrency {
  code: string;
  name: string;
  symbol: string;
}

export interface ConversionResult {
  amount: number;
  from_currency: string;
  to_currency: string;
  converted_amount: number;
  formatted: string;
  original_formatted: string;
}

export interface ExchangeRates {
  base: string;
  rates: Record<string, number>;
  supported_currencies: SupportedCurrency[];
}

/** Fetch exchange rates for a base currency */
export async function fetchExchangeRates(base = 'INR'): Promise<ExchangeRates | null> {
  try {
    const { data } = await apiClient.get('/currency/rates/', { params: { base } });
    return data;
  } catch {
    return null;
  }
}

/** Convert an amount from one currency to another */
export async function convertCurrency(
  amount: number,
  from: string,
  to: string,
): Promise<ConversionResult | null> {
  try {
    const { data } = await apiClient.get('/currency/convert/', {
      params: { amount, from, to },
    });
    return data;
  } catch {
    return null;
  }
}

/** Get list of supported currencies */
export async function fetchSupportedCurrencies(): Promise<SupportedCurrency[]> {
  try {
    const { data } = await apiClient.get('/currency/supported/');
    return data?.currencies ?? [];
  } catch {
    return [];
  }
}

/** Auto-detect user's preferred currency */
export async function detectUserCurrency(
  country?: string,
  locale?: string,
): Promise<string> {
  try {
    const { data } = await apiClient.get('/currency/detect/', {
      params: { country, locale },
    });
    return data?.currency ?? 'INR';
  } catch {
    return 'INR';
  }
}
