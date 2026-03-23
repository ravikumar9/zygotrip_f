import { clsx } from 'clsx';

// ─── Base pulse block ─────────────────────────────────────────────────────────

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={clsx('animate-pulse rounded bg-neutral-200', className)}
      style={style}
    />
  );
}

// ─── Hotel Search Card Skeleton ───────────────────────────────────────────────

export function HotelCardSkeleton() {
  return (
    <div className="bg-white/80 rounded-2xl shadow-card overflow-hidden flex flex-col sm:flex-row">
      {/* Image */}
      <Skeleton className="sm:w-64 sm:shrink-0 h-48 sm:h-auto rounded-none sm:rounded-l-2xl" />

      {/* Body */}
      <div className="flex-1 p-4 space-y-3">
        {/* Title + stars */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1.5 flex-1">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-3.5 w-32" />
          </div>
          <Skeleton className="h-10 w-12 rounded-xl shrink-0" />
        </div>

        {/* Location */}
        <Skeleton className="h-3.5 w-36" />

        {/* Amenity chips */}
        <div className="flex gap-2">
          <Skeleton className="h-6 w-20 rounded-full" />
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>

        {/* Price row */}
        <div className="flex items-end justify-between pt-2">
          <div className="space-y-1">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-3 w-20" />
          </div>
          <Skeleton className="h-10 w-28 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

// ─── Hotel Detail Skeleton ────────────────────────────────────────────────────

export function HotelDetailSkeleton() {
  return (
    <div className="min-h-screen page-listing-bg">
      {/* Gallery */}
      <div className="h-[420px] bg-neutral-200 animate-pulse" />

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
          {/* Left */}
          <div className="space-y-5">
            {/* Title block */}
            <div className="bg-white/80 rounded-2xl p-6 space-y-3">
              <div className="flex items-start justify-between">
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-8 w-72" />
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-4 w-40" />
                </div>
                <Skeleton className="h-14 w-16 rounded-xl shrink-0" />
              </div>
              <div className="flex gap-2 pt-2">
                <Skeleton className="h-7 w-20 rounded-full" />
                <Skeleton className="h-7 w-28 rounded-full" />
                <Skeleton className="h-7 w-24 rounded-full" />
              </div>
            </div>

            {/* Tab content skeleton */}
            <div className="bg-white/80 rounded-2xl p-6 space-y-3">
              <div className="flex gap-4 border-b pb-3">
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-20" />
              </div>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
              <div className="grid grid-cols-3 gap-3 pt-2">
                {Array.from({ length: 9 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 rounded-xl" />
                ))}
              </div>
            </div>
          </div>

          {/* Right — Booking widget */}
          <div className="bg-white/80 rounded-2xl shadow-card p-5 h-fit space-y-4">
            <Skeleton className="h-6 w-36" />
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="h-14 rounded-xl" />
              <Skeleton className="h-14 rounded-xl" />
            </div>
            <Skeleton className="h-14 rounded-xl" />
            <div className="space-y-2 pt-2">
              <div className="flex justify-between">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-20" />
              </div>
              <div className="flex justify-between">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-16" />
              </div>
              <div className="flex justify-between pt-2 border-t">
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-5 w-24" />
              </div>
            </div>
            <Skeleton className="h-12 rounded-2xl" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Search Results Skeleton ──────────────────────────────────────────────────

export function SearchResultsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <HotelCardSkeleton key={i} />
      ))}
    </div>
  );
}

// ─── Booking Summary / Card Skeleton ─────────────────────────────────────────

export function BookingSummarySkeleton() {
  return (
    <div className="bg-white/80 rounded-2xl shadow-card overflow-hidden">
      {/* Image strip */}
      <Skeleton className="h-40 w-full rounded-none" />

      <div className="p-5 space-y-3">
        {/* Property name + status */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1.5 flex-1">
            <Skeleton className="h-5 w-52" />
            <Skeleton className="h-3.5 w-32" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full shrink-0" />
        </div>

        {/* Dates grid */}
        <div className="grid grid-cols-3 gap-3 bg-page rounded-xl p-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-1">
              <Skeleton className="h-3 w-12" />
              <Skeleton className="h-4 w-16" />
            </div>
          ))}
        </div>

        {/* Price + CTA */}
        <div className="flex items-center justify-between pt-1">
          <div className="space-y-1">
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-6 w-24" />
          </div>
          <Skeleton className="h-9 w-24 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

// ─── Generic Row Skeleton ─────────────────────────────────────────────────────

export function RowSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4"
          style={{ width: `${100 - i * 12}%` }}
        />
      ))}
    </div>
  );
}

export default Skeleton;
