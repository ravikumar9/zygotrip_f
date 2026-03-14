'use client';

import { useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for IntersectionObserver-based infinite scroll.
 *
 * Returns a ref to attach to a sentinel element at the bottom of the list.
 * Calls `onIntersect` when the sentinel enters the viewport.
 *
 * Usage:
 *   const sentinelRef = useInfiniteScroll({
 *     onIntersect: () => fetchNextPage(),
 *     enabled: hasNextPage && !isFetchingNextPage,
 *   });
 *   return <div ref={sentinelRef} />
 */
export function useInfiniteScroll({
  onIntersect,
  enabled = true,
  rootMargin = '400px',
}: {
  onIntersect: () => void;
  enabled?: boolean;
  rootMargin?: string;
}) {
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const callbackRef = useRef(onIntersect);
  callbackRef.current = onIntersect;

  const setRef = useCallback(
    (node: HTMLDivElement | null) => {
      sentinelRef.current = node;
    },
    []
  );

  useEffect(() => {
    if (!enabled || !sentinelRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          callbackRef.current();
        }
      },
      { rootMargin }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [enabled, rootMargin]);

  return setRef;
}
