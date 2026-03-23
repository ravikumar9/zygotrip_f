'use client';

import { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getHotel, fetchPricingIntelligence } from '@/services/hotels';
import { checkoutService } from '@/services/checkout';
import type { RoomType, RoomMealPlan, PricingIntelligence } from '@/types';
import { personalization } from '@/lib/personalization';
// CouponSuggestionCard is used on the booking page, not here

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
const ReviewSection = dynamic(() => import('@/components/hotels/ReviewSection'), {
  loading: () => <div className="h-48 bg-neutral-100 animate-pulse rounded-2xl" />,
  ssr: false,
});
const PriceCalendar = dynamic(() => import('@/components/hotels/PriceCalendar'), {
  loading: () => <div className="h-48 bg-neutral-100 animate-pulse rounded-2xl" />,
  ssr: false,
});
const AmenityBreakdown = dynamic(() => import('@/components/hotels/AmenityBreakdown'), {
  loading: () => <div className="h-32 bg-neutral-100 animate-pulse rounded-2xl" />,
  ssr: false,
});
import {
  MapPin, Star, Shield, AlertCircle, ChevronRight, Check,
  Calendar, Users, Minus, Plus, ArrowLeft, Share2, Heart,
  Wifi, ParkingCircle, Utensils, Waves, Dumbbell, Wind, Bed,
  Tag, TrendingDown, BadgeCheck,
} from 'lucide-react';
import WishlistButton from '@/components/hotels/WishlistButton';
import { HotelShareButton } from '@/components/social/ShareButton';
import toast from 'react-hot-toast';
import { addDays, format, parseISO, isValid } from 'date-fns';
import { clsx } from 'clsx';
import { useFormatPrice } from '@/hooks/useFormatPrice';

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

