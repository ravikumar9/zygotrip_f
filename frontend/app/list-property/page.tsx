'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

const VENDOR_ROLES = [
  {
    slug: 'property',
    label: 'Property Owner',
    icon: '🏨',
    desc: 'List your hotel, resort, homestay or villa',
    color: 'border-amber-200 hover:border-amber-500 hover:bg-amber-50',
  },
  {
    slug: 'cab',
    label: 'Cab Operator',
    icon: '🚗',
    desc: 'Offer car rental & airport transfer services',
    color: 'border-green-200 hover:border-green-500 hover:bg-green-50',
  },
  {
    slug: 'bus',
    label: 'Bus Operator',
    icon: '🚌',
    desc: 'Manage intercity and local bus routes',
    color: 'border-blue-200 hover:border-blue-500 hover:bg-blue-50',
  },
  {
    slug: 'package',
    label: 'Tour Operator',
    icon: '🗺️',
    desc: 'Create and sell curated travel packages',
    color: 'border-purple-200 hover:border-purple-500 hover:bg-purple-50',
  },
] as const;

const PERKS = [
  'Free listing — no upfront fees',
  'Instant booking confirmation',
  'Dedicated vendor dashboard',
  'Secure payouts to your bank account',
];

export default function ListPropertyPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen page-booking-bg flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-block">
            <span
              className="text-2xl font-black text-primary-600 font-heading"
            >
              Zygo<span className="text-accent-500">Trip</span>
            </span>
          </Link>
          <h1 className="text-2xl font-bold text-neutral-900 mt-4">List your business</h1>
          <p className="text-neutral-500 mt-1 text-sm">
            Already have an account?{' '}
            <Link href="/account/login" className="text-primary-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>

        {/* Perks */}
        <div className="bg-primary-50 rounded-xl px-4 py-3 mb-4 space-y-1.5">
          {PERKS.map(perk => (
            <div key={perk} className="flex items-center gap-2 text-xs text-primary-800">
              <CheckCircle2 size={13} className="text-primary-500 shrink-0" />
              {perk}
            </div>
          ))}
        </div>

        {/* Role selector */}
        <div className="bg-white rounded-2xl shadow-card p-6">
          <p className="text-sm font-semibold text-neutral-600 mb-4">
            What type of business do you operate?
          </p>
          <div className="space-y-2">
            {VENDOR_ROLES.map(role => (
              <button
                key={role.slug}
                type="button"
                onClick={() => router.push(`/account/register/${role.slug}`)}
                className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-xl border-2 transition-all text-left group ${role.color}`}
              >
                <span className="text-2xl shrink-0">{role.icon}</span>
                <span className="flex-1 min-w-0">
                  <span className="font-semibold text-neutral-800 block">{role.label}</span>
                  <span className="text-xs text-neutral-400">{role.desc}</span>
                </span>
                <ArrowRight
                  size={16}
                  className="text-neutral-300 group-hover:text-neutral-500 shrink-0 transition-colors"
                />
              </button>
            ))}
          </div>
        </div>

        <p className="text-center mt-4 text-xs text-neutral-400">
          Looking to travel instead?{' '}
          <Link href="/account/register/customer" className="text-primary-600 hover:underline">
            Create a traveller account
          </Link>
        </p>
      </div>
    </div>
  );
}
