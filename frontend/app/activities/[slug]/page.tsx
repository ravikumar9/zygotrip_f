import { Metadata } from 'next';
import ActivityDetailClient from './ActivityDetailClient';

export const metadata: Metadata = {
  title: 'Activity Details | Zygotrip',
  description: 'View activity details, select a time slot, and book your experience.',
};

export default function ActivityDetailPage({ params }: { params: { slug: string } }) {
  return <ActivityDetailClient slug={params.slug} />;
}
