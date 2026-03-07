'use client';

import { Suspense } from 'react';
import BookingFlow from './BookingFlow';
import LoadingSpinner from '@/components/ui/LoadingSpinner';

export default function BookingPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <BookingFlow />
    </Suspense>
  );
}
