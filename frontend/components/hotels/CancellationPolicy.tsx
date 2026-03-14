'use client';

import { Shield, AlertTriangle, XCircle, Clock, Check, Info } from 'lucide-react';

interface CancellationTier {
  hours_before: number;
  refund_percent: number;
}

interface CancellationPolicyProps {
  type: 'free' | 'moderate' | 'strict' | 'non_refundable' | 'custom';
  tiers?: CancellationTier[];
  checkinDate?: string;
}

const POLICY_CONFIG = {
  free: {
    icon: Shield,
    color: 'text-green-600',
    bg: 'bg-green-50',
    border: 'border-green-200',
    label: 'Free Cancellation',
    description: 'Full refund if cancelled before check-in',
  },
  moderate: {
    icon: Clock,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    label: 'Moderate Cancellation',
    description: 'Free cancellation up to 48 hours before check-in',
  },
  strict: {
    icon: AlertTriangle,
    color: 'text-orange-600',
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    label: 'Strict Cancellation',
    description: 'Partial refund available with early cancellation',
  },
  non_refundable: {
    icon: XCircle,
    color: 'text-red-600',
    bg: 'bg-red-50',
    border: 'border-red-200',
    label: 'Non-Refundable',
    description: 'This booking cannot be cancelled for a refund',
  },
  custom: {
    icon: Info,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    label: 'Custom Policy',
    description: 'Refund depends on when you cancel',
  },
};

function formatHours(hours: number): string {
  if (hours >= 72) return `${Math.floor(hours / 24)} days`;
  if (hours >= 24) return `${Math.floor(hours / 24)} day${hours >= 48 ? 's' : ''}`;
  return `${hours} hours`;
}

export default function CancellationPolicyDisplay({ type, tiers, checkinDate }: CancellationPolicyProps) {
  const config = POLICY_CONFIG[type] || POLICY_CONFIG.custom;
  const Icon = config.icon;

  // Sort tiers descending by hours
  const sortedTiers = tiers ? [...tiers].sort((a, b) => b.hours_before - a.hours_before) : [];

  return (
    <div className={`rounded-xl p-4 border ${config.bg} ${config.border}`}>
      <div className="flex items-start gap-3 mb-3">
        <Icon size={18} className={`${config.color} shrink-0 mt-0.5`} />
        <div>
          <h4 className={`font-semibold text-sm ${config.color}`}>{config.label}</h4>
          <p className="text-xs text-neutral-500 mt-0.5">{config.description}</p>
        </div>
      </div>

      {sortedTiers.length > 0 && (
        <div className="ml-7 space-y-0">
          {/* Timeline visual */}
          {sortedTiers.map((tier, index) => {
            const isLast = index === sortedTiers.length - 1;
            const isFullRefund = tier.refund_percent === 100;
            const isNoRefund = tier.refund_percent === 0;

            return (
              <div key={index} className="flex items-start gap-3 relative">
                {/* Timeline dot + line */}
                <div className="flex flex-col items-center shrink-0">
                  <div className={`w-3 h-3 rounded-full border-2 ${
                    isFullRefund ? 'bg-green-500 border-green-600' :
                    isNoRefund ? 'bg-red-500 border-red-600' :
                    'bg-amber-500 border-amber-600'
                  }`} />
                  {!isLast && <div className="w-0.5 h-8 bg-neutral-200" />}
                </div>

                {/* Content */}
                <div className="pb-3">
                  <p className="text-xs font-semibold text-neutral-700">
                    {tier.hours_before > 0
                      ? `More than ${formatHours(tier.hours_before)} before check-in`
                      : 'After check-in time'
                    }
                  </p>
                  <p className={`text-xs font-bold ${
                    isFullRefund ? 'text-green-600' :
                    isNoRefund ? 'text-red-600' :
                    'text-amber-600'
                  }`}>
                    {tier.refund_percent}% refund
                    {isFullRefund && ' — Full refund'}
                    {isNoRefund && ' — No refund'}
                  </p>
                </div>
              </div>
            );
          })}

          {/* Deadline callout */}
          {checkinDate && sortedTiers.length > 0 && (
            <div className="mt-2 bg-white rounded-lg px-3 py-2 border border-neutral-200">
              <p className="text-[10px] text-neutral-500">
                <span className="font-semibold">Note:</span> Free cancellation deadline is{' '}
                <span className="font-bold text-neutral-700">
                  {formatHours(sortedTiers[0].hours_before)} before {checkinDate}
                </span>
              </p>
            </div>
          )}
        </div>
      )}

      {type === 'non_refundable' && (
        <div className="ml-7 mt-1">
          <div className="flex items-center gap-1.5 text-[10px] text-red-500">
            <XCircle size={10} /> Non-refundable rates are typically 10-20% cheaper
          </div>
        </div>
      )}
    </div>
  );
}
