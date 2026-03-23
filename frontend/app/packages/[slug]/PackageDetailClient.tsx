'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, MapPin, Calendar, Users, Clock, Star, Shield,
  ChevronDown, ChevronUp, Check, Plus, Minus, Loader2,
  Sun, Moon, Coffee, Utensils, Camera, Mountain, Home,
} from 'lucide-react';
import { getPackageDetail } from '@/services/packages';
import api from '@/services/api';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import toast from 'react-hot-toast';
import { format, parseISO, addDays } from 'date-fns';
import type { TravelPackage, PackageItineraryDay } from '@/types/packages';

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  sightseeing: <Camera size={14} />,
  meal: <Utensils size={14} />,
  adventure: <Mountain size={14} />,
  transfer: <MapPin size={14} />,
  stay: <Home size={14} />,
  default: <Sun size={14} />,
};

interface AvailabilitySlot {
  date: string;
  available_slots: number;
  price_adult: number;
  price_child: number;
  season: string;
  is_sold_out: boolean;
}

export default function PackageDetailClient() {
  const { formatPrice } = useFormatPrice();
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;

  const [pkg, setPkg] = useState<TravelPackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedDay, setExpandedDay] = useState<number | null>(0);

  // Booking form
  const [selectedDate, setSelectedDate] = useState('');
  const [adults, setAdults] = useState(2);
  const [children, setChildren] = useState(0);
  const [bookingLoading, setBookingLoading] = useState(false);

  // Customization
  const [hotelUpgrade, setHotelUpgrade] = useState<'standard' | 'premium' | 'luxury'>('standard');
  const [mealUpgrade, setMealUpgrade] = useState(false);
  const [selectedAddons, setSelectedAddons] = useState<number[]>([]);

  // Availability calendar
  const [availability, setAvailability] = useState<AvailabilitySlot[]>([]);
  const [calLoading, setCalLoading] = useState(false);
  const [bookingReference, setBookingReference] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    (async () => {
      try {
        const data = await getPackageDetail(slug);
        setPkg(data);
      } catch {
        setError('Package not found');
      } finally {
        setLoading(false);
      }
    })();
  }, [slug]);

  // Fetch availability when package loads
  useEffect(() => {
    if (!pkg) return;
    setCalLoading(true);
    const start = format(new Date(), 'yyyy-MM-dd');
    const end = format(addDays(new Date(), 90), 'yyyy-MM-dd');
    api.get(`/packages/${pkg.id}/availability/`, { params: { start_date: start, end_date: end } })
      .then(({ data }: { data: { calendar?: AvailabilitySlot[] } | AvailabilitySlot[] }) => setAvailability((Array.isArray(data) ? data : data.calendar) || []))
      .catch(() => {})
      .finally(() => setCalLoading(false));
  }, [pkg]);

  const handleBook = async () => {
    if (!pkg || !selectedDate) {
      toast.error('Please select a travel date');
      return;
    }
    setBookingLoading(true);
    try {
      const { data } = await api.post('/packages/book/', {
        package_id: pkg.id,
        departure_date: selectedDate,
        adults,
        children,
        hotel_upgrade: hotelUpgrade !== 'standard' ? hotelUpgrade : undefined,
        meal_upgrade: mealUpgrade || undefined,
        addon_ids: selectedAddons.length > 0 ? selectedAddons : undefined,
      });
      setBookingReference(data.public_booking_id || data.booking_id || data.uuid || null);
      toast.success(`Package booked successfully${data.public_booking_id ? `: ${data.public_booking_id}` : '!'}`);
    } catch {
      toast.error('Booking failed. Please try again.');
    } finally {
      setBookingLoading(false);
    }
  };

  // Calculate total estimate
  const calculateTotal = () => {
    if (!pkg) return 0;
    const slotData = availability.find(a => a.date === selectedDate);
    const baseAdult = slotData?.price_adult || pkg.price_adult;
    const baseChild = slotData?.price_child || pkg.price_child;
    let total = baseAdult * adults + baseChild * children;

    // Hotel upgrade
    const nights = (pkg.duration_days || 1) - 1;
    if (hotelUpgrade === 'premium') total += 1500 * nights * (adults + children);
    if (hotelUpgrade === 'luxury') total += 3500 * nights * (adults + children);

    // Meal upgrade
    if (mealUpgrade) total += 500 * (pkg.duration_days || 1) * (adults + children);

    return total;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-neutral-400" />
      </div>
    );
  }

  if (error || !pkg) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-5xl mb-4">📦</p>
          <h2 className="text-xl font-bold text-neutral-700">{error || 'Package not found'}</h2>
          <Link href="/packages" className="mt-4 text-primary-600 font-semibold hover:underline block">← Browse packages</Link>
        </div>
      </div>
    );
  }

  const totalEstimate = calculateTotal();

  return (
    <div className="min-h-screen page-listing-bg">
      {/* Top bar */}
      <div className="bg-white/80 border-b sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <button onClick={() => router.back()} className="text-neutral-500 hover:text-neutral-800">
            <ArrowLeft size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="font-bold text-neutral-900 text-sm truncate">{pkg.name}</h1>
            <p className="text-xs text-neutral-400">{pkg.duration_days}D/{pkg.duration_nights || pkg.duration_days - 1}N · {pkg.destination}</p>
          </div>
          <div className="text-right">
            <p className="text-lg font-black text-neutral-900">{formatPrice(pkg.price_adult)}</p>
            <p className="text-[10px] text-neutral-400">per person</p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Hero image */}
        {pkg.images && pkg.images.length > 0 && (
          <div className="h-64 md:h-80 rounded-2xl overflow-hidden mb-6">
            <img src={pkg.images[0].url} alt={pkg.name} className="w-full h-full object-cover" />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6">
          {/* Left — Itinerary */}
          <div className="space-y-5">
            {/* Overview */}
            <div className="bg-white/80 rounded-2xl shadow-card p-5">
              <h2 className="text-lg font-black text-neutral-900 mb-2 font-heading">{pkg.name}</h2>
              <div className="flex items-center gap-4 flex-wrap mb-3">
                <span className="flex items-center gap-1.5 text-xs text-neutral-500">
                  <Calendar size={12} className="text-primary-500" /> {pkg.duration_days}D/{pkg.duration_nights || pkg.duration_days - 1}N
                </span>
                <span className="flex items-center gap-1.5 text-xs text-neutral-500">
                  <MapPin size={12} className="text-primary-500" /> {pkg.destination}
                </span>
                {pkg.rating > 0 && (
                  <span className="flex items-center gap-1 text-xs text-neutral-500">
                    <Star size={12} fill="#f59e0b" stroke="none" /> {pkg.rating.toFixed(1)} ({pkg.review_count || 0})
                  </span>
                )}
              </div>
              {pkg.description && <p className="text-sm text-neutral-600 leading-relaxed">{pkg.description}</p>}

              {/* Highlights */}
              {pkg.highlights && pkg.highlights.length > 0 && (
                <div className="mt-4 pt-3 border-t border-neutral-100">
                  <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Highlights</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {pkg.highlights.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-neutral-700">
                        <Check size={12} className="text-green-500 shrink-0" /> {h}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Day-by-day Itinerary */}
            <div className="bg-white/80 rounded-2xl shadow-card p-5">
              <h3 className="font-bold text-neutral-800 text-sm mb-4 font-heading">Day-by-Day Itinerary</h3>
              <div className="space-y-3">
                {(pkg.itinerary || []).map((day: PackageItineraryDay, index: number) => {
                  const isExpanded = expandedDay === index;
                  return (
                    <div key={index} className="border border-neutral-100 rounded-xl overflow-hidden">
                      <button
                        onClick={() => setExpandedDay(isExpanded ? null : index)}
                        className="w-full flex items-center justify-between px-4 py-3 bg-page hover:bg-neutral-100 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="w-8 h-8 rounded-lg bg-primary-600 text-white flex items-center justify-center text-xs font-bold shrink-0">
                            D{index + 1}
                          </span>
                          <div className="text-left">
                            <p className="font-semibold text-neutral-800 text-sm">{day.title || `Day ${index + 1}`}</p>
                            {day.location && <p className="text-xs text-neutral-400">{day.location}</p>}
                          </div>
                        </div>
                        {isExpanded ? <ChevronUp size={16} className="text-neutral-400" /> : <ChevronDown size={16} className="text-neutral-400" />}
                      </button>
                      {isExpanded && (
                        <div className="px-4 py-4 space-y-3">
                          {day.description && (
                            <p className="text-sm text-neutral-600 leading-relaxed">{day.description}</p>
                          )}
                          {day.activities && day.activities.length > 0 && (
                            <div className="space-y-2">
                              {day.activities.map((activity, ai) => (
                                <div key={ai} className="flex items-start gap-3 bg-page rounded-lg px-3 py-2.5 border border-neutral-100">
                                  <span className="text-primary-500 mt-0.5 shrink-0">
                                    {ACTIVITY_ICONS[activity.type || 'default'] || ACTIVITY_ICONS.default}
                                  </span>
                                  <div>
                                    <p className="text-xs font-semibold text-neutral-700">{activity.name}</p>
                                    {activity.description && <p className="text-xs text-neutral-500 mt-0.5">{activity.description}</p>}
                                    {activity.time && <p className="text-[10px] text-neutral-400 mt-0.5">⏰ {activity.time}</p>}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                          {day.meals && day.meals.length > 0 && (
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-semibold text-neutral-500">Meals:</span>
                              {day.meals.map((meal) => (
                                <span key={meal} className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full border border-green-100 font-medium">
                                  {meal}
                                </span>
                              ))}
                            </div>
                          )}
                          {day.hotel && (
                            <div className="flex items-center gap-2 text-xs text-neutral-500 bg-blue-50 rounded-lg px-3 py-2 border border-blue-100">
                              <Home size={12} className="text-blue-500" />
                              <span><span className="font-semibold text-blue-700">Stay:</span> {day.hotel}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Availability Calendar */}
            {availability.length > 0 && (
              <div className="bg-white/80 rounded-2xl shadow-card p-5">
                <h3 className="font-bold text-neutral-800 text-sm mb-4 font-heading">Availability &amp; Pricing</h3>
                <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-7 gap-2">
                  {availability.slice(0, 28).map((slot) => (
                    <button
                      key={slot.date}
                      disabled={slot.is_sold_out || slot.available_slots === 0}
                      onClick={() => setSelectedDate(slot.date)}
                      className={`p-2 rounded-lg border text-center transition-all ${
                        selectedDate === slot.date
                          ? 'bg-primary-600 text-white border-primary-600'
                          : slot.is_sold_out
                          ? 'bg-page text-neutral-300 border-neutral-100 cursor-not-allowed'
                          : 'bg-white/80 text-neutral-700 border-neutral-200 hover:border-primary-300'
                      }`}
                    >
                      <p className="text-[10px] font-medium">{format(parseISO(slot.date), 'dd MMM')}</p>
                      {!slot.is_sold_out ? (
                        <p className={`text-xs font-bold ${selectedDate === slot.date ? 'text-white' : 'text-neutral-800'}`}>
                          {formatPrice(slot.price_adult)}
                        </p>
                      ) : (
                        <p className="text-[10px] text-red-400">Sold</p>
                      )}
                      {!slot.is_sold_out && slot.available_slots <= 5 && (
                        <p className={`text-[8px] ${selectedDate === slot.date ? 'text-white/70' : 'text-orange-500'}`}>
                          {slot.available_slots} left
                        </p>
                      )}
                    </button>
                  ))}
                </div>
                {calLoading && <div className="text-center py-4"><Loader2 size={16} className="animate-spin text-neutral-400 mx-auto" /></div>}
              </div>
            )}
          </div>

          {/* Right — Booking */}
          <div>
            <div className="booking-panel p-5 sticky top-20">
              {bookingReference && (
                <div className="mb-4 rounded-xl border border-green-200 bg-green-50 p-3 text-sm text-green-700">
                  Booking confirmed. Reference: <span className="font-bold">{bookingReference}</span>
                </div>
              )}
              <div className="text-center mb-4 pb-3 border-b border-neutral-100">
                <p className="text-xs text-neutral-400">Starting from</p>
                <p className="text-2xl font-black text-neutral-900 font-heading">{formatPrice(pkg.price_adult)}</p>
                <p className="text-xs text-neutral-400">per person</p>
              </div>

              {/* Date */}
              <div className="mb-3">
                <label className="text-xs font-semibold text-neutral-500 block mb-1">Travel Date *</label>
                <input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  min={format(new Date(), 'yyyy-MM-dd')}
                  className="w-full bg-page rounded-xl px-3 py-2.5 border border-neutral-200 text-sm outline-none focus:border-primary-400"
                />
              </div>

              {/* Guests */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                {[
                  { label: 'Adults', val: adults, min: 1, max: 10, set: setAdults },
                  { label: 'Children', val: children, min: 0, max: 6, set: setChildren },
                ].map((item) => (
                  <div key={item.label}>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">{item.label}</label>
                    <div className="flex items-center justify-between bg-page rounded-xl px-2.5 py-2 border border-neutral-200">
                      <button onClick={() => item.set(Math.max(item.min, item.val - 1))} className="w-6 h-6 rounded-full bg-white/80 border border-neutral-300 flex items-center justify-center hover:border-primary-400"><Minus size={10} /></button>
                      <span className="text-sm font-bold">{item.val}</span>
                      <button onClick={() => item.set(Math.min(item.max, item.val + 1))} className="w-6 h-6 rounded-full bg-white/80 border border-neutral-300 flex items-center justify-center hover:border-primary-400"><Plus size={10} /></button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Customization */}
              <div className="mb-4">
                <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Customize</h4>

                {/* Hotel upgrade */}
                <div className="mb-2">
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Hotel Category</label>
                  <div className="flex gap-1">
                    {(['standard', 'premium', 'luxury'] as const).map((tier) => (
                      <button
                        key={tier}
                        onClick={() => setHotelUpgrade(tier)}
                        className={`flex-1 text-xs py-2 rounded-lg border font-semibold transition-all capitalize ${
                          hotelUpgrade === tier
                            ? 'bg-primary-600 text-white border-primary-600'
                            : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-300'
                        }`}
                      >
                        {tier}
                        {tier === 'premium' && <span className="block text-[9px] font-normal opacity-70">+₹1,500/n</span>}
                        {tier === 'luxury' && <span className="block text-[9px] font-normal opacity-70">+₹3,500/n</span>}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Meal upgrade */}
                <button
                  onClick={() => setMealUpgrade(!mealUpgrade)}
                  className={`w-full flex items-center justify-between text-xs px-3 py-2.5 rounded-lg border font-semibold mb-2 transition-all ${
                    mealUpgrade
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-green-300'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Utensils size={12} /> All Meals Included
                  </span>
                  <span className="text-[10px]">+₹500/day/person</span>
                </button>
              </div>

              {/* Price breakdown */}
              {totalEstimate > 0 && (
                <div className="bg-page rounded-xl p-3.5 mb-4 border border-neutral-200">
                  <div className="flex justify-between text-xs text-neutral-500 mb-1">
                    <span>{adults} Adult{adults > 1 ? 's' : ''} × {formatPrice(pkg.price_adult)}</span>
                    <span>{formatPrice(pkg.price_adult * adults)}</span>
                  </div>
                  {children > 0 && (
                    <div className="flex justify-between text-xs text-neutral-500 mb-1">
                      <span>{children} Child{children > 1 ? 'ren' : ''} × {formatPrice(pkg.price_child)}</span>
                      <span>{formatPrice(pkg.price_child * children)}</span>
                    </div>
                  )}
                  {hotelUpgrade !== 'standard' && (
                    <div className="flex justify-between text-xs text-blue-600 mb-1">
                      <span>{hotelUpgrade} hotel upgrade</span>
                      <span>+{formatPrice((hotelUpgrade === 'premium' ? 1500 : 3500) * ((pkg.duration_days || 1) - 1) * (adults + children))}</span>
                    </div>
                  )}
                  {mealUpgrade && (
                    <div className="flex justify-between text-xs text-green-600 mb-1">
                      <span>Meal upgrade</span>
                      <span>+{formatPrice(500 * (pkg.duration_days || 1) * (adults + children))}</span>
                    </div>
                  )}
                  <div className="pt-2 border-t border-neutral-200 flex justify-between">
                    <span className="font-bold text-xs text-neutral-700">Total</span>
                    <span className="font-black text-sm text-neutral-900">{formatPrice(totalEstimate)}</span>
                  </div>
                </div>
              )}

              <button
                onClick={handleBook}
                disabled={bookingLoading || !selectedDate}
                className="btn-primary w-full py-3 text-sm"
              >
                {bookingLoading ? (
                  <><Loader2 size={14} className="animate-spin" /> Booking...</>
                ) : (
                  <>Book Package</>
                )}
              </button>

              <p className="text-center text-xs text-neutral-400 mt-3">🔒 Secure booking · Best price guaranteed</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
