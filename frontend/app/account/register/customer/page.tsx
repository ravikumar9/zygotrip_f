'use client';

import Link from 'next/link';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import RegisterForm from '@/components/auth/RegisterForm';

const BENEFITS = [
  'Book hotels across 50+ Indian cities',
  'Exclusive member-only deals & early access',
  'Instant wallet cashback on every booking',
  'Manage all trips from one dashboard',
];

export default function CustomerRegisterPage() {
  return (
    <div className="min-h-screen page-booking-bg flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-6">
          <Link href="/" className="inline-block mb-4">
            <span
              className="text-2xl font-black text-primary-600 font-heading"
            >
              Zygo<span className="text-accent-500">Trip</span>
            </span>
          </Link>

          <div className="inline-flex items-center gap-2 bg-primary-50 text-primary-700 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide mb-3">
            🧳 Traveller Account
          </div>

          <h1 className="text-2xl font-bold text-neutral-900">Start your journey</h1>
          <p className="text-neutral-500 mt-1 text-sm">
            Already have an account?{' '}
            <Link href="/account/login" className="text-primary-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>

        {/* Benefits */}
        <div className="bg-primary-50 rounded-xl px-4 py-3 mb-4 space-y-1.5">
          {BENEFITS.map(b => (
            <div key={b} className="flex items-center gap-2 text-xs text-primary-800">
              <CheckCircle2 size={13} className="text-primary-500 shrink-0" />
              {b}
            </div>
          ))}
        </div>

        {/* Form */}
        <div className="bg-white/80 rounded-2xl shadow-card p-8">
          <RegisterForm role="traveler" roleLabel="Traveller" redirectTo="/" />
        </div>

        <Link
          href="/account/register"
          className="flex items-center justify-center gap-1.5 mt-4 text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
        >
          <ArrowLeft size={12} />
          Change account type
        </Link>
      </div>
    </div>
  );
}
