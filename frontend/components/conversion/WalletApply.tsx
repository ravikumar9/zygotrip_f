'use client';

import { Wallet, ChevronDown, ChevronUp, CheckCircle2, LogIn } from 'lucide-react';
import { useState } from 'react';
import { clsx } from 'clsx';
import Link from 'next/link';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import { useAuth } from '@/contexts/AuthContext';

interface WalletApplyProps {
  /** Available wallet balance in INR */
  balance: number;
  /** Total payable amount */
  totalAmount: number;
  /** Whether wallet is currently applied */
  isApplied: boolean;
  /** Callback when user toggles wallet usage */
  onToggle: (applied: boolean) => void;
  className?: string;
}

/**
 * Wallet balance applier for checkout — shows balance and
 * allows one-click apply to reduce payable amount.
 * Only available for authenticated users; guests see a login prompt.
 *
 * Usage:
 * <WalletApply balance={150} totalAmount={2500} isApplied={walletApplied} onToggle={setWalletApplied} />
 */
export default function WalletApply({
  balance,
  totalAmount,
  isApplied,
  onToggle,
  className,
}: WalletApplyProps) {
  const { formatPrice } = useFormatPrice();
  const { isAuthenticated } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const applicableAmount = Math.min(balance, totalAmount);
  const remainingPayable = totalAmount - (isApplied ? applicableAmount : 0);

  /* ── Guest users: show login prompt instead of wallet ── */
  if (!isAuthenticated) {
    return (
      <div className={clsx(
        'rounded-xl border border-neutral-200 bg-page p-4',
        className,
      )}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 bg-neutral-100">
            <Wallet className="w-5 h-5 text-neutral-400" />
          </div>
          <div className="flex-1">
            <span className="font-bold text-sm text-neutral-500">ZygoWallet</span>
            <p className="text-2xs text-neutral-400">Login to use your wallet balance</p>
          </div>
          <Link
            href="/accounts/login"
            className="flex items-center gap-1.5 text-xs font-bold text-primary-600 hover:text-primary-700 bg-primary-50 hover:bg-primary-100 px-3 py-1.5 rounded-lg transition-colors"
          >
            <LogIn size={12} />
            Login
          </Link>
        </div>
      </div>
    );
  }

  if (balance <= 0) return null;

  return (
    <div className={clsx(
      'rounded-xl border transition-all',
      isApplied ? 'bg-emerald-50 border-emerald-300' : 'bg-white/80 border-neutral-200',
      className,
    )}>
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4"
      >
        <div className={clsx(
          'w-10 h-10 rounded-lg flex items-center justify-center shrink-0',
          isApplied ? 'bg-emerald-100' : 'bg-primary-50',
        )}>
          <Wallet className={clsx('w-5 h-5', isApplied ? 'text-emerald-600' : 'text-primary-500')} />
        </div>

        <div className="flex-1 text-left">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-neutral-800">ZygoWallet</span>
            {isApplied && (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            )}
          </div>
          <p className="text-2xs text-neutral-500">
            Balance: {formatPrice(balance)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {!isApplied && (
            <span className="text-xs font-bold text-primary-500">
              Use {formatPrice(applicableAmount)}
            </span>
          )}
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-neutral-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-neutral-400" />
          )}
        </div>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 pt-0 border-t border-neutral-100 animate-slide-down">
          <div className="space-y-2 mt-3">
            <div className="flex justify-between text-xs">
              <span className="text-neutral-500">Wallet Balance</span>
              <span className="font-bold">{formatPrice(balance)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-neutral-500">Applicable Amount</span>
              <span className="font-bold text-emerald-600">-{formatPrice(applicableAmount)}</span>
            </div>
            {isApplied && (
              <div className="flex justify-between text-xs pt-1 border-t border-neutral-100">
                <span className="text-neutral-500">Remaining to Pay</span>
                <span className="font-black">{formatPrice(remainingPayable)}</span>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => onToggle(!isApplied)}
            className={clsx(
              'w-full mt-3 py-2 rounded-lg text-xs font-bold transition-colors',
              isApplied
                ? 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                : 'bg-primary-500 text-white hover:bg-primary-600',
            )}
          >
            {isApplied ? 'Remove Wallet' : `Apply ${formatPrice(applicableAmount)}`}
          </button>
        </div>
      )}

      {/* Collapsed applied state */}
      {isApplied && !expanded && (
        <div className="px-4 pb-3 pt-0">
          <p className="text-2xs text-emerald-600 font-semibold">
            {formatPrice(applicableAmount)} wallet balance applied · Pay {formatPrice(remainingPayable)}
          </p>
        </div>
      )}
    </div>
  );
}
