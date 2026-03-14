'use client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from '@/contexts/AuthContext';
import { CurrencyProvider } from '@/contexts/CurrencyContext';

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  }));

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <CurrencyProvider>
          {children}
        </CurrencyProvider>
      </AuthProvider>
      <Toaster
        position="top-center"
        toastOptions={{
          duration: 6000,
          style: {
            background: '#1e293b',
            color: '#f1f5f9',
            fontSize: '14px',
            borderRadius: '12px',
            padding: '14px 20px',
            maxWidth: '480px',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#fff' } },
          error: { duration: 8000, iconTheme: { primary: '#ef4444', secondary: '#fff' } },
        }}
      />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
