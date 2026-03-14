import { Metadata } from 'next';
import ActivitySearchClient from './ActivitySearchClient';

export const metadata: Metadata = {
  title: 'Activities & Things To Do | Zygotrip',
  description: 'Discover tours, experiences, and activities worldwide. Book with instant confirmation and free cancellation.',
};

export default function ActivitiesPage() {
  return <ActivitySearchClient />;
}
