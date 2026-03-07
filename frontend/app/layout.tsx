import type { Metadata } from 'next';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import QueryProvider from './providers';

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
          <Header />
          <main className="pt-14 min-h-screen">{children}</main>
          <Footer />
          <Toaster
            position="top-center"
            toastOptions={{
              duration: 6000,
              style: {
                maxWidth: '440px',
                fontSize: '14px',
                fontWeight: '600',
                borderRadius: '12px',
                padding: '12px 16px',
              },
              success: {
                iconTheme: { primary: '#00a652', secondary: '#fff' },
              },
              error: {
                iconTheme: { primary: '#EB2026', secondary: '#fff' },
              },
            }}
          />
        </QueryProvider>
      </body>
    </html>
  );
}
