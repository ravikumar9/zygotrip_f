'use client';

import { Flame, Clock, TrendingUp, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';

type UrgencyType = 'scarcity' | 'demand' | 'time' | 'price-drop';

interface UrgencyBadgeProps {
  type: UrgencyType;
  text: string;
  size?: 'sm' | 'md';
  className?: string;
  animate?: boolean;
}

const ICON_MAP = {
  scarcity:    AlertTriangle,
  demand:      Flame,
  time:        Clock,
  'price-drop': TrendingUp,
};

const COLOR_MAP = {
  scarcity:    'bg-red-50 text-red-700 border-red-200',
  demand:      'bg-orange-50 text-orange-700 border-orange-200',
  time:        'bg-amber-50 text-amber-700 border-amber-200',
  'price-drop': 'bg-green-50 text-green-700 border-green-200',
};

/**
 * OTA urgency/scarcity badge — drives conversion via FOMO.
 *
 * Usage:
 * <UrgencyBadge type="scarcity" text="Only 2 rooms left" />
 * <UrgencyBadge type="demand" text="Booked 5 times today" />
 * <UrgencyBadge type="price-drop" text="Price dropped ₹500" />
 */
export default function UrgencyBadge({
  type,
  text,
  size = 'sm',
  className,
  animate = true,
}: UrgencyBadgeProps) {
  const Icon = ICON_MAP[type];
  const isSm = size === 'sm';

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border font-bold',
        COLOR_MAP[type],
        isSm ? 'px-2 py-0.5 text-2xs' : 'px-3 py-1 text-xs',
        animate && type === 'scarcity' && 'animate-pulse-soft',
        className,
      )}
    >
      <Icon className={isSm ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      {text}
    </span>
  );
}
