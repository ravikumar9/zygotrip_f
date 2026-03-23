import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Privacy Policy | ZygoTrip',
  description:
    'Read ZygoTrip\'s privacy policy to understand how we collect, use, and protect your personal data. Your privacy matters to us.',
};

const LAST_UPDATED = 'March 14, 2026';

export default function PrivacyPolicyPage() {
  return (
    <main className="min-h-screen page-listing-bg">
      {/* Header */}
      <section className="text-white py-14 px-4" style={{ background: 'linear-gradient(135deg,#171717,#404040)' }}>
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-3xl md:text-4xl font-black font-heading mb-3">Privacy Policy</h1>
          <p className="text-white/70 text-sm">Last updated: {LAST_UPDATED}</p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-4 py-12 space-y-10 text-[15px] text-neutral-700 leading-relaxed">

        <p>
          ZygoTrip Technologies Pvt. Ltd. (<strong>"ZygoTrip"</strong>, <strong>"we"</strong>,{' '}
          <strong>"us"</strong>, or <strong>"our"</strong>) is committed to protecting your privacy.
          This Privacy Policy explains how we collect, use, disclose, and safeguard information when
          you use our website, mobile application, and services (collectively, the{' '}
          <strong>"Platform"</strong>).
        </p>
        <p>
          By using the Platform, you agree to the terms of this Privacy Policy. If you do not agree,
          please discontinue use of our Platform.
        </p>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">1. Information We Collect</h2>

          <h3 className="font-semibold text-neutral-900 mb-2">1.1 Information You Provide</h3>
          <ul className="list-disc list-inside space-y-1 mb-4">
            <li><strong>Account information</strong>: name, email address, mobile number, password</li>
            <li><strong>Booking details</strong>: guest names, check-in/check-out dates, travel preferences</li>
            <li><strong>Payment information</strong>: payment method type (we do not store full card numbers — these are handled by PCI-DSS compliant gateways)</li>
            <li><strong>Communications</strong>: messages sent to our support team</li>
            <li><strong>Reviews and ratings</strong>: content you submit about properties</li>
          </ul>

          <h3 className="font-semibold text-neutral-900 mb-2">1.2 Automatically Collected Information</h3>
          <ul className="list-disc list-inside space-y-1 mb-4">
            <li>Device identifiers (device type, OS, browser, IP address)</li>
            <li>Usage data (pages visited, search queries, click events)</li>
            <li>Location data (only when you grant permission)</li>
            <li>Cookies and similar tracking technologies (see Section 6)</li>
          </ul>

          <h3 className="font-semibold text-neutral-900 mb-2">1.3 Information from Third Parties</h3>
          <ul className="list-disc list-inside space-y-1">
            <li>Social login data (name, email) when you sign in with Google or Facebook</li>
            <li>Payment confirmation data from our payment gateway partners (Cashfree, Stripe, Paytm)</li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">2. How We Use Your Information</h2>
          <p className="mb-3">We use the collected information to:</p>
          <ul className="list-disc list-inside space-y-2">
            <li>Process and confirm bookings, and send booking confirmation and vouchers</li>
            <li>Process payments and issue invoices and refunds</li>
            <li>Send transactional notifications via email, SMS, and WhatsApp</li>
            <li>Provide customer support and resolve disputes</li>
            <li>Personalise search results, recommendations, and pricing displays</li>
            <li>Detect and prevent fraud, abuse, and security incidents</li>
            <li>Improve our Platform through analytics and A/B testing</li>
            <li>Send promotional offers and newsletters (only with your consent; you may opt out at any time)</li>
            <li>Comply with legal and regulatory obligations</li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">3. Sharing of Information</h2>
          <p className="mb-3">
            We do not sell your personal data. We may share your information in the following circumstances:
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">3.1 Service Providers</h3>
          <p className="mb-3">
            We share necessary data with third-party vendors who perform services on our behalf,
            including payment gateways, cloud hosting providers, SMS/WhatsApp providers, and
            analytics platforms. These vendors are contractually bound to protect your data.
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">3.2 Hotel / Transport Partners</h3>
          <p className="mb-3">
            To fulfil your booking, we share your name, contact details, and booking information
            with the relevant hotel, bus operator, or cab provider.
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">3.3 Legal Requirements</h3>
          <p>
            We may disclose information if required by law, court order, or government authority,
            or to protect the rights, property, or safety of ZygoTrip, our users, or the public.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">4. Data Security</h2>
          <p className="mb-3">
            We implement industry-standard security measures to protect your data:
          </p>
          <ul className="list-disc list-inside space-y-2">
            <li>All data in transit is encrypted using TLS 1.3</li>
            <li>Passwords are hashed using bcrypt with a high work factor</li>
            <li>Payment data is processed through PCI-DSS Level 1 certified gateways</li>
            <li>Access to production systems is restricted to authorised personnel only</li>
            <li>Regular security audits and penetration testing are conducted</li>
          </ul>
          <p className="mt-3">
            While we take all reasonable precautions, no method of transmission over the Internet
            is 100% secure. In the event of a data breach that affects your rights, we will notify
            you as required by applicable law.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">5. Your Rights</h2>
          <p className="mb-3">
            Subject to applicable Indian data protection laws, you have the right to:
          </p>
          <ul className="list-disc list-inside space-y-2">
            <li><strong>Access</strong>: Request a copy of the personal data we hold about you</li>
            <li><strong>Correction</strong>: Request correction of inaccurate or incomplete data</li>
            <li><strong>Deletion</strong>: Request deletion of your account and associated data (subject to legal retention requirements)</li>
            <li><strong>Portability</strong>: Request your data in a structured, machine-readable format</li>
            <li><strong>Opt-out</strong>: Unsubscribe from marketing communications at any time</li>
          </ul>
          <p className="mt-3">
            To exercise any of these rights, please email{' '}
            <a href="mailto:privacy@zygotrip.com" className="text-primary-600 underline">
              privacy@zygotrip.com
            </a>
            . We will respond within 30 days.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">6. Cookies Policy</h2>
          <p className="mb-3">
            We use cookies and similar technologies to enhance your experience on the Platform.
            Cookies help us remember your preferences, keep you logged in, and understand how
            you use our Platform.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-neutral-100">
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Cookie Type</th>
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Purpose</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Essential', 'Required for authentication, sessions, and security'],
                  ['Functional', 'Remember language, currency, and preferences'],
                  ['Analytics', 'Understand usage patterns to improve the Platform'],
                  ['Marketing', 'Deliver relevant ads on third-party platforms (opt-in only)'],
                ].map(([type, purpose]) => (
                  <tr key={type} className="odd:bg-white/80 even:bg-page">
                    <td className="px-4 py-2 border border-neutral-200 font-medium">{type}</td>
                    <td className="px-4 py-2 border border-neutral-200">{purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            You can manage cookie preferences through your browser settings. Disabling essential
            cookies may affect Platform functionality.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">7. Children&apos;s Privacy</h2>
          <p>
            ZygoTrip is not directed at children under the age of 18. We do not knowingly collect
            personal data from minors. If you believe a minor has provided us with personal data,
            please contact us immediately at{' '}
            <a href="mailto:privacy@zygotrip.com" className="text-primary-600 underline">
              privacy@zygotrip.com
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">8. Data Retention</h2>
          <p>
            We retain your personal data for as long as your account is active or as needed to
            provide services, comply with legal obligations, resolve disputes, and enforce our
            agreements. Booking records are retained for a minimum of 7 years for accounting and
            tax compliance purposes.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">9. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify you of material
            changes via email or a prominent notice on the Platform at least 14 days before the
            change takes effect. Continued use of the Platform after the effective date constitutes
            acceptance of the updated policy.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">10. Contact Us</h2>
          <p>For privacy-related queries or to exercise your data rights, contact our Data Protection Officer:</p>
          <address className="not-italic mt-3 bg-page rounded-xl p-4 text-sm border border-neutral-100">
            <strong>ZygoTrip Technologies Pvt. Ltd.</strong><br />
            Attn: Data Protection Officer<br />
            [Address], Bengaluru, Karnataka, India<br />
            Email:{' '}
            <a href="mailto:privacy@zygotrip.com" className="text-primary-600 underline">
              privacy@zygotrip.com
            </a>
          </address>
        </section>

        <div className="pt-6 border-t border-neutral-100 flex flex-wrap gap-4 text-sm">
          <Link href="/terms" className="text-primary-600 hover:underline">Terms of Service</Link>
          <Link href="/cancellation-policy" className="text-primary-600 hover:underline">Cancellation Policy</Link>
          <Link href="/help" className="text-primary-600 hover:underline">Help Centre</Link>
        </div>
      </div>
    </main>
  );
}
