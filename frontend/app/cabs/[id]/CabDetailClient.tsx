'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, MapPin, Car, Users, Clock, Shield, Star,
  Phone, Navigation, Loader2, CheckCircle, AlertCircle,
} from 'lucide-react';
import { getCabDetail } from '@/services/cabs';
import api from '@/services/api';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import toast from 'react-hot-toast';
import type { Cab } from '@/types/cabs';

interface DriverInfo {
  name: string;
  phone: string;
  rating: number;
  trips_completed: number;
  vehicle_number: string;
  otp: string;
}

interface TrackingState {
  status: 'searching' | 'driver_found' | 'driver_accepted' | 'en_route' | 'arrived' | 'in_trip' | 'completed';
  driver?: DriverInfo;
  eta_minutes?: number;
  lat?: number;
  lng?: number;
}

const STATUS_LABELS: Record<string, { label: string; color: string; description: string }> = {
  searching:       { label: 'Finding Driver',    color: 'text-amber-600',  description: 'Looking for the nearest available driver...' },
  driver_found:    { label: 'Driver Found',      color: 'text-blue-600',   description: 'A driver has been matched to your ride.' },
  driver_accepted: { label: 'Driver On Way',     color: 'text-green-600',  description: 'Your driver is heading to the pickup point.' },
  en_route:        { label: 'Driver Arriving',   color: 'text-green-600',  description: 'Your driver is almost at the pickup point.' },
  arrived:         { label: 'Driver Arrived',     color: 'text-green-700',  description: 'Your driver is waiting at the pickup point.' },
  in_trip:         { label: 'Trip in Progress',  color: 'text-primary-600', description: 'You are on your way to the destination.' },
  completed:       { label: 'Trip Completed',    color: 'text-neutral-600', description: 'Thank you for riding with ZygoTrip!' },
};

