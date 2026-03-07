'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  User, MapPin, Calendar, CheckCircle, Clock,
  XCircle, ChevronRight, LogOut, Edit2, Mail, Phone,
} from 'lucide-react';
import { useMyBookings } from '@/hooks/useBooking';
import { updateProfile } from '@/services/auth';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import toast from 'react-hot-toast';
import type { BookingSummary } from '@/types';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  confirmed:       { label: 'Confirmed',       color: 'text-green-600 bg-green-50',     icon: <CheckCircle className="w-4 h-4" /> },
  hold:            { label: 'Hold',            color: 'text-yellow-600 bg-yellow-50',   icon: <Clock className="w-4 h-4" /> },
  payment_pending: { label: 'Payment Pending', color: 'text-blue-600 bg-blue-50',       icon: <Clock className="w-4 h-4" /> },
  cancelled:       { label: 'Cancelled',       color: 'text-red-600 bg-red-50',         icon: <XCircle className="w-4 h-4" /> },
  checked_in:      { label: 'Checked In',      color: 'text-primary-600 bg-primary-50', icon: <CheckCircle className="w-4 h-4" /> },
  checked_out:     { label: 'Checked Out',     color: 'text-neutral-600 bg-neutral-100',icon: <CheckCircle className="w-4 h-4" /> },
  settled:         { label: 'Completed',       color: 'text-green-600 bg-green-50',     icon: <CheckCircle className="w-4 h-4" /> },
};

