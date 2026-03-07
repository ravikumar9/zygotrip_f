'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Wallet, ArrowUpRight, ArrowDownLeft, Plus, TrendingUp, Clock, Shield } from 'lucide-react';
import { useWalletBalance, useWalletTransactions, useTopUp } from '@/hooks/useWallet';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import toast from 'react-hot-toast';
import { useAuth } from '@/contexts/AuthContext';

const TOP_UP_PRESETS = [500, 1000, 2000, 5000];

export default function WalletPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // Auth guard — wait for auth state, then redirect if unauthenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/account/login?next=/wallet');
    }
  }, [isAuthenticated, authLoading, router]);

  const { data: wallet, isLoading, error } = useWalletBalance();
  const { data: txData, fetchNextPage, hasNextPage } = useWalletTransactions();
  const topUp = useTopUp();

  // Redirect on API 401
  useEffect(() => {
    if ((error as any)?.response?.status === 401) {
      router.replace('/account/login?next=/wallet');
    }
  }, [error, router]);

  const [amount, setAmount] = useState('');
  const [showTopUp, setShowTopUp] = useState(false);

  const transactions = txData?.pages.flatMap(p => p.results) ?? [];

  const handleTopUp = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseFloat(amount);
    if (!amt || amt < 100) {
      toast.error('Minimum top-up amount is ₹100');
      return;
    }
    try {
      await topUp.mutateAsync({ amount: amt });
      toast.success(`₹${amt.toLocaleString('en-IN')} added to your wallet!`);
      setAmount('');
      setShowTopUp(false);
    } catch {
      toast.error('Top-up failed. Please try again.');
    }
  };

  // Show spinner while auth is resolving or wallet data is loading
  if (authLoading || isLoading) return <LoadingSpinner />;

  // If not authenticated after loading (should already be redirecting), render nothing
  if (!isAuthenticated) return null;

  return (
    <div className="page-booking-bg py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-2xl font-bold text-neutral-900 mb-8">My Wallet</h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Available Balance */}
          <div className="md:col-span-2 bg-gradient-to-br from-primary-600 to-primary-800 text-white rounded-2xl p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <p className="text-primary-200 text-sm mb-1">Available Balance</p>
                <p className="text-4xl font-bold">
                  ₹{parseFloat(wallet?.balance || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </p>
              </div>
              <div className="bg-white/20 p-3 rounded-xl">
                <Wallet className="w-6 h-6" />
              </div>
            </div>
            {wallet?.locked_balance && parseFloat(wallet.locked_balance) > 0 && (
              <div className="bg-white/10 rounded-xl px-3 py-2 text-sm">
                <span className="text-primary-200">Locked for booking: </span>
                <span className="font-semibold">₹{parseFloat(wallet.locked_balance).toLocaleString('en-IN')}</span>
              </div>
            )}
            <button
              onClick={() => setShowTopUp(true)}
              className="mt-4 bg-white text-primary-600 font-semibold px-5 py-2 rounded-xl text-sm hover:bg-primary-50 transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Money
            </button>
          </div>

          {/* Stats */}
          <div className="space-y-3">
            <div className="bg-white rounded-xl p-4 shadow-card">
              <div className="flex items-center gap-2 text-green-600 mb-1">
                <TrendingUp className="w-4 h-4" />
                <span className="text-xs font-medium uppercase tracking-wide">Total Added</span>
              </div>
              <p className="text-xl font-bold text-neutral-800">
                ₹{parseFloat(wallet?.total_balance || '0').toLocaleString('en-IN')}
              </p>
            </div>
            <div className="bg-white rounded-xl p-4 shadow-card">
              <div className="flex items-center gap-2 text-blue-600 mb-1">
                <Shield className="w-4 h-4" />
                <span className="text-xs font-medium uppercase tracking-wide">Secure &amp; Instant</span>
              </div>
              <p className="text-sm text-neutral-500">All transactions are encrypted and protected</p>
            </div>
          </div>
        </div>

        {/* Top-up modal */}
        {showTopUp && (
          <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
              <h3 className="text-lg font-bold text-neutral-900 mb-4">Add Money to Wallet</h3>
              <form onSubmit={handleTopUp} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-2">Amount (₹)</label>
                  <input
                    type="number"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    placeholder="Enter amount"
                    min="100"
                    max="100000"
                    className="input-field w-full"
                    required
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {TOP_UP_PRESETS.map(preset => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setAmount(String(preset))}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                        amount === String(preset)
                          ? 'bg-primary-600 text-white border-primary-600'
                          : 'border-neutral-200 text-neutral-700 hover:border-primary-400'
                      }`}
                    >
                      +₹{preset.toLocaleString('en-IN')}
                    </button>
                  ))}
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowTopUp(false)}
                    className="flex-1 btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={topUp.isPending}
                    className="flex-1 btn-primary disabled:opacity-50"
                  >
                    {topUp.isPending ? 'Processing...' : 'Add Money'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Transaction History */}
        <div className="bg-white rounded-2xl shadow-card">
          <div className="p-5 border-b border-neutral-100">
            <h2 className="text-lg font-semibold text-neutral-900">Transaction History</h2>
          </div>

          {transactions.length === 0 ? (
            <div className="py-16 text-center">
              <Wallet className="w-12 h-12 text-neutral-200 mx-auto mb-3" />
              <p className="text-neutral-500">No transactions yet</p>
              <p className="text-sm text-neutral-400">Add money to your wallet to get started</p>
            </div>
          ) : (
            <div className="divide-y divide-neutral-50">
              {transactions.map(tx => (
                <div key={tx.id} className="flex items-center gap-4 p-4 hover:bg-neutral-50 transition-colors">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                    tx.transaction_type === 'credit'
                      ? 'bg-green-100 text-green-600'
                      : 'bg-red-100 text-red-600'
                  }`}>
                    {tx.transaction_type === 'credit'
                      ? <ArrowDownLeft className="w-5 h-5" />
                      : <ArrowUpRight className="w-5 h-5" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-neutral-800 truncate">{tx.description || 'Transaction'}</p>
                    <div className="flex items-center gap-2 text-xs text-neutral-400">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(tx.created_at).toLocaleString('en-IN', {
                        day: '2-digit', month: 'short', year: 'numeric',
                        hour: '2-digit', minute: '2-digit'
                      })}</span>
                    </div>
                  </div>
                  <div className={`font-bold text-base shrink-0 ${
                    tx.transaction_type === 'credit' ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {tx.amount_display}
                  </div>
                </div>
              ))}
            </div>
          )}

          {hasNextPage && (
            <div className="p-4 border-t border-neutral-100 text-center">
              <button
                onClick={() => fetchNextPage()}
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                Load more transactions
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
