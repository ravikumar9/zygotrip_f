import api from './api';
import type { ApiResponse, PaginatedData, WalletBalance, WalletTransaction, OwnerWallet } from '@/types';

export async function getWalletBalance(): Promise<WalletBalance> {
  const { data } = await api.get<ApiResponse<WalletBalance>>('/wallet/');
  if (!data.success) throw new Error('Failed to fetch wallet balance');
  return data.data;
}

export async function getWalletTransactions(page: number = 1): Promise<{
  results: WalletTransaction[];
  pagination: PaginatedData<WalletTransaction>['pagination'];
}> {
  const { data } = await api.get('/wallet/transactions/', { params: { page } });
  if (!data.success) throw new Error('Failed to fetch transactions');
  return data.data;
}

export async function topUpWallet(amount: number, note?: string): Promise<{
  transaction_uid: string;
  amount_credited: string;
  new_balance: string;
  currency: string;
}> {
  const { data } = await api.post('/wallet/topup/', { amount, note });
  if (!data.success) throw new Error('Top-up failed');
  return data.data;
}

export async function getOwnerWallet(): Promise<OwnerWallet> {
  const { data } = await api.get<ApiResponse<OwnerWallet>>('/wallet/owner/');
  if (!data.success) throw new Error('Failed to fetch owner wallet');
  return data.data;
}
