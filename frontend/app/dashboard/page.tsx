import { Metadata } from 'next';
import OwnerDashboardClient from './OwnerDashboardClient';

export const metadata: Metadata = {
  title: 'Owner Dashboard | ZygoTrip',
  description: 'Manage your property, bookings, revenue, and inventory on the ZygoTrip owner dashboard.',
};

export default function DashboardPage() {
  return <OwnerDashboardClient />;
}