export default function AccountPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading, logout, refreshUser } = useAuth();

  // Auth guard
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/account/login?next=/account');
    }
  }, [isAuthenticated, authLoading, router]);

  const { data: bookingsData, isLoading: bookingsLoading } = useMyBookings();
  const [editMode, setEditMode] = useState(false);
  const [profileForm, setProfileForm] = useState({
    full_name: user?.full_name ?? '',
    phone: user?.phone ?? '',
  });
  const [saving, setSaving] = useState(false);

  // Keep form in sync when user data loads
  useEffect(() => {
    if (user) {
      setProfileForm({ full_name: user.full_name ?? '', phone: user.phone ?? '' });
    }
  }, [user]);

  const bookings = bookingsData?.pages.flatMap(p => p.results) ?? [];

  const handleLogout = async () => {
    // Use AuthContext logout so header updates immediately without router.refresh()
    await logout();
    toast.success('Signed out successfully.');
    router.push('/');
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateProfile(profileForm);
      await refreshUser(); // Sync AuthContext with updated user data
      toast.success('Profile updated.');
      setEditMode(false);
    } catch {
      toast.error('Failed to update profile.');
    } finally {
      setSaving(false);
    }
  };

  if (authLoading) return <LoadingSpinner />;
  if (!isAuthenticated) return null;

  return (
    <div className="page-booking-bg py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-2xl font-bold text-neutral-900">My Account</h1>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-neutral-500 hover:text-red-600 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Profile Card */}
          <div className="md:col-span-1">
            <div className="bg-white rounded-2xl shadow-card p-6">
              <div className="flex justify-between items-start mb-4">
                <div className="w-14 h-14 bg-primary-600 rounded-full flex items-center justify-center text-white text-2xl font-black">
                  {user?.full_name?.charAt(0)?.toUpperCase() ?? 'U'}
                </div>
                <button
                  onClick={() => setEditMode(!editMode)}
                  className="text-neutral-400 hover:text-primary-600 transition-colors p-1"
                  title="Edit profile"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
              </div>

              {editMode ? (
                <form onSubmit={handleSaveProfile} className="space-y-3">
                  <input
                    type="text"
                    value={profileForm.full_name}
                    onChange={e => setProfileForm({ ...profileForm, full_name: e.target.value })}
                    placeholder=" "
                    className="input-field text-sm"
                  />
                  <input
                    type="tel"
                    value={profileForm.phone}
                    onChange={e => setProfileForm({ ...profileForm, phone: e.target.value })}
                    placeholder=" "
                    className="input-field text-sm"
                  />
                  <div className="flex gap-2">
                    <button type="submit" disabled={saving} className="flex-1 btn-primary text-sm py-2">
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                    <button type="button" onClick={() => setEditMode(false)} className="flex-1 btn-secondary text-sm py-2">
                      Cancel
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-2">
                  <p className="font-bold text-neutral-900 text-base">{user?.full_name}</p>
                  <div className="flex items-center gap-1.5 text-sm text-neutral-500">
                    <Mail className="w-3.5 h-3.5 shrink-0 text-neutral-400" />
                    <span className="truncate">{user?.email}</span>
                  </div>
                  {user?.phone && (
                    <div className="flex items-center gap-1.5 text-sm text-neutral-500">
                      <Phone className="w-3.5 h-3.5 shrink-0 text-neutral-400" />
                      <span>{user.phone}</span>
                    </div>
                  )}
                  <div className="mt-1">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-xs font-medium capitalize">
                      {user?.role?.replace('_', ' ') ?? 'Customer'}
                    </span>
                  </div>
                </div>
              )}

              {/* Quick links */}
              <div className="mt-6 border-t border-neutral-100 pt-4 space-y-1">
                <Link href="/wallet" className="flex items-center justify-between py-2 text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  <span>My Wallet</span>
                  <ChevronRight className="w-4 h-4" />
                </Link>
                <Link href="/hotels" className="flex items-center justify-between py-2 text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  <span>Browse Hotels</span>
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>

          {/* Bookings */}
          <div className="md:col-span-2">
            <h2 className="text-lg font-semibold text-neutral-900 mb-4">My Bookings</h2>

            {bookingsLoading ? (
              <div className="space-y-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="bg-white rounded-2xl shadow-card p-5">
                    <div className="skeleton h-5 w-3/4 rounded mb-2" />
                    <div className="skeleton h-4 w-1/4 rounded mb-4" />
                    <div className="skeleton h-4 w-1/2 rounded" />
                  </div>
                ))}
              </div>
            ) : bookings.length === 0 ? (
              <div className="bg-white rounded-2xl shadow-card p-10 text-center">
                <Calendar className="w-12 h-12 text-neutral-200 mx-auto mb-3" />
                <p className="text-neutral-500 mb-1">No bookings yet</p>
                <p className="text-sm text-neutral-400 mb-4">Explore hotels and make your first booking</p>
                <Link href="/hotels" className="btn-primary">
                  Browse Hotels
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {bookings.map(booking => (
                  <BookingCard key={booking.uuid} booking={booking} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function BookingCard({ booking }: { booking: BookingSummary }) {
  const status = STATUS_CONFIG[booking.status] || {
    label: booking.status,
    color: 'text-neutral-600 bg-neutral-100',
    icon: <Clock className="w-4 h-4" />,
  };

  const fmt = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch { return dateStr; }
  };

  return (
    <div className="bg-white rounded-2xl shadow-card p-5 hover:shadow-card-hover transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <div className="min-w-0 flex-1 pr-3">
          <p className="font-semibold text-neutral-900 truncate">{booking.property_name}</p>
          <p className="text-xs text-neutral-400 mt-0.5 font-mono">{booking.public_booking_id}</p>
        </div>
        <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold shrink-0 ${status.color}`}>
          {status.icon}
          {status.label}
        </span>
      </div>

      <div className="flex flex-wrap gap-4 text-sm text-neutral-600 mb-4">
        <div className="flex items-center gap-1.5">
          <Calendar className="w-4 h-4 text-neutral-400" />
          <span>{fmt(booking.check_in)} → {fmt(booking.check_out)}</span>
        </div>
        {booking.city_name && (
          <div className="flex items-center gap-1.5">
            <MapPin className="w-4 h-4 text-neutral-400" />
            <span>{booking.city_name}</span>
          </div>
        )}
      </div>

      <div className="flex justify-between items-center">
        <p className="font-bold text-neutral-900">
          ₹{parseFloat(booking.total_amount).toLocaleString('en-IN')}
        </p>
        {['hold', 'payment_pending', 'confirmed'].includes(booking.status) && (
          <span className="text-xs text-neutral-400 bg-neutral-50 px-2.5 py-1 rounded-full">
            Cancellation available
          </span>
        )}
      </div>
    </div>
  );
}
