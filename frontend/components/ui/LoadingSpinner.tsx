'use client';
import { clsx } from 'clsx';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export default function LoadingSpinner({ size = 'md', className }: LoadingSpinnerProps) {
  return (
    <div
      className={clsx(
        'inline-block animate-spin rounded-full border-2 border-neutral-200 border-t-primary-600',
        size === 'sm' && 'w-4 h-4',
        size === 'md' && 'w-8 h-8',
        size === 'lg' && 'w-12 h-12',
        className
      )}
    />
  );
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center space-y-3">
        <LoadingSpinner size="lg" />
        <p className="text-sm text-neutral-500">Loading...</p>
      </div>
    </div>
  );
}