export default function CabDetailClient() {
  const { formatPrice } = useFormatPrice();
  const params = useParams();
  const router = useRouter();
  const cabId = Number(params.id);

  const [cab, setCab] = useState<Cab | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Booking form
  const [pickup, setPickup] = useState('');
  const [dropoff, setDropoff] = useState('');
  const [pickupDate, setPickupDate] = useState('');
  const [pickupTime, setPickupTime] = useState('');
  const [estimatedKm, setEstimatedKm] = useState(0);
  const [estimatedFare, setEstimatedFare] = useState(0);
  const [booking, setBooking] = useState(false);

  // Tracking state
  const [tracking, setTracking] = useState<TrackingState | null>(null);
  const [bookingId, setBookingId] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!cabId) return;
    (async () => {
      try {
        const data = await getCabDetail(cabId);
        setCab(data);
      } catch {
        setError('Cab not found');
      } finally {
        setLoading(false);
      }
    })();
  }, [cabId]);

  // Estimate fare when km changes
  useEffect(() => {
    if (!cab || estimatedKm <= 0) { setEstimatedFare(0); return; }
    const base = cab.price_per_km * estimatedKm;
    const driverAllowance = 200;
    const gst = Math.round(base * 0.05);
    setEstimatedFare(base + driverAllowance + gst);
  }, [estimatedKm, cab]);

  // Poll tracking status
  useEffect(() => {
    if (!bookingId) return;
    const poll = async () => {
      try {
        const { data } = await api.get(`/cabs/bookings/${bookingId}/tracking/`);
        setTracking(data);
        if (data.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch { /* ignore polling errors */ }
    };
    poll();
    pollRef.current = setInterval(poll, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [bookingId]);

  const handleBook = async () => {
    if (!cab || !pickup || !dropoff) {
      toast.error('Please enter pickup and drop-off locations');
      return;
    }
    setBooking(true);
    try {
      const { data } = await api.post('/cabs/book/', {
        cab_id: cab.id,
        pickup_address: pickup,
        dropoff_address: dropoff,
        pickup_date: pickupDate || undefined,
        pickup_time: pickupTime || undefined,
      });
      setBookingId(data.booking_uuid || data.uuid);
      setTracking({ status: 'searching' });
      toast.success('Booking confirmed! Finding a driver...');
    } catch {
      toast.error('Booking failed. Please try again.');
    } finally {
      setBooking(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-neutral-400" />
      </div>
    );
  }

  if (error || !cab) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-5xl mb-4">🚗</p>
          <h2 className="text-xl font-bold text-neutral-700">{error || 'Cab not found'}</h2>
          <Link href="/cabs" className="mt-4 text-primary-600 font-semibold hover:underline block">← Back to search</Link>
        </div>
      </div>
    );
  }

  const statusInfo = tracking ? STATUS_LABELS[tracking.status] || STATUS_LABELS.searching : null;

  return (
    <div className="min-h-screen page-listing-bg">
      {/* Top bar */}
      <div className="bg-white border-b sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-4">
          <button onClick={() => router.back()} className="text-neutral-500 hover:text-neutral-800">
            <ArrowLeft size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-neutral-900 text-sm truncate">{cab.name}</h1>
            <p className="text-xs text-neutral-400">{cab.category_label || cab.category} · {cab.seats} seats</p>
          </div>
          <div className="text-right">
            <p className="text-lg font-black text-neutral-900">{formatPrice(cab.price_per_km)}<span className="text-xs font-normal text-neutral-400">/km</span></p>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">

          {/* Left — Vehicle details + map placeholder */}
          <div className="space-y-5">
            {/* Vehicle card */}
            <div className="bg-white rounded-2xl shadow-card overflow-hidden">
              <div className="h-56 bg-neutral-100 flex items-center justify-center">
                {cab.image_url ? (
                  <img src={cab.image_url} alt={cab.name} className="w-full h-full object-cover" />
                ) : (
                  <Car size={64} className="text-neutral-300" />
                )}
              </div>
              <div className="p-5">
                <h2 className="text-xl font-black text-neutral-900 mb-2">{cab.name}</h2>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-neutral-50 rounded-xl p-3 text-center border border-neutral-100">
                    <Users size={16} className="mx-auto text-primary-500 mb-1" />
                    <p className="text-xs font-semibold text-neutral-700">{cab.seats} Seats</p>
                  </div>
                  <div className="bg-neutral-50 rounded-xl p-3 text-center border border-neutral-100">
                    <Car size={16} className="mx-auto text-primary-500 mb-1" />
                    <p className="text-xs font-semibold text-neutral-700">{cab.category_label || cab.category}</p>
                  </div>
                  <div className="bg-neutral-50 rounded-xl p-3 text-center border border-neutral-100">
                    <Shield size={16} className="mx-auto text-green-500 mb-1" />
                    <p className="text-xs font-semibold text-neutral-700">Verified</p>
                  </div>
                  <div className="bg-neutral-50 rounded-xl p-3 text-center border border-neutral-100">
                    <Clock size={16} className="mx-auto text-amber-500 mb-1" />
                    <p className="text-xs font-semibold text-neutral-700">24/7</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Live tracking panel */}
            {tracking && (
              <div className="bg-white rounded-2xl shadow-card p-5">
                <h3 className="font-bold text-neutral-800 text-sm mb-4">Live Tracking</h3>

                {/* Status progress */}
                <div className="flex items-center gap-2 mb-5">
                  {['searching', 'driver_found', 'driver_accepted', 'arrived', 'in_trip', 'completed'].map((step, i) => {
                    const stepOrder = ['searching', 'driver_found', 'driver_accepted', 'arrived', 'in_trip', 'completed'];
                    const currentOrder = stepOrder.indexOf(tracking.status);
                    const isActive = i <= currentOrder;
                    return (
                      <div key={step} className="flex items-center flex-1">
                        <div className={`w-3 h-3 rounded-full shrink-0 ${isActive ? 'bg-green-500' : 'bg-neutral-200'}`} />
                        {i < stepOrder.length - 1 && (
                          <div className={`h-0.5 flex-1 ${isActive && i < currentOrder ? 'bg-green-500' : 'bg-neutral-200'}`} />
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Status message */}
                <div className={`flex items-start gap-3 rounded-xl p-4 mb-4 ${
                  tracking.status === 'searching' ? 'bg-amber-50 border border-amber-200' :
                  tracking.status === 'completed' ? 'bg-neutral-50 border border-neutral-200' :
                  'bg-green-50 border border-green-200'
                }`}>
                  {tracking.status === 'searching' ? (
                    <Loader2 size={18} className="animate-spin text-amber-500 shrink-0 mt-0.5" />
                  ) : tracking.status === 'completed' ? (
                    <CheckCircle size={18} className="text-green-500 shrink-0 mt-0.5" />
                  ) : (
                    <Navigation size={18} className="text-green-600 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className={`font-semibold text-sm ${statusInfo?.color}`}>{statusInfo?.label}</p>
                    <p className="text-xs text-neutral-500 mt-0.5">{statusInfo?.description}</p>
                    {tracking.eta_minutes != null && tracking.eta_minutes > 0 && (
                      <p className="text-xs font-bold text-green-700 mt-1">ETA: {tracking.eta_minutes} min</p>
                    )}
                  </div>
                </div>

                {/* Map placeholder */}
                <div className="h-48 bg-neutral-100 rounded-xl flex items-center justify-center border border-neutral-200">
                  <div className="text-center text-neutral-400">
                    <MapPin size={28} className="mx-auto mb-2 opacity-40" />
                    <p className="text-xs">Live map tracking</p>
                    {tracking.lat && tracking.lng && (
                      <p className="text-[10px] mt-1">Driver: {tracking.lat.toFixed(4)}, {tracking.lng.toFixed(4)}</p>
                    )}
                  </div>
                </div>

                {/* Driver info */}
                {tracking.driver && (
                  <div className="mt-4 bg-neutral-50 rounded-xl p-4 border border-neutral-200">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                          <Car size={18} className="text-primary-600" />
                        </div>
                        <div>
                          <p className="font-semibold text-neutral-800 text-sm">{tracking.driver.name}</p>
                          <div className="flex items-center gap-2 text-xs text-neutral-400">
                            <span className="flex items-center gap-0.5"><Star size={10} fill="#f59e0b" stroke="none" /> {tracking.driver.rating}</span>
                            <span>·</span>
                            <span>{tracking.driver.trips_completed} trips</span>
                          </div>
                        </div>
                      </div>
                      <a href={`tel:${tracking.driver.phone}`} className="p-2 rounded-full bg-green-50 text-green-600 hover:bg-green-100">
                        <Phone size={16} />
                      </a>
                    </div>
                    <div className="flex items-center justify-between text-xs bg-white rounded-lg px-3 py-2 border border-neutral-100">
                      <span className="text-neutral-500">Vehicle: <span className="font-semibold text-neutral-700">{tracking.driver.vehicle_number}</span></span>
                      <span className="text-neutral-500">OTP: <span className="font-bold text-primary-600 text-sm">{tracking.driver.otp}</span></span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Features */}
            <div className="bg-white rounded-2xl shadow-card p-5">
              <h3 className="font-bold text-neutral-800 text-sm mb-3">Inclusions &amp; Policies</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {[
                  'Fuel charges included', 'Driver allowance ₹200',
                  'Toll/parking extra', 'GST @5% included',
                  '24/7 customer support', 'Clean & sanitized vehicles',
                ].map((item) => (
                  <div key={item} className="flex items-center gap-2 text-xs text-neutral-600 bg-neutral-50 rounded-lg px-3 py-2.5 border border-neutral-100">
                    <CheckCircle size={12} className="text-green-500 shrink-0" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right — Booking panel */}
          <div>
            <div className="booking-panel p-5 sticky top-20">
              <h3 className="font-bold text-neutral-800 mb-4">Book This Cab</h3>

              <div className="space-y-3 mb-4">
                <div>
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Pickup Location *</label>
                  <div className="flex items-center gap-2 bg-neutral-50 rounded-xl px-3 py-2.5 border border-neutral-200 focus-within:border-primary-400">
                    <MapPin size={14} className="text-green-500 shrink-0" />
                    <input
                      type="text"
                      value={pickup}
                      onChange={(e) => setPickup(e.target.value)}
                      placeholder="Enter pickup address"
                      className="bg-transparent text-sm text-neutral-700 outline-none w-full"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Drop-off Location *</label>
                  <div className="flex items-center gap-2 bg-neutral-50 rounded-xl px-3 py-2.5 border border-neutral-200 focus-within:border-primary-400">
                    <MapPin size={14} className="text-red-500 shrink-0" />
                    <input
                      type="text"
                      value={dropoff}
                      onChange={(e) => setDropoff(e.target.value)}
                      placeholder="Enter drop-off address"
                      className="bg-transparent text-sm text-neutral-700 outline-none w-full"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">Date</label>
                    <input
                      type="date"
                      value={pickupDate}
                      onChange={(e) => setPickupDate(e.target.value)}
                      className="w-full bg-neutral-50 rounded-xl px-3 py-2.5 border border-neutral-200 text-sm text-neutral-700 outline-none focus:border-primary-400"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">Time</label>
                    <input
                      type="time"
                      value={pickupTime}
                      onChange={(e) => setPickupTime(e.target.value)}
                      className="w-full bg-neutral-50 rounded-xl px-3 py-2.5 border border-neutral-200 text-sm text-neutral-700 outline-none focus:border-primary-400"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Estimated Distance (km)</label>
                  <input
                    type="number"
                    min={1}
                    max={2000}
                    value={estimatedKm || ''}
                    onChange={(e) => setEstimatedKm(Number(e.target.value))}
                    placeholder="Enter approx. distance"
                    className="w-full bg-neutral-50 rounded-xl px-3 py-2.5 border border-neutral-200 text-sm text-neutral-700 outline-none focus:border-primary-400"
                  />
                </div>
              </div>

              {/* Fare estimate */}
              {estimatedFare > 0 && (
                <div className="bg-neutral-50 rounded-xl p-3.5 mb-4 border border-neutral-200">
                  <div className="flex justify-between text-xs text-neutral-500 mb-1">
                    <span>{formatPrice(cab.price_per_km)}/km × {estimatedKm} km</span>
                    <span>{formatPrice(cab.price_per_km * estimatedKm)}</span>
                  </div>
                  <div className="flex justify-between text-xs text-neutral-500 mb-1">
                    <span>Driver allowance</span>
                    <span>₹200</span>
                  </div>
                  <div className="flex justify-between text-xs text-neutral-500 mb-2">
                    <span>GST @5%</span>
                    <span>{formatPrice(Math.round(cab.price_per_km * estimatedKm * 0.05))}</span>
                  </div>
                  <div className="pt-2 border-t border-neutral-200 flex justify-between">
                    <span className="font-bold text-xs text-neutral-700">Estimated Total</span>
                    <span className="font-black text-sm text-neutral-900">{formatPrice(estimatedFare)}</span>
                  </div>
                  <p className="text-[10px] text-neutral-400 mt-1 text-center">Toll & parking charges extra</p>
                </div>
              )}

              <button
                onClick={handleBook}
                disabled={booking || !pickup || !dropoff || !!tracking}
                className="btn-primary w-full py-3 text-sm"
              >
                {booking ? (
                  <><Loader2 size={14} className="animate-spin" /> Booking...</>
                ) : tracking ? (
                  'Ride Booked ✓'
                ) : (
                  'Book Cab'
                )}
              </button>

              <p className="text-center text-xs text-neutral-400 mt-3">🔒 Secure booking · Verified drivers</p>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