const TABS = ['Room Options', 'Amenities', 'Location', 'Reviews', 'Policies'] as const;
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
  const { formatPrice: fmt } = useFormatPrice();
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
  const [bookingLoading, setBookingLoading] = useState(false);
  const [mealFilter, setMealFilter] = useState('');  // '' = all plans

  // ── Price intelligence state ─────────────────────────────────
  const [priceIntel, setPriceIntel] = useState<PricingIntelligence | null>(null);

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

  // Track hotel view for "Recently Viewed" personalization on homepage
  useEffect(() => {
    if (!property) return;
    personalization.trackView({
      id: property.id,
      name: property.name,
      slug: property.slug,
      city: property.city_name || '',
      image: property.images?.[0]?.url,
      price: property.min_price,
      rating: parseFloat(property.rating) || undefined,
      stars: property.star_category,
    });
  }, [property?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBook = async () => {
    if (!property || !checkIn || !checkOut) return;
    if (!selectedRoom) {
      setActiveTab('Room Options');
      toast('Select a room type from the Room Options tab first', { icon: '👆', duration: 4000 });
      return;
    }
    setBookingLoading(true);
    try {
      const session = await checkoutService.startCheckout({
        property_id: property.id,
        room_type_id: selectedRoom.id,
        check_in: checkIn,
        check_out: checkOut,
        guests,
        rooms,
        meal_plan_code: selectedMealPlan?.code || 'R',
      });
      router.push(`/checkout/${session.session_id}`);
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
          const order = ['R', 'R+B', 'R+B+L/D', 'R+A'];
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
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex items-center gap-6">
          {/* Back */}
          <button
            onClick={() => router.back()}
            className="text-white/70 hover:text-white flex items-center gap-1.5 text-xs font-semibold shrink-0 transition-colors"
          >
            <ArrowLeft size={14} /> Back
          </button>
          <div className="w-px h-5 bg-white/80/20" />
          {/* Property name */}
          <p className="font-bold text-white text-sm truncate max-w-xs">{property.name}</p>
          <div className="w-px h-5 bg-white/80/20" />
          {/* Dates */}
          <div className="flex items-center gap-1.5 text-white/80 text-xs font-medium">
            <Calendar size={11} className="text-primary-300" />
            <span>{fmtDateCompact(checkIn)}</span>
            <span className="text-white/40 mx-1">→</span>
            <span>{fmtDateCompact(checkOut)}</span>
            {nights > 0 && <span className="text-white/50 ml-1">({nights}N)</span>}
          </div>
          <div className="w-px h-5 bg-white/80/20" />
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

      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {/* Back / actions bar — mobile only */}
        <div className="flex items-center justify-between mb-5 lg:hidden">
          <button onClick={() => router.back()} className="flex items-center gap-2 text-neutral-600 hover:text-neutral-900 font-semibold text-sm transition-colors">
            <ArrowLeft size={18} /> Back
          </button>
          <div className="flex items-center gap-2">
            <HotelShareButton
              propertyName={property?.name ?? ''}
              slug={slug}
              city={property?.city_name}
            />
            {property?.id && (
              <WishlistButton
                propertyId={property.id}
                variant="button"
                size="sm"
              />
            )}
          </div>
        </div>

        {/* Desktop share/save — above gallery */}
        <div className="hidden lg:flex items-center justify-end gap-2 mb-4">
          <HotelShareButton
            propertyName={property?.name ?? ''}
            slug={slug}
            city={property?.city_name}
          />
          {property?.id && (
            <WishlistButton
              propertyId={property.id}
              variant="button"
              size="sm"
            />
          )}
        </div>

        {/* Gallery */}
        <PropertyGallery images={property.images} propertyName={property.name} />

        {/* Urgency & trust signals strip */}
        <div className="flex items-center gap-3 bg-gradient-to-r from-green-50 via-emerald-50 to-green-50 border border-green-200 rounded-xl px-4 py-3 my-4 overflow-x-auto">
          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="flex items-center gap-1.5 text-green-700"><Check size={13} className="text-green-600" /> Free Cancellation</span>
            <span className="flex items-center gap-1.5 text-green-700"><Shield size={13} className="text-green-600" /> Instant Confirmation</span>
            <span className="flex items-center gap-1.5 text-green-700"><BadgeCheck size={13} className="text-green-600" /> Best Price Guaranteed</span>
          </div>
          {/* Urgency signals from backend data */}
          <div className="ml-auto flex items-center gap-2 shrink-0">
            {property.bookings_today > 0 && (
              <span className="text-2xs font-bold text-orange-700 bg-orange-100 px-2 py-1 rounded-full whitespace-nowrap">
                🔥 Booked {property.bookings_today}x today
              </span>
            )}
            {property.available_rooms != null && property.available_rooms > 0 && property.available_rooms <= 5 && (
              <span className="text-2xs font-bold text-red-700 bg-red-50 px-2 py-1 rounded-full animate-pulse-soft whitespace-nowrap">
                ⚡ Only {property.available_rooms} rooms left
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_380px] gap-6">

          {/* ── Left content ──────────────────────────────────────── */}
          <div className="space-y-5">

            {/* Header card */}
            <div className="bg-white/80 rounded-2xl p-6 shadow-card">
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
            <div className="bg-white/80 rounded-2xl shadow-card overflow-hidden">
              <div className="flex overflow-x-auto border-b border-neutral-100">
                {TABS.map((tab) => (
                  <button key={tab} onClick={() => setActiveTab(tab)} className={`tab-nav ${activeTab === tab ? 'active' : ''}`}>
                    {tab}
                    {tab === 'Room Options' && (property.room_types?.length ?? 0) > 0 && (
                      <span className="ml-1.5 text-xs bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded-full">
                        {property.room_types.length}
                      </span>
                    )}
                    {tab === 'Reviews' && property.review_count > 0 && (
                      <span className="ml-1.5 text-xs bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded-full">
                        {property.review_count}
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
                                : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-400 hover:text-primary-600'
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
                    {property.amenities && property.amenities.length > 0 ? (
                      <AmenityBreakdown amenities={property.amenities} />
                    ) : (
                      <div className="text-center py-10 text-neutral-400">
                        <Wifi size={32} className="mx-auto mb-2 opacity-30" />
                        <p className="text-sm">No amenities listed for this property.</p>
                      </div>
                    )}
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
                  <div className="space-y-4">
                    {/* Check-in / Check-out times */}
                    {(property.check_in_time || property.check_out_time) && (
                      <div className="grid grid-cols-2 gap-3">
                        {property.check_in_time && (
                          <div className="bg-green-50 border border-green-100 rounded-xl p-4">
                            <p className="text-xs text-green-600 font-semibold uppercase tracking-wider mb-1">Check-in from</p>
                            <p className="text-xl font-black text-green-800">{property.check_in_time}</p>
                          </div>
                        )}
                        {property.check_out_time && (
                          <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                            <p className="text-xs text-amber-600 font-semibold uppercase tracking-wider mb-1">Check-out by</p>
                            <p className="text-xl font-black text-amber-800">{property.check_out_time}</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* House rules */}
                    {property.house_rules && (
                      <div className="rounded-xl bg-page p-4 border border-neutral-100">
                        <h4 className="font-semibold text-neutral-800 text-sm mb-2 flex items-center gap-2">
                          <Shield size={13} className="text-primary-400" /> House Rules
                        </h4>
                        <p className="text-sm text-neutral-600 leading-relaxed whitespace-pre-line">{property.house_rules}</p>
                      </div>
                    )}

                    {/* Cancellation policy */}
                    {property.has_free_cancellation !== undefined && (
                      <div className={`rounded-xl p-4 border ${property.has_free_cancellation ? 'bg-green-50 border-green-100' : 'bg-orange-50 border-orange-100'}`}>
                        <h4 className={`font-semibold text-sm mb-1 flex items-center gap-2 ${property.has_free_cancellation ? 'text-green-800' : 'text-orange-800'}`}>
                          <Check size={13} /> Cancellation Policy
                        </h4>
                        <p className={`text-sm leading-relaxed ${property.has_free_cancellation ? 'text-green-700' : 'text-orange-700'}`}>
                          {property.has_free_cancellation
                            ? `Free cancellation up to ${property.cancellation_hours || 48} hours before check-in.`
                            : 'This property has a strict cancellation policy. Please review before booking.'}
                        </p>
                      </div>
                    )}

                    {/* Other policies */}
                    {property.policies && property.policies.length > 0 && property.policies.map((p: any) => (
                      <div key={p.id} className="rounded-xl bg-page p-4 border border-neutral-100">
                        <h4 className="font-semibold text-neutral-800 text-sm mb-1 flex items-center gap-2">
                          <AlertCircle size={13} className="text-orange-400" />{p.title}
                        </h4>
                        <p className="text-sm text-neutral-500 leading-relaxed">{p.description}</p>
                      </div>
                    ))}

                    {!property.check_in_time && !property.check_out_time && !property.house_rules && !(property.policies?.length) && (
                      <div className="text-center py-8 text-neutral-400">
                        <AlertCircle size={28} className="mx-auto mb-2 opacity-40" />
                        <p className="text-sm">No specific policies listed for this property.</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'Reviews' && (
                  <ReviewSection
                    propertyId={property.id}
                    propertySlug={property.slug}
                    propertyName={property.name}
                    overallRating={parseFloat(String(property.rating)) || 0}
                    reviewCount={property.review_count || 0}
                    ratingBreakdown={property.rating_breakdown}
                  />
                )}
              </div>
            </div>

            {/* Price Calendar */}
            {property.id && (
              <PriceCalendar
                propertyId={property.id}
                roomTypeId={selectedRoom?.id}
                onDateSelect={(ci, co) => { setCheckIn(ci); setCheckOut(co); }}
              />
            )}
          </div>

          {/* ── Booking Panel (Sticky Sidebar) ───────────────────── */}
          <div>
            <div className="booking-panel p-5 sticky top-24">
              {/* Price hero with discount */}
              <div className="text-center mb-5 pb-4 border-b border-neutral-100">
                <p className="text-xs text-neutral-400">Starting from</p>
                <div className="flex items-baseline justify-center gap-2 mt-0.5">
                  {property.rack_rate && property.rack_rate > property.min_price && (
                    <span className="text-sm text-neutral-400 line-through">
                      {fmt(property.rack_rate)}
                    </span>
                  )}
                  <p className="text-3xl font-black text-neutral-900 font-heading">
                    {fmt(property.min_price)}
                  </p>
                  {property.rack_rate && property.rack_rate > property.min_price && (
                    <span className="text-xs font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                      {Math.round(((property.rack_rate - property.min_price) / property.rack_rate) * 100)}% off
                    </span>
                  )}
                </div>
                <p className="text-xs text-neutral-400">per night + taxes</p>
                {/* Cashback incentive */}
                {property.cashback_amount && property.cashback_amount > 0 && (
                  <p className="text-2xs font-bold text-emerald-600 mt-2 bg-emerald-50 inline-block px-2 py-0.5 rounded-full">
                    🎁 Earn {fmt(property.cashback_amount)} cashback
                  </p>
                )}
              </div>

              {/* Dates */}
              <div className="grid grid-cols-2 gap-2 mb-3">
                {[
                  { label: 'Check-in', val: checkIn, min: format(tomorrow, 'yyyy-MM-dd'), set: setCheckIn },
                  { label: 'Check-out', val: checkOut, min: checkIn || format(tomorrow, 'yyyy-MM-dd'), set: setCheckOut },
                ].map((d) => (
                  <div key={d.label}>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">{d.label}</label>
                    <div className="flex items-center gap-1 bg-page rounded-xl px-2.5 py-2.5 border border-neutral-200 focus-within:border-primary-400">
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
                  { label: 'Guests', val: guests, min: 1, max: 12, set: setGuests },
                  { label: 'Rooms', val: rooms, min: 1, max: 8, set: setRooms },
                ].map((item) => (
                  <div key={item.label}>
                    <label className="text-xs font-semibold text-neutral-500 block mb-1">{item.label}</label>
                    <div className="flex items-center justify-between bg-page rounded-xl px-2.5 py-2.5 border border-neutral-200">
                      <button type="button" onClick={() => item.set(Math.max(item.min, item.val - 1))}
                        className="w-6 h-6 rounded-full bg-white/80 border border-neutral-300 flex items-center justify-center hover:border-primary-400">
                        <Minus size={10} />
                      </button>
                      <span className="text-sm font-bold">{item.val}</span>
                      <button type="button" onClick={() => item.set(Math.min(item.max, item.val + 1))}
                        className="w-6 h-6 rounded-full bg-white/80 border border-neutral-300 flex items-center justify-center hover:border-primary-400">
                        <Plus size={10} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Promo codes are applied at checkout — show hint */}
              <div className="flex items-center gap-2 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2.5 mb-4">
                <Tag size={12} className="text-amber-600 shrink-0" />
                <p className="text-xs text-amber-700">Have a promo code? Apply it at checkout for exclusive discounts</p>
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
                <div className="bg-page rounded-xl p-3.5 mb-4 border border-neutral-200">
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

                  <div className="flex justify-between text-xs text-neutral-400 mb-2">
                    <span>Taxes &amp; fees (GST)</span>
                    <span className="italic">calculated at checkout</span>
                  </div>
                  <div className="pt-2 border-t border-neutral-200 flex justify-between">
                    <span className="font-bold text-xs text-neutral-700">Estimated subtotal</span>
                    <span className="font-black text-sm text-neutral-900">{fmt(estimatedTotal)}</span>
                  </div>
                  <p className="text-[10px] text-neutral-400 mt-1 text-center">
                    Final price confirmed at checkout
                  </p>
                </div>
              )}

              {/* Savings celebration banner */}
              {nights > 0 && property.rack_rate && property.rack_rate > property.min_price && selectedRoom && (
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-xl p-3 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">🎉</span>
                    <div>
                      <p className="text-xs font-bold text-green-700">
                        You save {fmt((property.rack_rate - property.min_price) * nights * rooms)}
                      </p>
                      <p className="text-2xs text-green-600">
                        Room discount applied
                      </p>
                    </div>
                  </div>
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

      {/* ── Sticky Mobile Booking Bar ─────────────────────────────── */}
      <div className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/80 border-t border-neutral-200 shadow-[0_-4px_20px_rgba(0,0,0,0.1)] px-4 py-3 safe-area-bottom">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            {selectedRoom ? (
              <>
                <p className="text-lg font-black text-neutral-900 font-heading leading-tight">
                  {fmt(pricePerNight)}
                  <span className="text-xs font-normal text-neutral-400">/night</span>
                </p>
                <p className="text-[10px] text-neutral-500 truncate">
                  {selectedRoom.name}{selectedMealPlan ? ` · ${selectedMealPlan.name}` : ''}
                  {nights > 0 && <> · {nights}N · {fmt(estimatedTotal)}</>}
                </p>
              </>
            ) : (
              <>
                <p className="text-lg font-black text-neutral-900 font-heading leading-tight">
                  {property?.min_price ? fmt(property.min_price) : '—'}
                </p>
                <p className="text-[10px] text-neutral-400">per night + taxes</p>
              </>
            )}
          </div>
          <button
            onClick={handleBook}
            disabled={bookingLoading || !selectedRoom}
            className="btn-primary px-6 py-3 text-sm font-bold shrink-0 disabled:opacity-50"
          >
            {bookingLoading ? 'Booking…' : selectedRoom ? 'Book Now' : 'Select a Room'}
          </button>
        </div>
      </div>
      {/* Spacer for mobile sticky bar */}
      <div className="lg:hidden h-20" />
    </div>
  );
}
