'use client';

import { useEffect } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import Script from 'next/script';
import { analytics } from '@/lib/analytics';

/**
 * AnalyticsProvider — wraps the app to inject GA4/GTM scripts
 * and track client-side route transitions.
 *
 * Place in layout.tsx inside QueryProvider.
 */
export default function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Initialize analytics on mount
  useEffect(() => {
    analytics.init();
  }, []);

  // Track route changes
  useEffect(() => {
    const url = pathname + (searchParams.toString() ? `?${searchParams.toString()}` : '');
    analytics.pageView(url);
  }, [pathname, searchParams]);

  const gaId = analytics.GA_MEASUREMENT_ID;
  const gtmId = analytics.GTM_CONTAINER_ID;

  return (
    <>
      {/* GA4 — only load when measurement ID is set */}
      {gaId && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
            strategy="afterInteractive"
          />
          <Script id="ga4-init" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${gaId}', {
                page_path: window.location.pathname,
                send_page_view: false,
                cookie_flags: 'SameSite=Lax;Secure',
              });
            `}
          </Script>
        </>
      )}

      {/* GTM — only load when container ID is set */}
      {gtmId && (
        <Script id="gtm-init" strategy="afterInteractive">
          {`
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','${gtmId}');
          `}
        </Script>
      )}

      {children}
    </>
  );
}
