'use client';

import Link from 'next/link';
import { ArrowLeft, CheckCircle2 } from 'lucide-react';
import RegisterForm from '@/components/auth/RegisterForm';

const BENEFITS = [
  'Create fully customised holiday packages',
  'Bundle hotels, cabs & activities seamlessly',
  'Reach millions of ZygoTrip travellers',
  'Commission-based earnings with instant payouts',
];

export default function PackageRegisterPage() {
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

          <div className="inline-flex items-center gap-2 bg-purple-50 text-purple-700 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide mb-3">
            🗺️ Tour Operator Account
          </div>

          <h1 className="text-2xl font-bold text-neutral-900">Create travel packages</h1>
          <p className="text-neutral-500 mt-1 text-sm">
            Already registered?{' '}
            <Link href="/account/login" className="text-primary-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>

        {/* Benefits */}
        <div className="bg-purple-50 rounded-xl px-4 py-3 mb-4 space-y-1.5">
          {BENEFITS.map(b => (
            <div key={b} className="flex items-center gap-2 text-xs text-purple-800">
              <CheckCircle2 size={13} className="text-purple-500 shrink-0" />
              {b}
            </div>
          ))}
        </div>

        {/* Form */}
        <div className="bg-white rounded-2xl shadow-card p-8">
          <RegisterForm
            role="package_provider"
            roleLabel="Package Provider"
            redirectTo="/dashboard"
            extraFields={
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                  Agency / Company Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Incredible India Tours"
                  className="input-field"
                  autoComplete="organization"
                />
                <p className="text-xs text-neutral-400 mt-1">
                  Create and publish packages from your operator dashboard after signup.
                </p>
              </div>
            }
          />
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
