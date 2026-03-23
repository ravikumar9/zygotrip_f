import Link from 'next/link';

export const metadata = {
  title: 'Terms of Service — ZygoTrip',
  description: 'Read the ZygoTrip Terms of Service for booking hotels and travel packages.',
};

export default function TermsPage() {
  return (
    <div className="min-h-screen page-listing-bg py-12">
      <div className="max-w-3xl mx-auto px-4">
        <div className="bg-white rounded-2xl shadow-card p-8 md:p-12">
          <Link href="/" className="text-2xl font-black text-primary-600 font-heading mb-8 block">
            Zygo<span className="text-accent-500">Trip</span>
          </Link>

          <h1 className="text-3xl font-black text-neutral-900 mb-2">Terms of Service</h1>
          <p className="text-neutral-500 text-sm mb-8">Last updated: March 2026</p>

          <div className="prose prose-neutral max-w-none space-y-6 text-neutral-700 text-sm leading-relaxed">

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">1. Acceptance of Terms</h2>
              <p>By accessing or using ZygoTrip ("we", "us", "our"), you agree to be bound by these Terms of Service. If you do not agree, please do not use our platform.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">2. Booking & Reservations</h2>
              <p>All bookings made through ZygoTrip are subject to availability and confirmation. We act as an intermediary between travellers and accommodation providers. Prices displayed include applicable taxes and fees unless otherwise stated.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">3. Payments</h2>
              <p>Payments are processed securely through our payment partners (Cashfree Payments). By completing a booking you authorise the charge of the displayed amount to your selected payment method. All amounts are in Indian Rupees (INR) unless stated otherwise.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">4. Cancellations & Refunds</h2>
              <p>Cancellation policies vary by property. The applicable policy is displayed on the property page and during checkout. Refunds for eligible cancellations are processed within 5–7 business days to the original payment method.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">5. User Accounts</h2>
              <p>You are responsible for maintaining the confidentiality of your account credentials. You agree not to share your account with others and to notify us immediately of any unauthorised access.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">6. Prohibited Activities</h2>
              <p>You may not use ZygoTrip for any unlawful purpose, to submit false information, to attempt to gain unauthorised access to our systems, or to interfere with the proper operation of the platform.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">7. Limitation of Liability</h2>
              <p>ZygoTrip is not liable for any indirect, incidental, or consequential damages arising from your use of the platform. Our maximum liability is limited to the amount you paid for the relevant booking.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">8. Governing Law</h2>
              <p>These terms are governed by the laws of India. Any disputes shall be subject to the exclusive jurisdiction of courts in Bengaluru, Karnataka.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">9. Contact Us</h2>
              <p>For questions about these terms, please contact us at <a href="mailto:support@zygotrip.com" className="text-primary-600 underline">support@zygotrip.com</a>.</p>
            </section>
          </div>

          <div className="mt-8 pt-6 border-t border-neutral-100 flex gap-4 text-sm">
            <Link href="/legal/privacy" className="text-primary-600 hover:underline font-medium">Privacy Policy</Link>
            <Link href="/" className="text-neutral-400 hover:text-neutral-600">Back to Home</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
