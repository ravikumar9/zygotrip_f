import api from './api';
import type { ApiResponse, PaginatedData, WalletBalance, WalletTransaction, OwnerWallet } from '@/types';

export async function getWalletBalance(): Promise<WalletBalance> {
  const { data } = await api.get<ApiResponse<WalletBalance>>('/wallet/');
  if (!data.success) throw new Error('Failed to fetch wallet balance');
  return data.data;
}

export async function getWalletTransactions(page: number = 1) {
  const { data } = await api.get('/wallet/transactions/', { params: { page } });
  if (!data.success) throw new Error('Failed to fetch transactions');
  return data.data;
}

export async function initiateWalletTopup(amount: number, note?: string) {
  const { data } = await api.post('/wallet/topup/', { amount, note });
  if (!data.success) throw new Error(data?.error || 'Top-up failed');
  return data.data; // returns { order_id, payment_session_id, amount, cashfree_env }
}

export async function confirmWalletTopup(amount: number, orderId: string) {
  const { data } = await api.post('/wallet/topup/', {
    amount,
    order_id: orderId,
    payment_reference: orderId,
  });
  if (!data.success) throw new Error(data?.error || 'Verification failed');
  return data.data;
}

export async function getOwnerWallet(): Promise<OwnerWallet> {
  const { data } = await api.get<ApiResponse<OwnerWallet>>('/wallet/owner/');
  if (!data.success) throw new Error('Failed to fetch owner wallet');
  return data.data;
}
