'use client';

import { Shield, MapPin, CreditCard, RefreshCcw, Clock } from 'lucide-react';
import { clsx } from 'clsx';

type TrustSignalType =
  | 'free-cancellation'
  | 'pay-at-hotel'
  | 'instant-confirmation'
  | 'secure-payment'
  | 'best-price';

interface TrustSignalProps {
  type: TrustSignalType;
  size?: 'sm' | 'md';
  className?: string;
}

const CONFIG: Record<TrustSignalType, { icon: typeof Shield; label: string; color: string }> = {
  'free-cancellation':    { icon: RefreshCcw, label: 'Free Cancellation',     color: 'text-green-600' },
  'pay-at-hotel':         { icon: MapPin,     label: 'Pay at Hotel',          color: 'text-blue-600' },
  'instant-confirmation': { icon: Clock,      label: 'Instant Confirmation',  color: 'text-purple-600' },
  'secure-payment':       { icon: Shield,     label: 'Secure Payment',        color: 'text-emerald-600' },
  'best-price':           { icon: CreditCard, label: 'Best Price Guarantee',  color: 'text-orange-600' },
};

/**
 * OTA trust signal — builds confidence and reduces drop-off.
 *
 * Usage:
 * <TrustSignal type="free-cancellation" />
 * <TrustSignal type="pay-at-hotel" size="md" />
 */
export default function TrustSignal({ type, size = 'sm', className }: TrustSignalProps) {
  const { icon: Icon, label, color } = CONFIG[type];
  const isSm = size === 'sm';

  return (
    <span className={clsx('inline-flex items-center gap-1 font-semibold', color, isSm ? 'text-2xs' : 'text-xs', className)}>
      <Icon className={isSm ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      {label}
    </span>
  );
}
