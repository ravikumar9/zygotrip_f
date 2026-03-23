'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, UserPlus, Check, ShieldCheck, RefreshCw } from 'lucide-react';
import { register, verifyRegistrationOtp, resendRegistrationOtp } from '@/services/auth';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';

export type RoleType = 'traveler' | 'property_owner' | 'cab_owner' | 'bus_operator' | 'package_provider';

export interface RegisterFormProps {
  role: RoleType;
  roleLabel: string;
  extraFields?: React.ReactNode;
  redirectTo?: string;
}

const PASSWORD_RULES = [
  { label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
  { label: 'Contains a number', test: (p: string) => /\d/.test(p) },
  { label: 'Contains a letter', test: (p: string) => /[a-zA-Z]/.test(p) },
];

export default function RegisterForm({ role, roleLabel, extraFields, redirectTo = '/' }: RegisterFormProps) {
  const router = useRouter();
  const { refreshUser } = useAuth();

  const [step, setStep] = useState<'register' | 'verify'>( 'register');
  const [userId, setUserId] = useState<number | null>(null);
  const [userEmail, setUserEmail] = useState('');
  const [userPhone, setUserPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [form, setForm] = useState({ full_name: '', email: '', phone: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password.length < 8) { toast.error('Password must be at least 8 characters.'); return; }
    setLoading(true);
    setFieldErrors({});
    try {
      const res = await register(form.full_name, form.email, form.password, role, form.phone || undefined);
      const data = res as unknown as { user_id?: number; email?: string; phone?: string };
      if (data.user_id) {
        setUserId(data.user_id);
        setUserEmail(data.email || form.email);
        setUserPhone(data.phone || form.phone);
        setStep('verify');
        toast.success('OTP sent to your phone and email!');
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: Record<string, unknown> } };
      const data = e?.response?.data;
      const errMsg = (data?.error as { message?: unknown })?.message;
      if (errMsg && typeof errMsg === 'object') {
        const inline: Record<string, string> = {};
        Object.entries(errMsg as Record<string, unknown>).forEach(([k, v]) => {
          inline[k] = Array.isArray(v) ? String(v[0]) : String(v);
        });
        setFieldErrors(inline);
        toast.error(Object.values(inline)[0] || 'Please fix the errors.');
      } else {
        toast.error(typeof errMsg === 'string' ? errMsg : 'Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId || otp.length !== 6) { toast.error('Please enter the 6-digit OTP.'); return; }
    setLoading(true);
    try {
      await verifyRegistrationOtp(userId, otp);
      await refreshUser();
      toast.success('Account verified! Welcome to ZygoTrip 🎉');
      router.push(redirectTo);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } };
      toast.error(e?.response?.data?.error || 'Invalid OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (!userId) return;
    setResending(true);
    try {
      await resendRegistrationOtp(userId);
      toast.success('OTP resent successfully!');
    } catch {
      toast.error('Failed to resend OTP. Please try again.');
    } finally {
      setResending(false);
    }
  };

  if (step === 'verify') {
    return (
      <div className="space-y-5">
        <div className="text-center">
          <ShieldCheck className="w-12 h-12 text-primary-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-neutral-900">Verify your account</h3>
          <p className="text-sm text-neutral-500 mt-1">
            OTP sent to {userPhone && <span className="font-medium">{userPhone}</span>}
            {userPhone && userEmail && ' and '}
            {userEmail && <span className="font-medium">{userEmail}</span>}
          </p>
        </div>

        <form onSubmit={handleVerifyOtp} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1.5">Enter 6-digit OTP</label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              className="input-field text-center text-2xl font-bold tracking-widest"
              autoComplete="one-time-code"
            />
          </div>

          <button
            type="submit"
            disabled={loading || otp.length !== 6}
            className="w-full btn-primary py-3 text-base flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Verify & Continue'}
          </button>
        </form>

        <div className="text-center">
          <button
            onClick={handleResendOtp}
            disabled={resending}
            className="text-sm text-primary-600 hover:underline flex items-center gap-1 mx-auto"
          >
            <RefreshCw size={13} className={resending ? 'animate-spin' : ''} />
            {resending ? 'Resending...' : 'Resend OTP'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleRegister} className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Full Name *</label>
        <input type="text" required value={form.full_name}
          onChange={e => { setForm({ ...form, full_name: e.target.value }); setFieldErrors(p => ({ ...p, full_name: '' })); }}
          placeholder="Your full name" className={'input-field' + (fieldErrors.full_name ? ' border-red-400' : '')} autoComplete="name" />
        {fieldErrors.full_name && <p className="text-red-500 text-xs mt-1">{fieldErrors.full_name}</p>}
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Email Address *</label>
        <input type="email" required value={form.email}
          onChange={e => { setForm({ ...form, email: e.target.value }); setFieldErrors(p => ({ ...p, email: '' })); }}
          placeholder="you@example.com" className={'input-field' + (fieldErrors.email ? ' border-red-400' : '')} autoComplete="email" />
        {fieldErrors.email && <p className="text-red-500 text-xs mt-1">{fieldErrors.email}</p>}
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Phone Number *</label>
        <input type="tel" required value={form.phone}
          onChange={e => { setForm({ ...form, phone: e.target.value }); setFieldErrors(p => ({ ...p, phone: '' })); }}
          placeholder="+91 98765 43210" className={'input-field' + (fieldErrors.phone ? ' border-red-400' : '')} autoComplete="tel" />
        {fieldErrors.phone && <p className="text-red-500 text-xs mt-1">{fieldErrors.phone}</p>}
        <p className="text-xs text-neutral-400 mt-1">OTP will be sent to this number for verification</p>
      </div>

      {extraFields}

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1.5">Password *</label>
        <div className="relative">
          <input type={showPassword ? 'text' : 'password'} required value={form.password}
            onChange={e => setForm({ ...form, password: e.target.value })}
            placeholder="Create a strong password" className="input-field pr-10" autoComplete="new-password" />
          <button type="button" onClick={() => setShowPassword(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600">
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {form.password && (
          <div className="mt-2 space-y-1">
            {PASSWORD_RULES.map(rule => (
              <div key={rule.label} className={'flex items-center gap-2 text-xs ' + (rule.test(form.password) ? 'text-green-600' : 'text-neutral-400')}>
                <Check className={'w-3 h-3 ' + (rule.test(form.password) ? 'text-green-500' : 'text-neutral-300')} />
                {rule.label}
              </div>
            ))}
          </div>
        )}
      </div>

      <button type="submit" disabled={loading}
        className="w-full btn-primary py-3 text-base flex items-center justify-center gap-2 disabled:opacity-50">
        {loading ? 'Creating account...' : <><UserPlus className="w-5 h-5" />Create {roleLabel} Account</>}
      </button>

      <p className="text-center text-xs text-neutral-400 pt-1">
        By registering you agree to our{' '}
        <Link href="/legal/terms" className="underline hover:text-neutral-600">Terms</Link>
        {' & '}
        <Link href="/legal/privacy" className="underline hover:text-neutral-600">Privacy Policy</Link>.
      </p>
    </form>
  );
}
