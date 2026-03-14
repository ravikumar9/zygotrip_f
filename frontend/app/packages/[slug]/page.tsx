import { Metadata } from 'next';
import PackageDetailClient from './PackageDetailClient';

export const metadata: Metadata = {
  title: 'Package Details | ZygoTrip',
  description: 'Explore holiday package details, day-by-day itinerary, customize your trip, and book at the best price.',
};

export default function PackageDetailPage() {
  return <PackageDetailClient />;
}
