'use client';

import { useState, useEffect } from 'react';
import { Heart } from 'lucide-react';
import api from '@/services/api';
import toast from 'react-hot-toast';
import { clsx } from 'clsx';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

interface WishlistButtonProps {
  propertyId: number;
  initialSaved?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'icon' | 'button';
  onToggle?: (saved: boolean) => void;
  className?: string;
}

const SIZE_MAP = {
  sm: { icon: 15, px: 'px-2.5 py-1.5', text: 'text-xs' },
  md: { icon: 18, px: 'px-3 py-2', text: 'text-sm' },
  lg: { icon: 20, px: 'px-4 py-2.5', text: 'text-sm' },
};

export default function WishlistButton({
  propertyId,
  initialSaved = false,
  size = 'md',
  variant = 'icon',
  onToggle,
  className,
}: WishlistButtonProps) {
  const { isAuthenticated } = useAuth();
  const router = useRouter();
  const [saved, setSaved] = useState(initialSaved);
  const [loading, setLoading] = useState(false);

  // Sync with server once on mount if authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    api
      .get(`/properties/${propertyId}/save/`)
      .then((res) => setSaved(res.data?.saved ?? false))
      .catch(() => {}); // silently ignore
  }, [propertyId, isAuthenticated]);

  const handleToggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!isAuthenticated) {
      toast.error('Sign in to save properties');
      router.push('/account/login');
      return;
    }

    const prev = saved;
    // Optimistic update
    setSaved(!prev);
    setLoading(true);

    try {
      if (prev) {
        await api.delete(`/properties/${propertyId}/save/`);
        toast.success('Removed from saved');
      } else {
        await api.post(`/properties/${propertyId}/save/`);
        toast.success('Saved to wishlist ❤️');
      }
      onToggle?.(!prev);
    } catch (err: any) {
      // Revert on failure
      setSaved(prev);
      if (err?.response?.status === 401) {
        toast.error('Sign in to save properties');
        router.push('/account/login');
      } else {
        toast.error('Could not update wishlist');
      }
    } finally {
      setLoading(false);
    }
  };

  const { icon: iconSize, px, text } = SIZE_MAP[size];

  if (variant === 'button') {
    return (
      <button
        onClick={handleToggle}
        disabled={loading}
        className={clsx(
          'flex items-center gap-1.5 rounded-full font-semibold border transition-all',
          px,
          text,
          saved
            ? 'bg-red-50 border-red-300 text-red-600 hover:bg-red-100'
            : 'bg-white/80/90 border-neutral-200 text-neutral-600 hover:border-red-300 hover:text-red-500',
          loading && 'opacity-60 cursor-not-allowed',
          className,
        )}
        aria-label={saved ? 'Remove from wishlist' : 'Save to wishlist'}
      >
        <Heart
          size={iconSize}
          fill={saved ? 'currentColor' : 'none'}
          strokeWidth={1.8}
          className={clsx('transition-transform', !loading && 'hover:scale-110')}
        />
        {saved ? 'Saved' : 'Save'}
      </button>
    );
  }

  // Icon-only variant (floating heart)
  return (
    <button
      onClick={handleToggle}
      disabled={loading}
      className={clsx(
        'flex items-center justify-center rounded-full shadow-md transition-all',
        size === 'sm' ? 'w-8 h-8' : size === 'lg' ? 'w-11 h-11' : 'w-9 h-9',
        saved ? 'bg-red-500 text-white' : 'bg-white/80/90 text-neutral-500 hover:text-red-500',
        loading && 'opacity-60 cursor-not-allowed',
        className,
      )}
      aria-label={saved ? 'Remove from wishlist' : 'Save to wishlist'}
    >
      <Heart
        size={iconSize}
        fill={saved ? 'currentColor' : 'none'}
        strokeWidth={1.8}
        className="transition-transform hover:scale-110"
      />
    </button>
  );
}
