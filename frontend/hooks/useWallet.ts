'use client';
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getWalletBalance, getWalletTransactions, topUpWallet, getOwnerWallet } from '@/services/wallet';

export function useWalletBalance() {
  return useQuery({
    queryKey: ['wallet-balance'],
    queryFn: getWalletBalance,
    staleTime: 5 * 60_000,
  });
}

export function useWalletTransactions() {
  return useInfiniteQuery({
    queryKey: ['wallet-transactions'],
    queryFn: ({ pageParam = 1 }) => getWalletTransactions(pageParam as number),
    initialPageParam: 1,
    getNextPageParam: (lastPage: any, pages) => {
      const total = lastPage.pagination?.total ?? 0;
      const perPage = lastPage.pagination?.per_page ?? 20;
      return pages.length * perPage < total ? pages.length + 1 : undefined;
    },
    staleTime: 60_000,
  });
}

export function useTopUp() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ amount, note }: { amount: number; note?: string }) =>
      topUpWallet(amount, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet-balance'] });
      queryClient.invalidateQueries({ queryKey: ['wallet-transactions'] });
    },
  });
}

export function useOwnerWallet() {
  return useQuery({
    queryKey: ['owner-wallet'],
    queryFn: getOwnerWallet,
    staleTime: 5 * 60_000,
  });
}
