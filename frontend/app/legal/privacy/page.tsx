import Link from 'next/link';

export const metadata = {
  title: 'Privacy Policy — ZygoTrip',
  description: 'Learn how ZygoTrip collects, uses, and protects your personal information.',
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen page-listing-bg py-12">
      <div className="max-w-3xl mx-auto px-4">
        <div className="bg-white rounded-2xl shadow-card p-8 md:p-12">
          <Link href="/" className="text-2xl font-black text-primary-600 font-heading mb-8 block">
            Zygo<span className="text-accent-500">Trip</span>
          </Link>

          <h1 className="text-3xl font-black text-neutral-900 mb-2">Privacy Policy</h1>
          <p className="text-neutral-500 text-sm mb-8">Last updated: March 2026</p>

          <div className="prose prose-neutral max-w-none space-y-6 text-neutral-700 text-sm leading-relaxed">

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">1. Information We Collect</h2>
              <p>We collect information you provide when creating an account (name, email, phone), making bookings (payment details, travel dates, guest information), and interacting with our platform (search queries, viewed properties, reviews).</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">2. How We Use Your Information</h2>
              <p>We use your information to process bookings, send booking confirmations and updates, personalise your experience, prevent fraud, improve our platform, and comply with legal obligations.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">3. Information Sharing</h2>
              <p>We share your information with accommodation providers to fulfil your booking, payment processors to complete transactions, and service providers who assist our operations. We do not sell your personal information to third parties.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">4. Cookies</h2>
              <p>We use cookies and similar technologies to maintain your session, remember your preferences, and analyse usage patterns. You can control cookies through your browser settings, though this may affect platform functionality.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">5. Data Security</h2>
              <p>We implement industry-standard security measures including encryption in transit (TLS), encrypted storage for sensitive data, and regular security audits. No system is 100% secure; please use strong passwords and protect your account credentials.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">6. Data Retention</h2>
              <p>We retain your personal data for as long as your account is active or as required by law. Booking records are retained for 7 years for financial compliance. You may request deletion of your account data subject to legal retention requirements.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">7. Your Rights</h2>
              <p>You have the right to access, correct, or delete your personal information. You may also object to processing or request data portability. To exercise these rights, contact us at <a href="mailto:privacy@zygotrip.com" className="text-primary-600 underline">privacy@zygotrip.com</a>.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">8. Children's Privacy</h2>
              <p>Our services are not directed at children under 18. We do not knowingly collect personal information from minors.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">9. Changes to This Policy</h2>
              <p>We may update this policy from time to time. We will notify you of significant changes via email or a prominent notice on our platform.</p>
            </section>

            <section>
              <h2 className="text-lg font-bold text-neutral-900 mb-2">10. Contact Us</h2>
              <p>For privacy-related questions, contact our Data Protection Officer at <a href="mailto:privacy@zygotrip.com" className="text-primary-600 underline">privacy@zygotrip.com</a>.</p>
            </section>
          </div>

          <div className="mt-8 pt-6 border-t border-neutral-100 flex gap-4 text-sm">
            <Link href="/legal/terms" className="text-primary-600 hover:underline font-medium">Terms of Service</Link>
            <Link href="/" className="text-neutral-400 hover:text-neutral-600">Back to Home</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
