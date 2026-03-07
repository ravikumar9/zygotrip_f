'use client';
import { clsx } from 'clsx';

interface AmenityBadgeProps {
  name: string;
  icon?: string;
  variant?: 'default' | 'outlined';
}

// Icon map for common amenities
const iconMap: Record<string, string> = {
  wifi: '📶', 'free wifi': '📶',
  pool: '🏊', swimming: '🏊',
  parking: '🅿️', 'free parking': '🅿️',
  gym: '💪', fitness: '💪',
  spa: '💆', restaurant: '🍽️',
  bar: '🍸', 'air conditioning': '❄️', ac: '❄️',
  breakfast: '🍳', 'room service': '🛎️',
  pet: '🐾', 'pet friendly': '🐾',
};

export default function AmenityBadge({ name, icon, variant = 'default' }: AmenityBadgeProps) {
  const emoji = icon || iconMap[name.toLowerCase()] || '✓';
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full whitespace-nowrap',
        variant === 'default'
          ? 'bg-neutral-100 text-neutral-700'
          : 'border border-neutral-200 text-neutral-600'
      )}
    >
      <span>{emoji}</span>
      <span>{name}</span>
    </span>
  );
}
