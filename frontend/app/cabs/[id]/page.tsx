import { Metadata } from 'next';
import CabDetailClient from './CabDetailClient';

export const metadata: Metadata = {
  title: 'Book Cab | ZygoTrip',
  description: 'Book a cab with verified drivers, live GPS tracking, and transparent pricing.',
};

export default function CabDetailPage() {
  return <CabDetailClient />;
}
