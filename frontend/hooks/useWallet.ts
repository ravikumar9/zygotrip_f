'use client';
import { useQuery, useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { getWalletBalance, getWalletTransactions, getOwnerWallet } from '@/services/wallet';

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



export function useOwnerWallet() {
  return useQuery({
    queryKey: ['owner-wallet'],
    queryFn: getOwnerWallet,
    staleTime: 5 * 60_000,
  });
}
