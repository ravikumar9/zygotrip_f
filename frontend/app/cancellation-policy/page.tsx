import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Cancellation & Refund Policy | ZygoTrip',
  description:
    'Understand ZygoTrip\'s cancellation and refund policy for hotel bookings, bus tickets, cab rides, and holiday packages. Free cancellation available on eligible bookings.',
};

const LAST_UPDATED = 'March 14, 2026';

export default function CancellationPolicyPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <section className="text-white py-14 px-4" style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-3xl md:text-4xl font-black font-heading mb-3">
            Cancellation &amp; Refund Policy
          </h1>
          <p className="text-white/80 text-sm">Last updated: {LAST_UPDATED}</p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-4 py-12 space-y-10 text-[15px] text-neutral-700 leading-relaxed">

        {/* Quick Summary */}
        <div className="bg-green-50 border border-green-200 rounded-2xl p-5">
          <h2 className="text-base font-bold text-green-800 mb-2">✅ Quick Summary</h2>
          <ul className="space-y-1 text-sm text-green-900">
            <li>• Free cancellation available on most bookings up to 24 hours before check-in</li>
            <li>• Refunds are processed within 5–7 business days to the original payment method</li>
            <li>• ZygoTrip Wallet refunds are instant</li>
            <li>• Non-refundable rates are clearly marked before you book</li>
          </ul>
        </div>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">1. Hotel Cancellations</h2>

          <h3 className="font-semibold text-neutral-900 mb-2">1.1 Free Cancellation Bookings</h3>
          <p className="mb-3">
            If your booking is marked <strong>"Free Cancellation"</strong>, you can cancel at no charge
            up to the deadline shown on your booking confirmation (typically 24–48 hours before check-in).
            The full amount will be refunded to your original payment source.
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">1.2 Partially Refundable Bookings</h3>
          <p className="mb-3">
            Some rate plans offer a partial refund on cancellation. The exact refund amount and
            cancellation deadline are displayed on the property and room selection pages before payment.
            Cancelling after the free period will attract a penalty as specified in the rate plan.
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">1.3 Non-Refundable Bookings</h3>
          <p className="mb-3">
            Non-refundable rates are discounted rates where no refund is provided upon cancellation.
            These are clearly labelled <strong>"Non-Refundable"</strong> at the time of booking.
            We strongly recommend purchasing travel insurance for non-refundable bookings.
          </p>

          <h3 className="font-semibold text-neutral-900 mb-2">1.4 No-Show Policy</h3>
          <p>
            If you do not check-in on the booked date and have not cancelled in advance, your
            booking will be treated as a no-show. No refund is applicable for no-shows regardless
            of the original cancellation policy.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">2. Bus Ticket Cancellations</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-neutral-100">
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Time Before Departure</th>
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Cancellation Charge</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['More than 48 hours', '10% of ticket fare'],
                  ['24 – 48 hours', '25% of ticket fare'],
                  ['4 – 24 hours',  '50% of ticket fare'],
                  ['Less than 4 hours', 'No refund'],
                ].map(([time, charge]) => (
                  <tr key={time} className="odd:bg-white even:bg-neutral-50">
                    <td className="px-4 py-2 border border-neutral-200">{time}</td>
                    <td className="px-4 py-2 border border-neutral-200">{charge}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-neutral-500">
            Operator-specific policies may vary. The applicable policy is displayed before you confirm your booking.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">3. Cab Cancellations</h2>
          <ul className="space-y-2 list-disc list-inside">
            <li>Cancellations made more than 1 hour before the scheduled pickup: <strong>Full refund</strong></li>
            <li>Cancellations made 30 minutes to 1 hour before pickup: <strong>50% refund</strong></li>
            <li>Cancellations made less than 30 minutes before pickup or after driver assignment: <strong>No refund</strong></li>
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">4. Holiday Package Cancellations</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-neutral-100">
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Days Before Departure</th>
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Cancellation Charge</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['30+ days', '10% of package cost'],
                  ['15 – 29 days', '25% of package cost'],
                  ['7 – 14 days',  '50% of package cost'],
                  ['0 – 6 days',   '100% (no refund)'],
                ].map(([days, charge]) => (
                  <tr key={days} className="odd:bg-white even:bg-neutral-50">
                    <td className="px-4 py-2 border border-neutral-200">{days}</td>
                    <td className="px-4 py-2 border border-neutral-200">{charge}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">5. Refund Process &amp; Timelines</h2>
          <p className="mb-3">
            Once a cancellation is confirmed, the refund is initiated immediately. Estimated timelines:
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-neutral-100">
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Payment Method</th>
                  <th className="text-left px-4 py-2 border border-neutral-200 font-semibold">Refund Timeline</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['ZygoTrip Wallet', 'Instant'],
                  ['UPI / NetBanking', '3–5 business days'],
                  ['Credit / Debit Card', '5–7 business days'],
                  ['Paytm', '3–5 business days'],
                ].map(([method, time]) => (
                  <tr key={method} className="odd:bg-white even:bg-neutral-50">
                    <td className="px-4 py-2 border border-neutral-200">{method}</td>
                    <td className="px-4 py-2 border border-neutral-200">{time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-neutral-500">
            Bank processing times may vary. If you have not received your refund within 10 business
            days, please contact us at{' '}
            <a href="mailto:support@zygotrip.com" className="text-primary-600 underline">
              support@zygotrip.com
            </a>.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">6. Cancellations by ZygoTrip or Property</h2>
          <p>
            In the rare event that ZygoTrip or the property cancels your booking (due to overbooking,
            force majeure, or other unforeseen circumstances), you will receive a <strong>full refund</strong>{' '}
            within 24 hours. We will also make every effort to find you an alternative property of
            similar or better quality at no extra cost.
          </p>
        </section>

        <section>
          <h2 className="text-xl font-bold text-neutral-900 mb-4">7. How to Cancel</h2>
          <ol className="list-decimal list-inside space-y-2">
            <li>Log in to your ZygoTrip account</li>
            <li>Go to <strong>My Bookings</strong></li>
            <li>Select the booking you wish to cancel</li>
            <li>Click <strong>"Cancel Booking"</strong> and follow the on-screen steps</li>
            <li>You will receive a cancellation confirmation email with the refund details</li>
          </ol>
          <p className="mt-3 text-sm text-neutral-500">
            Alternatively, you can contact our support team at{' '}
            <a href="mailto:support@zygotrip.com" className="text-primary-600 underline">
              support@zygotrip.com
            </a>{' '}
            or call us at <strong>1800-xxx-xxxx</strong> (toll-free, 9 AM – 9 PM IST).
          </p>
        </section>

        <div className="pt-6 border-t border-neutral-100 flex flex-wrap gap-4 text-sm">
          <Link href="/terms" className="text-primary-600 hover:underline">Terms of Service</Link>
          <Link href="/privacy-policy" className="text-primary-600 hover:underline">Privacy Policy</Link>
          <Link href="/help" className="text-primary-600 hover:underline">Help Centre</Link>
        </div>
      </div>
    </main>
  );
}
