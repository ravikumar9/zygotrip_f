import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Terms of Service | ZygoTrip',
  description:
    'Read ZygoTrip\'s Terms of Service. Understand your rights and responsibilities when using our travel booking platform.',
};

const LAST_UPDATED = 'March 14, 2026';

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <section className="text-white py-14 px-4" style={{ background: 'linear-gradient(135deg,#171717,#404040)' }}>
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-3xl md:text-4xl font-black font-heading mb-3">Terms of Service</h1>
          <p className="text-white/70 text-sm">Last updated: {LAST_UPDATED}</p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-4 py-12 space-y-10 text-[15px] text-neutral-700 leading-relaxed">

        <p>
          Welcome to ZygoTrip. By accessing or using the ZygoTrip website, mobile application, or
          any related services (collectively, the <strong>"Platform"</strong>), you agree to be
          bound by these Terms of Service (<strong>"Terms"</strong>). Please read them carefully.
        </p>
        <p>
          These Terms constitute a legally binding agreement between you and ZygoTrip Technologies
          Pvt. Ltd. (<strong>"ZygoTrip"</strong>, <strong>"we"</strong>, <strong>"us"</strong>).
        </p>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">1. Eligibility</h2>
          <p>
            You must be at least 18 years of age to use the Platform. By using the Platform, you
            represent and warrant that you are 18 years of age or older, and that you have the legal
            capacity to enter into these Terms. If you are using the Platform on behalf of an
            organisation, you represent that you have authority to bind that organisation.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">2. Account Registration</h2>
          <ul className="list-disc list-inside space-y-2">
            <li>You must provide accurate, complete, and current information when creating an account.</li>
            <li>You are responsible for maintaining the confidentiality of your account credentials.</li>
            <li>You are responsible for all activities that occur under your account.</li>
            <li>Notify us immediately at <a href="mailto:support@zygotrip.com" className="text-primary-600 underline">support@zygotrip.com</a> if you suspect unauthorised access to your account.</li>
            <li>We reserve the right to suspend or terminate accounts that violate these Terms.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">3. Booking and Payment</h2>

          <h3 className="font-semibold text-neutral-900 mb-2">3.1 Booking Confirmation</h3>
          <p className="mb-3">
            A booking is confirmed only upon receipt of full payment and issuance of a booking
            confirmation with a unique booking reference. ZygoTrip acts as an intermediary
            between you and the service provider (hotel, bus operator, cab company, etc.).
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">3.2 Pricing</h3>
          <p className="mb-3">
            All prices displayed are in Indian Rupees (INR) and inclusive of applicable GST unless
            otherwise stated. Prices may change at any time before booking confirmation. ZygoTrip
            is not responsible for pricing errors but will notify you before charging any amount
            different from what was displayed at checkout.
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">3.3 Payment Processing</h3>
          <p>
            Payment is processed through third-party payment gateways (Cashfree, Stripe, Paytm).
            By submitting payment, you authorise ZygoTrip to charge the applicable amount. All
            payment transactions are encrypted and PCI-DSS compliant.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">4. Cancellations and Refunds</h2>
          <p>
            Cancellation and refund policies vary by booking type and are clearly displayed before
            payment. By confirming a booking, you acknowledge and accept the applicable cancellation
            policy. Please refer to our{' '}
            <Link href="/cancellation-policy" className="text-primary-600 underline">
              Cancellation Policy
            </Link>{' '}
            for full details.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">5. User Conduct</h2>
          <p className="mb-3">You agree not to:</p>
          <ul className="list-disc list-inside space-y-2">
            <li>Use the Platform for any unlawful purpose or in violation of any applicable law</li>
            <li>Make fraudulent bookings or provide false information</li>
            <li>Attempt to circumvent or exploit pricing, promotions, or cashback systems</li>
            <li>Scrape, harvest, or extract data from the Platform without written permission</li>
            <li>Interfere with the security or integrity of the Platform</li>
            <li>Upload or transmit malicious code, viruses, or harmful content</li>
            <li>Post reviews that are false, misleading, defamatory, or in violation of third-party rights</li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">6. ZygoTrip Wallet</h2>
          <ul className="list-disc list-inside space-y-2">
            <li>ZygoTrip Wallet credits can only be used on the Platform and cannot be transferred or withdrawn to a bank account.</li>
            <li>Cashback and promotional credits are subject to validity periods and minimum booking requirements.</li>
            <li>Wallet balances are not interest-bearing and do not expire unless stated otherwise in specific promotions.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">7. Intellectual Property</h2>
          <p>
            All content on the Platform — including text, images, logos, UI designs, and software —
            is the intellectual property of ZygoTrip or its licensors. You may not reproduce,
            distribute, or create derivative works without prior written permission. Property
            images used on the Platform are uploaded by or licensed from property owners.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">8. Third-Party Services</h2>
          <p>
            The Platform may contain links to third-party websites or integrate with third-party
            services (e.g., Google Maps, payment gateways). ZygoTrip is not responsible for the
            content, privacy practices, or conduct of any third-party services. Use of such
            services is at your own risk.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">9. Limitation of Liability</h2>
          <p className="mb-3">
            To the maximum extent permitted by applicable law, ZygoTrip shall not be liable for:
          </p>
          <ul className="list-disc list-inside space-y-2">
            <li>Any indirect, incidental, special, or consequential damages</li>
            <li>Loss of profits, data, goodwill, or business opportunities</li>
            <li>Service failures or errors by third-party providers (hotels, payment gateways, etc.)</li>
            <li>Force majeure events including natural disasters, government actions, or pandemics</li>
          </ul>
          <p className="mt-3">
            ZygoTrip&apos;s total liability to you for any claim arising out of or relating to
            these Terms shall not exceed the amount paid by you for the relevant booking.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">10. Indemnification</h2>
          <p>
            You agree to indemnify and hold harmless ZygoTrip, its officers, employees, and agents
            from any claims, damages, losses, or expenses arising from your use of the Platform,
            violation of these Terms, or infringement of any third-party rights.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">11. Governing Law &amp; Dispute Resolution</h2>
          <p className="mb-3">
            These Terms are governed by the laws of India. Any dispute arising out of or related to
            these Terms shall first be attempted to be resolved through good-faith negotiation.
          </p>
          <p>
            If unresolved within 30 days, disputes shall be submitted to binding arbitration under
            the Arbitration and Conciliation Act, 1996, with arbitration seated in Bengaluru,
            Karnataka. The language of arbitration shall be English.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">12. Changes to Terms</h2>
          <p>
            We reserve the right to modify these Terms at any time. Material changes will be
            communicated via email or a prominent notice on the Platform at least 14 days before
            taking effect. Your continued use of the Platform after the effective date constitutes
            acceptance of the updated Terms.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">13. Contact</h2>
          <p>For questions about these Terms, please contact:</p>
          <address className="not-italic mt-3 bg-neutral-50 rounded-xl p-4 text-sm border border-neutral-100">
            <strong>ZygoTrip Technologies Pvt. Ltd.</strong><br />
            Legal Team<br />
            [Address], Bengaluru, Karnataka, India<br />
            Email:{' '}
            <a href="mailto:legal@zygotrip.com" className="text-primary-600 underline">
              legal@zygotrip.com
            </a>
          </address>
        </section>

        <div className="pt-6 border-t border-neutral-100 flex flex-wrap gap-4 text-sm">
          <Link href="/privacy-policy" className="text-primary-600 hover:underline">Privacy Policy</Link>
          <Link href="/cancellation-policy" className="text-primary-600 hover:underline">Cancellation Policy</Link>
          <Link href="/help" className="text-primary-600 hover:underline">Help Centre</Link>
        </div>
      </div>
    </main>
  );
}
