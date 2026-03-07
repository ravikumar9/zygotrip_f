'use client';

import { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getHotel, fetchPricingIntelligence } from '@/services/hotels';
import { bookingsService } from '@/services/bookings';
import type { RoomType, RoomMealPlan, PricingIntelligence, PromoResult } from '@/types';

// Dynamic imports — only loaded when the component mounts (reduces initial bundle)
const PropertyGallery = dynamic(() => import('@/components/hotels/PropertyGallery'), {
  loading: () => <div className="h-72 bg-neutral-100 animate-pulse rounded-2xl" />,
  ssr: false,
});
const RoomSelector = dynamic(() => import('@/components/hotels/RoomSelector'), {
  loading: () => <div className="h-48 bg-neutral-100 animate-pulse rounded-2xl" />,
  ssr: false,
});
const PropertyMap = dynamic(() => import('@/components/hotels/PropertyMap'), {
  loading: () => <div className="h-56 bg-neutral-100 animate-pulse rounded-2xl" />,
  ssr: false,
});
import {
  MapPin, Star, Shield, AlertCircle, ChevronRight, Check,
  Calendar, Users, Minus, Plus, ArrowLeft, Share2, Heart,
  Wifi, ParkingCircle, Utensils, Waves, Dumbbell, Wind, Bed,
  Tag, TrendingDown, BadgeCheck, Loader2, X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { addDays, format, parseISO, isValid } from 'date-fns';
import { clsx } from 'clsx';
import { formatPrice as fmt } from '@/lib/formatPrice';

/** Format date string (yyyy-MM-dd) → "Mon, 12 Feb" for compact display */
function fmtDateCompact(dateStr: string): string {
  try {
    const d = parseISO(dateStr);
    if (!isValid(d)) return dateStr;
    return format(d, 'EEE, d MMM');
  } catch {
    return dateStr;
  }
}

const TABS = ['Room Options', 'Amenities', 'Location', 'Policies'] as const;
type Tab = typeof TABS[number];

const AMENITY_ICONS: Record<string, React.ReactNode> = {
  WiFi: <Wifi size={13} />,
  Parking: <ParkingCircle size={13} />,
  Restaurant: <Utensils size={13} />,
  Pool: <Waves size={13} />,
  Gym: <Dumbbell size={13} />,
  AC: <Wind size={13} />,
};

export default function HotelDetailClient() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();

  const tomorrow = addDays(new Date(), 1);
  const dayAfter = addDays(new Date(), 2);

  const [activeTab, setActiveTab] = useState<Tab>('Room Options');
  const [selectedRoom, setSelectedRoom] = useState<RoomType | null>(null);
  const [selectedMealPlan, setSelectedMealPlan] = useState<RoomMealPlan | null>(null);
  const [checkIn, setCheckIn] = useState(searchParams.get('checkin') || format(tomorrow, 'yyyy-MM-dd'));
  const [checkOut, setCheckOut] = useState(searchParams.get('checkout') || format(dayAfter, 'yyyy-MM-dd'));
  const [guests, setGuests] = useState(parseInt(searchParams.get('adults') || '2', 10));
  const [rooms, setRooms] = useState(1);
  const [wishlisted, setWishlisted] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [mealFilter, setMealFilter] = useState('');  // '' = all plans

  // ── Promo code state ─────────────────────────────────────────
  const [promoCode, setPromoCode] = useState('');
  const [promoResult, setPromoResult] = useState<PromoResult | null>(null);
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoError, setPromoError] = useState('');

  // ── Price intelligence state ─────────────────────────────────
  const [priceIntel, setPriceIntel] = useState<PricingIntelligence | null>(null);

  // Preserve location for back-navigation
  const searchLocation = searchParams.get('location') || '';

  const handleApplyPromo = async () => {
    if (!promoCode.trim()) return;
    setPromoLoading(true);
    setPromoError('');
    setPromoResult(null);
    try {
      const baseAmt = estimatedTotal > 0 ? estimatedTotal : (property?.min_price ?? 0) * Math.max(nights, 1) * rooms;
      const mealAmt = selectedMealPlan && mealPlanModifier > 0 ? mealPlanModifier * Math.max(nights, 1) * rooms : 0;
      const result = await bookingsService.applyPromo({
        promo_code: promoCode.trim().toUpperCase(),
        base_amount: String(baseAmt),
        meal_amount: String(mealAmt),
      });
      setPromoResult(result);
      if (!result.valid) setPromoError('Invalid or expired promo code');
    } catch {
      setPromoError('Could not validate promo code. Try again.');
    } finally {
      setPromoLoading(false);
    }
  };

  const { data: property, isLoading, error } = useQuery({
    queryKey: ['property', slug],
    queryFn: () => getHotel(slug),
    enabled: !!slug,
    staleTime: 5 * 60_000,
  });

  // Fetch price intelligence when property UUID loads — after property is declared
  useEffect(() => {
    if (!property?.uuid) return;
    fetchPricingIntelligence(property.uuid).then(data => {
      if (data) setPriceIntel(data);
    });
  }, [property?.uuid]);

  const handleBook = async () => {
    if (!property || !checkIn || !checkOut) return;
    if (!selectedRoom) {
      setActiveTab('Room Options');
      toast('Select a room type from the Room Options tab first', { icon: '👆', duration: 4000 });
      return;
    }
    setBookingLoading(true);
    try {
      const ctx = await bookingsService.createContext({
        property_id: property.id,
        room_type_id: selectedRoom.id,
        checkin: checkIn,
        checkout: checkOut,
        rooms,
        adults: guests,
        meal_plan: selectedMealPlan?.code || 'room_only',
      });
      // Preserve all search context in booking URL (Goibibo-parity URL framing)
      const params = new URLSearchParams();
      if (searchLocation) params.set('location', searchLocation);
      params.set('checkin', checkIn);
      params.set('checkout', checkOut);
      params.set('adults', String(guests));
      params.set('rooms', String(rooms));
      if (property.city_name) params.set('city', property.city_name);
      router.push(`/booking/${ctx.uuid}?${params.toString()}`);
    } catch {
      toast.error('Could not initiate booking. Please try again.', { duration: 6000 });
    } finally {
      setBookingLoading(false);
    }
  };

  const nights = checkIn && checkOut
    ? Math.max(0, Math.round((new Date(checkOut).getTime() - new Date(checkIn).getTime()) / 86_400_000))
    : 0;

  // Pre-booking ESTIMATE only — final price comes from server via BookingContext.
  // This estimate intentionally excludes GST, service fee, and date-aware pricing.
  const mealPlanModifier = selectedMealPlan ? parseFloat(String(selectedMealPlan.price_modifier)) : 0;
  const pricePerNight = selectedRoom
    ? parseFloat(String(selectedRoom.base_price)) + mealPlanModifier
    : (property?.min_price ?? 0);
  const estimatedTotal = pricePerNight * nights * rooms;
  const promoDiscount = promoResult?.valid ? parseFloat(promoResult.discount_amount ?? '0') : 0;
  const discountedTotal = Math.max(0, estimatedTotal - promoDiscount);

  // Filter rooms by meal plan
  const filteredRooms = mealFilter && property?.room_types
    ? property.room_types.filter((rt) => {
        // Check legacy meal_plan CharField
        if (rt.meal_plan === mealFilter) return true;
        // Check new RoomMealPlan relation
        if (rt.meal_plans?.some((mp) => mp.code === mealFilter)) return true;
        return false;
      })
    : (property?.room_types ?? []);

  // Derive meal filter options dynamically from room data (no hardcoded labels)
  const mealFilterOptions = useMemo(() => {
    const codes = new Set<string>();
    const nameMap: Record<string, string> = {};
    (property?.room_types ?? []).forEach(rt => {
      (rt.meal_plans ?? []).forEach(mp => {
        if (mp.is_available !== false) {
          codes.add(mp.code);
          if (!nameMap[mp.code]) nameMap[mp.code] = mp.name;
        }
      });
    });
    return [
      { code: '', label: 'All Plans' },
      ...Array.from(codes)
        .sort((a, b) => {
          const order = ['room_only', 'breakfast', 'half_board', 'full_board', 'all_inclusive'];
          return order.indexOf(a) - order.indexOf(b);
        })
        .map(code => ({ code, label: nameMap[code] })),
    ];
  }, [property?.room_types]);

  if (isLoading) {
    return (
      <div className="min-h-screen pt-6">
        <div className="max-w-7xl mx-auto px-4">
          <div className="skeleton h-[400px] w-full rounded-2xl mb-6" />
          <div className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <div className="skeleton h-8 w-2/3 rounded" />
              <div className="skeleton h-4 w-1/2 rounded" />
              <div className="skeleton h-56 w-full rounded-2xl" />
            </div>
            <div className="skeleton h-96 rounded-2xl" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !property) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-5xl mb-4">😕</p>
          <h2 className="text-xl font-bold text-neutral-700">Property not found</h2>
          <button onClick={() => router.push('/hotels')} className="mt-4 text-primary-600 font-semibold hover:underline">
            ← Browse all hotels
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-detail-bg">

      {/* ── Sticky top context bar (Goibibo-parity) ───────────── */}
      <div className="sticky top-14 z-30 hidden lg:block"
           style={{ background: 'linear-gradient(90deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%)' }}>
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex items-center gap-6">
          {/* Back */}
          <button
            onClick={() => router.back()}
            className="text-white/70 hover:text-white flex items-center gap-1.5 text-xs font-semibold shrink-0 transition-colors"
          >
            <ArrowLeft size={14} /> Back
          </button>
          <div className="w-px h-5 bg-white/20" />
          {/* Property name */}
          <p className="font-bold text-white text-sm truncate max-w-xs">{property.name}</p>
          <div className="w-px h-5 bg-white/20" />
          {/* Dates */}
          <div className="flex items-center gap-1.5 text-white/80 text-xs font-medium">
            <Calendar size={11} className="text-primary-300" />
            <span>{fmtDateCompact(checkIn)}</span>
            <span className="text-white/40 mx-1">→</span>
            <span>{fmtDateCompact(checkOut)}</span>
            {nights > 0 && <span className="text-white/50 ml-1">({nights}N)</span>}
          </div>
          <div className="w-px h-5 bg-white/20" />
          {/* Guests */}
          <div className="flex items-center gap-1.5 text-white/80 text-xs font-medium">
            <Users size={11} className="text-primary-300" />
            <span>{guests} Guests · {rooms} Room</span>
          </div>
          {/* Book now pill — far right */}
          <button
            onClick={handleBook}
            disabled={bookingLoading}
            className="ml-auto shrink-0 text-xs font-bold text-white px-4 py-1.5 rounded-full transition-all"
            style={{ background: 'var(--primary)' }}
          >
            {selectedRoom
              ? `Book @ ${fmt(pricePerNight)}/night${selectedMealPlan ? ` · ${selectedMealPlan.name}` : ''}`
              : 'Select a Room'}
          </button>
        </div>
      </div>

      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {/* Back / actions bar — mobile only */}
        <div className="flex items-center justify-between mb-5 lg:hidden">
          <button onClick={() => router.back()} className="flex items-center gap-2 text-neutral-600 hover:text-neutral-900 font-semibold text-sm transition-colors">
            <ArrowLeft size={18} /> Back
          </button>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-3 py-2 rounded-xl border border-neutral-200 bg-white text-sm font-medium text-neutral-600 hover:shadow-sm transition-all">
              <Share2 size={14} /> Share
            </button>
            <button
              onClick={() => setWishlisted(!wishlisted)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl border border-neutral-200 bg-white text-sm font-medium transition-all hover:shadow-sm"
              style={{ color: wishlisted ? '#eb5757' : '#4b5563' }}
            >
              <Heart size={14} fill={wishlisted ? '#eb5757' : 'none'} stroke="currentColor" />
              {wishlisted ? 'Saved' : 'Save'}
            </button>
          </div>
        </div>

        {/* Desktop share/save — above gallery */}
        <div className="hidden lg:flex items-center justify-end gap-2 mb-4">
          <button className="flex items-center gap-2 px-3 py-2 rounded-xl border border-neutral-200 bg-white text-sm font-medium text-neutral-600 hover:shadow-sm transition-all">
            <Share2 size={14} /> Share
          </button>
          <button
            onClick={() => setWishlisted(!wishlisted)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-neutral-200 bg-white text-sm font-medium transition-all hover:shadow-sm"
            style={{ color: wishlisted ? '#eb5757' : '#4b5563' }}
          >
            <Heart size={14} fill={wishlisted ? '#eb5757' : 'none'} stroke="currentColor" />
            {wishlisted ? 'Saved' : 'Save'}
          </button>
        </div>

        {/* Gallery */}
        <PropertyGallery images={property.images} propertyName={property.name} />

        {/* Goibibo-style coupon / offer strip */}
        <div className="flex items-center gap-3 bg-gradient-to-r from-amber-50 via-orange-50 to-amber-50 border border-amber-200 rounded-xl px-4 py-3 my-4 overflow-x-auto">
          <div className="shrink-0 w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center">
            <Tag size={14} className="text-primary-600" />
          </div>
          <div className="shrink-0">
            <p className="text-xs font-bold text-neutral-800">Best deals &amp; offers</p>
            <p className="text-xs text-neutral-500">Enter a promo code in the booking panel for exclusive discounts</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-6">

          {/* ── Left content ──────────────────────────────────────── */}
          <div className="space-y-5">

            {/* Header card */}
            <div className="bg-white rounded-2xl p-6 shadow-card">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {property.star_category > 0 && (
                    <div className="flex items-center gap-0.5 mb-1.5">
                      {Array.from({ length: property.star_category }).map((_, i) => (
                        <Star key={i} size={13} fill="#f59e0b" stroke="none" />
                      ))}
                      <span className="text-xs text-neutral-400 ml-1 font-medium">{property.property_type}</span>
                    </div>
                  )}
                  <h1 className="text-2xl font-black text-neutral-900 mb-2 leading-tight font-heading">
                    {property.name}
                  </h1>
                  <div className="flex items-center gap-1.5 text-neutral-500 text-sm flex-wrap">
                    <MapPin size={14} className="shrink-0 text-primary-400" />
                    <span>{[property.address, property.area, property.city_name].filter(Boolean).join(', ')}</span>
                    {property.latitude && property.longitude && (
                      <button
                        onClick={() => setActiveTab('Location')}
                        className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 ml-2 transition-colors"
                      >
                        <MapPin size={11} /> View Map
                      </button>
                    )}
                    {property.review_count > 0 && (
                      <button
                        onClick={() => {
                          const el = document.getElementById('guest-reviews');
                          el?.scrollIntoView({ behavior: 'smooth' });
                        }}
                        className="flex items-center gap-1 text-xs font-semibold text-purple-600 hover:text-purple-800 ml-1 transition-colors"
                      >
                        <Star size={11} /> View Reviews ({property.review_count})
                      </button>
                    )}
                  </div>
                </div>

                {property.rating && parseFloat(String(property.rating)) > 0 && (
                  <div className="flex flex-col items-center shrink-0">
                    <div className="rating-badge text-base px-3 py-1.5">
                      <Star size={13} fill="white" stroke="none" />
                      {parseFloat(String(property.rating)).toFixed(1)}
                    </div>
                    {property.review_count > 0 && (
                      <p className="text-xs text-neutral-400 mt-1">{property.review_count} reviews</p>
                    )}
                  </div>
                )}
              </div>

              {/* Trust badges */}
              <div className="flex flex-wrap gap-2 mt-4">
                {property.has_free_cancellation && (
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 px-3 py-1.5 rounded-xl border border-green-100">
                    <Check size={11} strokeWidth={3} /> Free Cancellation
                  </span>
                )}
                <span className="flex items-center gap-1.5 text-xs font-semibold text-primary-700 bg-primary-50 px-3 py-1.5 rounded-xl border border-primary-100">
                  <Shield size={11} /> Instant Confirmation
                </span>
                {property.is_trending && (
                  <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-3 py-1.5 rounded-xl border border-amber-100">
                    🔥 Trending
                  </span>
                )}
                {property.pay_at_hotel && (
                  <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-3 py-1.5 rounded-xl border border-blue-100">
                    Pay at Hotel
                  </span>
                )}
              </div>

              {/* Quick action — view room options */}
              {(property.room_types?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-neutral-100">
                  <button
                    onClick={() => setActiveTab('Room Options')}
                    className="flex items-center gap-1.5 text-xs font-semibold text-primary-600 bg-primary-50 hover:bg-primary-100 px-3 py-1.5 rounded-lg border border-primary-200 transition-colors"
                  >
                    <Bed size={12} /> VIEW {property.room_types.length} ROOM OPTIONS
                  </button>
                </div>
              )}

              {/* Property description (moved from Overview) */}
              {property.description && (
                <p className="text-neutral-500 leading-relaxed text-sm mt-4 pt-3 border-t border-neutral-100 line-clamp-3">
                  {property.description}
                </p>
              )}
            </div>

            {/* Tabs */}
            <div className="bg-white rounded-2xl shadow-card overflow-hidden">
              <div className="flex overflow-x-auto border-b border-neutral-100">
                {TABS.map((tab) => (
                  <button key={tab} onClick={() => setActiveTab(tab)} className={`tab-nav ${activeTab === tab ? 'active' : ''}`}>
                    {tab}
                    {tab === 'Room Options' && (property.room_types?.length ?? 0) > 0 && (
                      <span className="ml-1.5 text-xs bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded-full">
                        {property.room_types.length}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div className="p-6">
                {/* Room Options tab (primary tab — Goibibo-parity) */}
                {activeTab === 'Room Options' && (
                  <div>
                    {/* Meal plan filter pills (Goibibo-parity) */}
                    {(property.room_types?.length ?? 0) > 0 && (
                      <div className="flex items-center gap-2 mb-5 flex-wrap pb-4 border-b border-neutral-100">
                        <span className="text-xs font-bold text-neutral-500 shrink-0">Filter Meals:</span>
                        {mealFilterOptions.map(({ code, label }) => (
                          <button
                            key={code}
                            onClick={() => setMealFilter(code)}
                            className={clsx(
                              'text-xs px-3 py-1.5 rounded-full border font-semibold transition-all',
                              mealFilter === code
                                ? 'bg-primary-600 text-white border-primary-600'
                                : 'bg-white text-neutral-600 border-neutral-200 hover:border-primary-400 hover:text-primary-600'
                            )}
                          >
                            {label}
                          </button>
                        ))}
                        <span className="ml-auto text-xs text-neutral-400 font-medium">
                          {filteredRooms.length} room type{filteredRooms.length !== 1 ? 's' : ''}
                        </span>
                      </div>
                    )}

                    {/* 3-column table header (Goibibo-parity) */}
                    <div className="hidden lg:grid grid-cols-[280px_1fr_200px] bg-neutral-800 text-white rounded-t-xl overflow-hidden mb-0">
                      <div className="px-4 py-3 text-xs font-bold uppercase tracking-wider">Room Type</div>
                      <div className="px-4 py-3 text-xs font-bold uppercase tracking-wider border-l border-white/10">Room Options</div>
                      <div className="px-4 py-3 text-xs font-bold uppercase tracking-wider border-l border-white/10 text-right">Price</div>
                    </div>

                    <RoomSelector
                      rooms={filteredRooms}
                      selectedRoomId={selectedRoom?.id}
                      selectedMealPlanCode={selectedMealPlan?.code}
                      onSelect={(room, mealPlan) => {
                        setSelectedRoom(room);
                        setSelectedMealPlan(mealPlan ?? null);
                      }}
                    />
                    {filteredRooms.length === 0 && mealFilter && (
                      <div className="text-center py-8 text-neutral-400">
                        <Bed size={32} className="mx-auto mb-2 opacity-40" />
                        <p className="text-sm">No rooms with this meal plan. <button className="text-primary-600 font-semibold" onClick={() => setMealFilter('')}>Show all rooms</button></p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'Amenities' && (
                  <div>
                    <h3 className="font-bold text-neutral-800 mb-4 text-sm font-heading">All Amenities</h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                      {property.amenities?.map((a) => (
                        <div key={a.name} className="flex items-center gap-2.5 text-sm text-neutral-700 bg-neutral-50 rounded-xl px-3 py-3 border border-neutral-100 hover:border-primary-200 transition-colors">
                          <span className="text-primary-500 shrink-0">{AMENITY_ICONS[a.name] ?? <Check size={13} className="text-green-500" strokeWidth={2.5} />}</span>
                          {a.name}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === 'Location' && (
                  <div className="space-y-4">
                    <PropertyMap
                      latitude={property.latitude}
                      longitude={property.longitude}
                      name={property.name}
                      address={[property.address, property.area, property.city_name].filter(Boolean).join(', ')}
                    />
                    <div className="flex items-start gap-2 bg-primary-50 rounded-xl px-4 py-3 border border-primary-100">
                      <MapPin size={14} className="text-primary-500 mt-0.5 shrink-0" />
                      <p className="text-sm text-primary-800 leading-relaxed">
                        <span className="font-bold">{property.name}</span>
                        {[property.address, property.area, property.city_name].filter(Boolean).length > 0 && (
                          <> — {[property.address, property.area, property.city_name].filter(Boolean).join(', ')}</>
                        )}
                      </p>
                    </div>
                  </div>
                )}

                {activeTab === 'Policies' && (
                  <div className="space-y-3">
                    {property.policies && property.policies.length > 0 ? (
                      property.policies.map((p) => (
                        <div key={p.id} className="rounded-xl bg-neutral-50 p-4 border border-neutral-100">
                          <h4 className="font-semibold text-neutral-800 text-sm mb-1 flex items-center gap-2">
                            <AlertCircle size={13} className="text-orange-400" />{p.title}
                          </h4>
                          <p className="text-sm text-neutral-500 leading-relaxed">{p.description}</p>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-neutral-400">
                        <AlertCircle size={28} className="mx-auto mb-2 opacity-40" />
                        <p className="text-sm">No specific policies listed for this property.</p>
                        {property.has_free_cancellation && (
                          <p className="text-sm text-green-600 mt-2 font-medium">Free cancellation available</p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Booking Panel ──────────────────────────────────────── */}
          <div>
            <div className="booking-panel p-5 sticky top-24">
              <div className="text-center mb-5 pb-4 border-b border-neutral-100">
                <p className="text-xs text-neutral-400">Starting from</p>
                <p className="text-3xl font-black text-neutral-900 mt-0.5 font-heading">
                  {fmt(property.min_price)}
                </p>
                <p className="text-xs text-neutral-400">per night + taxes</p>
              </div>

              {/* Dates */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                {[
                  { label: 'Check-in', val: checkIn, min: format(tomorrow, 'yyyy-MM-dd'), set: setCheckIn },
                  { label: 'Check-out', val: checkOut, min: checkIn || format(tomorrow, 'yyyy-MM-dd'), set: setCheckOut },
                ].map((d) => (
                  <div key={d.label}>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">{d.label}</label>
                    <div className="flex items-center gap-1 bg-neutral-50 rounded-xl px-2.5 py-2.5 border border-neutral-200 focus-within:border-primary-400">
                      <Calendar size={12} className="text-neutral-400 shrink-0" />
                      <input type="date" value={d.val} min={d.min}
                        onChange={(e) => d.set(e.target.value)}
                        className="bg-transparent text-xs font-semibold text-neutral-700 outline-none w-full" />
                    </div>
                  </div>
                ))}
              </div>

              {/* Guests / Rooms */}
              <div className="grid grid-cols-2 gap-2 mb-4">
                {[
                  { label: 'Guests', val: guests, min: 1, set: setGuests },
                  { label: 'Rooms', val: rooms, min: 1, set: setRooms },
                ].map((item) => (
                  <div key={item.label}>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">{item.label}</label>
                    <div className="flex items-center justify-between bg-neutral-50 rounded-xl px-2.5 py-2.5 border border-neutral-200">
                      <button type="button" onClick={() => item.set(Math.max(item.min, item.val - 1))}
                        className="w-6 h-6 rounded-full bg-white border border-neutral-300 flex items-center justify-center hover:border-primary-400">
                        <Minus size={10} />
                      </button>
                      <span className="text-sm font-bold">{item.val}</span>
                      <button type="button" onClick={() => item.set(item.val + 1)}
                        className="w-6 h-6 rounded-full bg-white border border-neutral-300 flex items-center justify-center hover:border-primary-400">
                        <Plus size={10} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Promo code widget */}
              <div className="mb-4">
                {promoResult?.valid ? (
                  <div className="promo-applied">
                    <BadgeCheck size={14} className="shrink-0" />
                    <span className="flex-1">{promoResult.promo_code} applied — {fmt(promoDiscount)} off</span>
                    <button
                      onClick={() => { setPromoResult(null); setPromoCode(''); setPromoError(''); }}
                      className="text-green-500 hover:text-green-700 shrink-0"
                      aria-label="Remove promo"
                    >
                      <X size={13} />
                    </button>
                  </div>
                ) : (
                  <div>
                    <div className="promo-input-row">
                      <input
                        type="text"
                        placeholder="Promo code"
                        value={promoCode}
                        onChange={e => { setPromoCode(e.target.value.toUpperCase()); setPromoError(''); }}
                        onKeyDown={e => e.key === 'Enter' && handleApplyPromo()}
                        className="flex-1 text-xs border border-neutral-200 rounded-xl px-3 py-2 outline-none focus:border-primary-400 font-mono tracking-wider bg-neutral-50 uppercase"
                        disabled={promoLoading}
                      />
                      <button
                        onClick={handleApplyPromo}
                        disabled={promoLoading || !promoCode.trim()}
                        className="flex items-center gap-1 text-xs font-bold px-3 py-2 rounded-xl bg-primary-600 hover:bg-primary-700 text-white disabled:opacity-50 transition-colors shrink-0"
                      >
                        {promoLoading ? <Loader2 size={11} className="animate-spin" /> : <Tag size={11} />}
                        Apply
                      </button>
                    </div>
                    {promoError && <p className="promo-error">{promoError}</p>}
                  </div>
                )}
              </div>

              {/* Room select reminder */}
              {!selectedRoom && (property.room_types?.length ?? 0) > 0 && (
                <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 rounded-xl px-3 py-2.5 mb-4 border border-amber-100">
                  <AlertCircle size={13} className="shrink-0 mt-0.5" />
                  Select a room from the &ldquo;Room Options&rdquo; tab
                </div>
              )}

              {/* Selected room + meal plan badge */}
              {selectedRoom && (
                <div className="bg-primary-50 rounded-xl px-3 py-2.5 mb-3 border border-primary-100">
                  <div className="flex items-center gap-2">
                    <Check size={13} className="text-primary-600 shrink-0" />
                    <span className="text-xs font-semibold text-primary-800 truncate flex-1">{selectedRoom.name}</span>
                    <button
                      onClick={() => { setSelectedRoom(null); setSelectedMealPlan(null); }}
                      className="text-primary-400 hover:text-primary-600 text-xs shrink-0"
                    >×</button>
                  </div>
                  {selectedMealPlan && (
                    <p className="text-xs text-primary-600 mt-0.5 ml-5">
                      {selectedMealPlan.name}
                      {parseFloat(String(selectedMealPlan.price_modifier)) > 0 &&
                        <span className="ml-1 text-primary-400">+{fmt(parseFloat(String(selectedMealPlan.price_modifier)))}</span>
                      }
                    </p>
                  )}
                </div>
              )}

              {/* Price estimate — display only, NOT used for checkout */}
              {nights > 0 && estimatedTotal > 0 && (
                <div className="bg-neutral-50 rounded-xl p-3.5 mb-4 border border-neutral-200">
                  {selectedRoom && (
                    <div className="flex justify-between text-xs text-neutral-500 mb-1">
                      <span>Room: {fmt(parseFloat(String(selectedRoom.base_price)))}</span>
                      <span>× {nights}N × {rooms}R</span>
                    </div>
                  )}
                  {selectedMealPlan && mealPlanModifier > 0 && (
                    <div className="flex justify-between text-xs text-green-600 mb-1">
                      <span>{selectedMealPlan.name}</span>
                      <span>+{fmt(mealPlanModifier)} × {nights}N × {rooms}R</span>
                    </div>
                  )}
                  <div className="flex justify-between text-xs text-neutral-600 mb-1 font-medium">
                    <span>{fmt(pricePerNight)}/night × {nights}N × {rooms}R</span>
                    <span className="font-semibold">{fmt(estimatedTotal)}</span>
                  </div>
                  {promoDiscount > 0 && (
                    <div className="flex justify-between text-xs text-green-600 font-semibold mb-1">
                      <span className="flex items-center gap-1"><Tag size={10} /> Promo ({promoResult?.promo_code})</span>
                      <span>−{fmt(promoDiscount)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-xs text-neutral-400 mb-2">
                    <span>Taxes &amp; fees (GST)</span>
                    <span className="italic">calculated at checkout</span>
                  </div>
                  <div className="pt-2 border-t border-neutral-200 flex justify-between">
                    <span className="font-bold text-xs text-neutral-700">Estimated subtotal</span>
                    <span className="font-black text-sm text-neutral-900">{fmt(discountedTotal)}</span>
                  </div>
                  <p className="text-[10px] text-neutral-400 mt-1 text-center">
                    Final price confirmed at checkout
                  </p>
                </div>
              )}

              <button
                onClick={handleBook}
                disabled={!checkIn || !checkOut || bookingLoading}
                className="btn-primary w-full text-base py-3"
              >
                {bookingLoading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="white" strokeWidth="4" />
                      <path className="opacity-75" fill="white" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16v-4l-3 3 3 3v-4a8 8 0 01-8-8z" />
                    </svg>
                    Processing...
                  </>
                ) : (
                  <>{selectedRoom ? 'Book Now' : 'Select a Room'} <ChevronRight size={16} /></>
                )}
              </button>

              <p className="text-center text-xs text-neutral-400 mt-3">🔒 Secure checkout · Instant confirmation</p>
            </div>

            {/* Price Intelligence badge — data from backend only, shown if available */}
            {priceIntel && priceIntel.summary.total_competitors > 0 && (
              <div className="mt-3">
                {priceIntel.summary.is_cheapest ? (
                  <div className="price-intel-badge cheapest">
                    <BadgeCheck size={15} className="shrink-0" />
                    <div>
                      <p className="font-bold text-xs">Best Price Guaranteed</p>
                      {priceIntel.summary.our_advantage_pct > 0 && (
                        <p className="text-xs font-normal opacity-80">
                          {priceIntel.summary.our_advantage_pct.toFixed(0)}% cheaper than market avg
                        </p>
                      )}
                    </div>
                  </div>
                ) : priceIntel.summary.our_advantage_pct > 0 ? (
                  <div className="price-intel-badge competitive">
                    <TrendingDown size={15} className="shrink-0" />
                    <div>
                      <p className="font-bold text-xs">Competitive Price</p>
                      <p className="text-xs font-normal opacity-80">
                        {priceIntel.summary.our_advantage_pct.toFixed(0)}% below market average
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
