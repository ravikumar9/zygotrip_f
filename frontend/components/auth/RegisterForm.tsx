'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, UserPlus, Check } from 'lucide-react';
import { register } from '@/services/auth';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';

// ── Types ────────────────────────────────────────────────────────────────────

export type RoleType =
  | 'traveler'
  | 'property_owner'
  | 'cab_owner'
  | 'bus_operator'
  | 'package_provider';

export interface RegisterFormProps {
  role: RoleType;
  roleLabel: string;
  /** Extra fields specific to this role (rendered between phone and password) */
  extraFields?: React.ReactNode;
  /** Where to redirect after successful registration */
  redirectTo?: string;
}

// ── Password strength rules ───────────────────────────────────────────────────

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'Contains a number', test: (p: string) => /\d/.test(p) },
  { label: 'Contains a letter', test: (p: string) => /[a-zA-Z]/.test(p) },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function RegisterForm({
  role,
  roleLabel,
  extraFields,
  redirectTo = '/',
}: RegisterFormProps) {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password.length < 8) {
      toast.error('Password must be at least 8 characters.');
      return;
    }
    setLoading(true);
    try {
      await register(form.full_name, form.email, form.password, role, form.phone || undefined);
      await refreshUser();
      toast.success(`Account created! Welcome to ZygoTrip.`);
      router.push(redirectTo);
    } catch (err: any) {
      const data = err?.response?.data;
      const msg =
        data?.error?.message ||
        data?.email?.[0] ||
        data?.full_name?.[0] ||
        'Registration failed. Please try again.';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Full name */}
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Full Name *</label>
        <input
          type="text"
          required
          value={form.full_name}
          onChange={e => setForm({ ...form, full_name: e.target.value })}
          placeholder=" "
          className="input-field"
          autoComplete="name"
        />
      </div>

      {/* Email */}
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Email Address *</label>
        <input
          type="email"
          required
          value={form.email}
          onChange={e => setForm({ ...form, email: e.target.value })}
          placeholder=" "
          className="input-field"
          autoComplete="email"
        />
      </div>

      {/* Phone */}
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Phone Number</label>
        <input
          type="tel"
          value={form.phone}
          onChange={e => setForm({ ...form, phone: e.target.value })}
          placeholder=" "
          className="input-field"
          autoComplete="tel"
        />
      </div>

      {/* Slot for role-specific fields */}
      {extraFields}

      {/* Password */}
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Password *</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            required
            value={form.password}
            onChange={e => setForm({ ...form, password: e.target.value })}
            placeholder="Create a strong password"
            className="input-field pr-10"
            autoComplete="new-password"
          />
          <button
            type="button"
            onClick={() => setShowPassword(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>

        {/* Password strength */}
        {form.password && (
          <div className="mt-2 space-y-1">
            {PASSWORD_RULES.map(rule => (
              <div
                key={rule.label}
                className={`flex items-center gap-2 text-xs ${
                  rule.test(form.password) ? 'text-green-600' : 'text-neutral-400'
                }`}
              >
                <Check
                  className={`w-3 h-3 ${rule.test(form.password) ? 'text-green-500' : 'text-neutral-300'}`}
                />
                {rule.label}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={loading}
        className="w-full btn-primary py-3 text-base flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="white" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="white"
                d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z"
              />
            </svg>
            Creating account…
          </>
        ) : (
          <>
            <UserPlus className="w-5 h-5" />
            Create {roleLabel} Account
          </>
        )}
      </button>

      <p className="text-center text-xs text-neutral-400 pt-1">
        By registering you agree to our{' '}
        <Link href="/legal/terms" className="underline hover:text-neutral-600">
          Terms
        </Link>{' '}
        and{' '}
        <Link href="/legal/privacy" className="underline hover:text-neutral-600">
          Privacy Policy
        </Link>
        .
      </p>
    </form>
  );
}
