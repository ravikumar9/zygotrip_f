import type { Metadata } from 'next';
import { Suspense } from 'react';
import './globals.css';
import 'leaflet/dist/leaflet.css';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import QueryProvider from './providers';
import AnalyticsProvider from '@/components/AnalyticsProvider';
import ErrorBoundary from '@/components/ErrorBoundary';
import AbandonmentBanner from '@/components/booking/AbandonmentBanner';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'https://zygotrip.com'),
  title: { default: 'ZygoTrip — Hotels, Buses, Cabs & Packages', template: '%s | ZygoTrip' },
  description: 'Book hotels, buses, cabs and holiday packages at the best prices. ZygoTrip — your trusted OTA platform.',
  keywords: ['hotel booking', 'bus tickets', 'cab booking', 'holiday packages', 'India travel', 'cheap hotels'],
  openGraph: {
    type: 'website',
    siteName: 'ZygoTrip',
    locale: 'en_IN',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-image-preview': 'large' },
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION || '',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <Suspense fallback={null}>
            <AnalyticsProvider>
              <ErrorBoundary>
                <Header />
                <main className="pt-14 min-h-screen bg-page">{children}</main>
                <AbandonmentBanner />
                <Footer />
              </ErrorBoundary>
            </AnalyticsProvider>
          </Suspense>
        </QueryProvider>
      </body>
    </html>
  );
}
