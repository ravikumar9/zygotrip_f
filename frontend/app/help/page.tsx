import type { Metadata } from 'next';
import Link from 'next/link';

const SOCIAL_LINKS = [
  { label: 'Facebook', href: 'https://www.facebook.com/profile.php?id=61583679493958' },
  { label: 'YouTube', href: 'https://youtube.com/@zygotrip' },
  { label: 'LinkedIn', href: 'https://www.linkedin.com/in/zygo-trip-1968a63b6/' },
  { label: 'X', href: 'https://x.com/ZygoTrip' },
  { label: 'Instagram', href: 'https://www.instagram.com/zygotrip/' },
];

export const metadata: Metadata = {
  title: 'Help Centre | ZygoTrip Support',
  description:
    'Find answers to common questions about bookings, payments, cancellations, and more on ZygoTrip. Contact our support team for assistance.',
};

const FAQ_CATEGORIES = [
  {
    icon: '🏨',
    title: 'Hotel Bookings',
    faqs: [
      {
        q: 'How do I book a hotel on ZygoTrip?',
        a: 'Search for your destination, select check-in and check-out dates, choose your preferred hotel and room, then complete payment. You\'ll receive an instant booking confirmation via email and SMS.',
      },
      {
        q: 'Can I modify my hotel booking after confirmation?',
        a: 'Modifications depend on the property\'s policy. Visit "My Bookings", select the booking, and check if modification is available. For date changes, contact our support team.',
      },
      {
        q: 'What documents do I need at hotel check-in?',
        a: 'Carry a valid government-issued photo ID (Aadhaar, passport, or driving licence) and your booking confirmation (email or app). Some properties may also require a credit card for incidentals.',
      },
      {
        q: 'What is a price lock and inventory hold?',
        a: 'When you begin checkout, we place a 30-minute inventory hold on your selected room at the quoted price. This ensures the room remains available and the price doesn\'t change while you complete payment.',
      },
    ],
  },
  {
    icon: '💳',
    title: 'Payments & Refunds',
    faqs: [
      {
        q: 'What payment methods does ZygoTrip accept?',
        a: 'We accept UPI, Credit/Debit Cards (Visa, Mastercard, Amex), NetBanking, Paytm, and ZygoTrip Wallet. All transactions are encrypted and PCI-DSS compliant.',
      },
      {
        q: 'My payment failed but amount was deducted. What should I do?',
        a: 'In most cases, failed payment amounts are automatically reversed within 5–7 business days. If you don\'t see the reversal, please email us at support@zygotrip.com with your transaction details.',
      },
      {
        q: 'How long does a refund take?',
        a: 'Refunds to ZygoTrip Wallet are instant. UPI/NetBanking refunds take 3–5 business days and credit/debit card refunds take 5–7 business days.',
      },
      {
        q: 'What is ZygoTrip Wallet and how does it work?',
        a: 'ZygoTrip Wallet is a digital wallet within the app. You can add money to it and use it for instant bookings. Cashback from bookings is credited to your wallet. Wallet balance cannot be transferred to a bank account.',
      },
    ],
  },
  {
    icon: '❌',
    title: 'Cancellations',
    faqs: [
      {
        q: 'How do I cancel my booking?',
        a: 'Go to My Bookings, select the booking, and click "Cancel Booking". The refund will be processed as per the cancellation policy displayed at the time of booking.',
      },
      {
        q: 'What is free cancellation?',
        a: 'Free cancellation means you can cancel your booking without any charge before the specified deadline (usually 24–48 hours before check-in). Look for the "Free Cancellation" badge when searching.',
      },
      {
        q: 'I missed the free cancellation window. Can I still get a refund?',
        a: 'Unfortunately, cancellations after the free period attract a penalty as per the rate plan policy. In exceptional circumstances (medical emergency, etc.), contact our support team with documentation.',
      },
    ],
  },
  {
    icon: '🚌',
    title: 'Buses & Cabs',
    faqs: [
      {
        q: 'How early should I arrive for a bus?',
        a: 'We recommend arriving at the boarding point at least 15 minutes before departure. Carry your e-ticket (email/app) and a valid ID.',
      },
      {
        q: 'Can I reschedule a bus ticket?',
        a: 'Rescheduling depends on the bus operator\'s policy. Check your booking for reschedule options, or contact our support team.',
      },
      {
        q: 'How do I track my cab?',
        a: 'Once your cab is dispatched, you can track the driver\'s live location in the ZygoTrip app under "My Bookings" → your cab booking.',
      },
    ],
  },
];

