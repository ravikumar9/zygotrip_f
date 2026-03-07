'use client';
import { Star } from 'lucide-react';
import { clsx } from 'clsx';

interface RatingStarsProps {
  rating: number;
  reviewCount?: number;
  showCount?: boolean;
  size?: 'sm' | 'md' | 'lg';
  tier?: string;
}

const tierColors = {
  excellent: 'bg-green-100 text-green-800',
  good: 'bg-blue-100 text-blue-700',
  average: 'bg-yellow-100 text-yellow-700',
  below_average: 'bg-gray-100 text-gray-600',
};

export default function RatingStars({ rating, reviewCount, showCount = true, size = 'sm', tier }: RatingStarsProps) {
  const stars = Math.round(rating);
  const iconSize = size === 'sm' ? 12 : size === 'md' ? 16 : 20;

  return (
    <div className="flex items-center gap-1.5">
      <div className="flex items-center gap-0.5">
        {Array.from({ length: 5 }, (_, i) => (
          <Star
            key={i}
            size={iconSize}
            className={i < stars ? 'fill-amber-400 text-amber-400' : 'fill-gray-200 text-gray-200'}
          />
        ))}
      </div>
      {showCount && typeof reviewCount === 'number' && (
        <span className="text-xs text-neutral-500">
          {rating.toFixed(1)} ({reviewCount.toLocaleString()})
        </span>
      )}
      {tier && (
        <span className={clsx('text-xs font-medium px-1.5 py-0.5 rounded-full capitalize', tierColors[tier as keyof typeof tierColors] ?? 'bg-gray-100 text-gray-600')}>
          {tier.replace('_', ' ')}
        </span>
      )}
    </div>
  );
}
