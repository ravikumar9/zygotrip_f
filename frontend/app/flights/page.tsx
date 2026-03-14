import { Metadata } from 'next';
import FlightSearchClient from './FlightSearchClient';

export const metadata: Metadata = {
  title: 'Search Flights | ZygoTrip',
  description: 'Search and compare flights across 100+ airlines. Find the cheapest fares with instant booking confirmation.',
};

export default function FlightsPage() {
  return <FlightSearchClient />;
}