export default function HelpPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <section className="text-white py-16 px-4 text-center" style={{ background: 'linear-gradient(135deg,#1d4ed8,#f97316)' }}>
        <h1 className="text-3xl md:text-4xl font-black font-heading mb-3">Help Centre</h1>
        <p className="text-white/80 max-w-xl mx-auto text-sm mb-8">
          Find answers to your questions or get in touch with our support team.
        </p>
        {/* Quick contact */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="mailto:support@zygotrip.com"
            className="bg-white text-primary-700 font-semibold px-6 py-3 rounded-xl hover:bg-neutral-50 transition-colors text-sm inline-flex items-center gap-2"
          >
            ✉️ Email Support
          </a>
          <a
            href="https://wa.me/91XXXXXXXXXX"
            target="_blank"
            rel="noopener noreferrer"
            className="border border-white/50 text-white font-semibold px-6 py-3 rounded-xl hover:bg-white/10 transition-colors text-sm inline-flex items-center gap-2"
          >
            💬 WhatsApp Chat
          </a>
        </div>
      </section>

      {/* Quick links */}
      <section className="bg-neutral-50 border-b border-neutral-100 py-6 px-4">
        <div className="max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-sm">
          {[
            { label: 'My Bookings', href: '/bookings', icon: '📋' },
            { label: 'Cancellation Policy', href: '/cancellation-policy', icon: '❌' },
            { label: 'Privacy Policy', href: '/privacy-policy', icon: '🔒' },
            { label: 'Contact Us', href: 'mailto:support@zygotrip.com', icon: '📬' },
          ].map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="bg-white border border-neutral-200 rounded-xl px-4 py-3 hover:shadow-md hover:border-primary-300 transition-all font-medium text-neutral-700"
            >
              <span className="block text-xl mb-1">{link.icon}</span>
              {link.label}
            </Link>
          ))}
        </div>
      </section>

      {/* FAQ Categories */}
      <section className="max-w-4xl mx-auto px-4 py-14 space-y-12">
        <h2 className="text-2xl font-bold text-neutral-900 font-heading text-center">
          Frequently Asked Questions
        </h2>

        {FAQ_CATEGORIES.map((cat) => (
          <div key={cat.title}>
            <h3 className="text-lg font-bold text-neutral-900 mb-4 flex items-center gap-2">
              <span>{cat.icon}</span> {cat.title}
            </h3>
            <div className="space-y-3">
              {cat.faqs.map((faq, i) => (
                <details
                  key={i}
                  className="bg-white border border-neutral-200 rounded-xl overflow-hidden group"
                >
                  <summary className="px-5 py-4 text-sm font-semibold text-neutral-800 cursor-pointer hover:bg-neutral-50 transition-colors list-none flex items-center justify-between">
                    {faq.q}
                    <span className="text-neutral-400 ml-4 shrink-0 group-open:rotate-180 transition-transform">
                      ▼
                    </span>
                  </summary>
                  <div className="px-5 pb-4 text-sm text-neutral-600 leading-relaxed">
                    {faq.a}
                  </div>
                </details>
              ))}
            </div>
          </div>
        ))}
      </section>

      {/* Still need help */}
      <section className="bg-neutral-50 border-t border-neutral-100 py-14 px-4 text-center">
        <h2 className="text-xl font-bold text-neutral-900 mb-2">Still need help?</h2>
        <p className="text-neutral-500 text-sm mb-6">
          Our support team is available 9 AM – 9 PM IST, 7 days a week.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center text-sm">
          <a
            href="mailto:support@zygotrip.com"
            className="bg-primary-600 text-white font-semibold px-7 py-3 rounded-xl hover:bg-primary-700 transition-colors"
          >
            Email: support@zygotrip.com
          </a>
          <a
            href="tel:1800XXXXXXXX"
            className="border border-neutral-300 text-neutral-700 font-semibold px-7 py-3 rounded-xl hover:bg-neutral-100 transition-colors"
          >
            Call: 1800-xxx-xxxx (Toll Free)
          </a>
        </div>
        <div className="mt-8">
          <p className="text-xs uppercase tracking-wide text-neutral-400 font-semibold mb-3">
            Official ZygoTrip channels
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
            {SOCIAL_LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full border border-neutral-200 bg-white px-4 py-2 text-neutral-600 hover:border-primary-300 hover:text-primary-700 transition-colors"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
