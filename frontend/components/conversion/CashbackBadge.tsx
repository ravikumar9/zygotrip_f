'use client';

import { Wallet, Gift, Clock } from 'lucide-react';
import { clsx } from 'clsx';
import { useFormatPrice } from '@/hooks/useFormatPrice';

interface CashbackBadgeProps {
  /** Cashback amount in INR */
  amount: number;
  /** "Earn ₹X cashback" vs "₹X cashback credited" */
  variant?: 'earn' | 'credited' | 'expiring';
  /** Days until expiry (for expiring variant) */
  expiryDays?: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * Wallet cashback badge — drives repeat bookings via loyalty loop.
 *
 * Usage:
 * <CashbackBadge amount={200} variant="earn" />
 * <CashbackBadge amount={300} variant="credited" />
 * <CashbackBadge amount={400} variant="expiring" expiryDays={5} />
 */
export default function CashbackBadge({
  amount,
  variant = 'earn',
  expiryDays,
  size = 'sm',
  className,
}: CashbackBadgeProps) {
  const { formatPrice } = useFormatPrice();
  const formattedAmount = formatPrice(amount);

  const messages = {
    earn:     `Earn ${formattedAmount} cashback on this booking`,
    credited: `${formattedAmount} cashback credited to your wallet`,
    expiring: `${formattedAmount} wallet credits expiring in ${expiryDays} days`,
  };

  const colors = {
    earn:     'bg-emerald-50 text-emerald-700 border-emerald-200',
    credited: 'bg-blue-50 text-blue-700 border-blue-200',
    expiring: 'bg-amber-50 text-amber-800 border-amber-300',
  };

  const icons = {
    earn:     Gift,
    credited: Wallet,
    expiring: Clock,
  };

  const Icon = icons[variant];
  const isLg = size === 'lg';
  const isSm = size === 'sm';

  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg border font-semibold',
        colors[variant],
        isLg ? 'px-4 py-3 text-sm' : isSm ? 'px-2.5 py-1.5 text-2xs' : 'px-3 py-2 text-xs',
        variant === 'expiring' && 'animate-pulse-soft',
        className,
      )}
    >
      <Icon className={isLg ? 'w-5 h-5' : 'w-4 h-4'} />
      <span>{messages[variant]}</span>
    </div>
  );
}
