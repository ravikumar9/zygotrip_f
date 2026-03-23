'use client';

const MEAL_PLAN_LABELS: Record<string, string> = {
  'EP': 'Room Only (No Meals)',
  'CP': 'Continental Plan (Breakfast)',
  'MAP': 'Modified American Plan (Breakfast + Dinner)',
  'AP': 'American Plan (All Meals)',
  'AI': 'All Inclusive',
};


import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import {
  MapPin,
  Star,
  ChevronLeft,
  Share2,
  Heart,
  Shield,
  Clock,
  CheckCircle,
  AlertCircle,
  Info,
  Phone,
  ChevronRight,
  Coffee,
  Check,
  Navigation,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { getPropertyDetail } from '@/services/hotels';
import { checkoutService } from '@/services/checkout';
import { analytics, bookingFunnel } from '@/lib/analytics';
import PropertyGallery from '@/components/hotels/PropertyGallery';
import RoomSelector from '@/components/hotels/RoomSelector';
import ReviewSection from '@/components/hotels/ReviewSection';
import PriceCalendar from '@/components/hotels/PriceCalendar';
import PropertyMap from '@/components/hotels/PropertyMap';
import AmenityBreakdown from '@/components/hotels/AmenityBreakdown';
import CancellationPolicy from '@/components/hotels/CancellationPolicy';
import Skeleton from '@/components/ui/Skeleton';
import { useFormatPrice } from '@/hooks/useFormatPrice';
import type { Property, RoomType, RoomMealPlan, PropertyImage, PropertyAmenity } from '@/types';

type PropertyDetailShape = Property & {
  images?: PropertyImage[];
  amenities?: PropertyAmenity[];
  room_types?: RoomType[];
  review_count?: number;
  rack_rate?: number;
  has_breakfast?: boolean;
  rating_tier?: string;
};

function useSearchContext() {
  const sp = useSearchParams();
  return {
    checkin: sp.get('checkin') || '',
    checkout: sp.get('checkout') || '',
    adults: parseInt(sp.get('adults') || '2', 10),
    children: parseInt(sp.get('children') || '0', 10),
    rooms: parseInt(sp.get('rooms') || '1', 10),
    location: sp.get('location') || '',
  };
}

function StickyBookingBar({
  property,
  minPrice,
  onBookNow,
}: {
  property: PropertyDetailShape;
  minPrice: number;
  onBookNow: () => void;
}) {
  const { formatPrice } = useFormatPrice();

  return (
    <div className="hidden lg:flex fixed top-0 left-0 right-0 z-40 bg-white/80 border-b border-neutral-200 shadow-sm items-center gap-6 px-6 py-3">
      <div className="flex-1 min-w-0">
        <h2 className="font-bold text-neutral-900 text-sm truncate">{property.name}</h2>
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <MapPin size={11} />
          {property.city_name}
          {property.rating && (
            <>
              <Star size={11} className="text-amber-400 fill-amber-400 ml-1" />
              {property.rating}
            </>
          )}
        </div>
      </div>
      {minPrice > 0 && (
        <div className="text-right">
          <p className="text-lg font-black text-neutral-900">{formatPrice(minPrice)}</p>
          <p className="text-xs text-neutral-400">per night + taxes</p>
        </div>
      )}
      <button
        onClick={onBookNow}
        className="bg-primary-600 hover:bg-primary-700 text-white font-bold px-6 py-2.5 rounded-xl transition-colors text-sm"
      >
        Book Now
      </button>
    </div>
  );
}

export default function HotelDetailPage() {
  const params = useParams();
  const router = useRouter();
  const ctx = useSearchContext();
  const { formatPrice } = useFormatPrice();

  const slug =
    typeof params.slug === 'string'
      ? params.slug
      : Array.isArray(params.slug)
        ? params.slug[0]
        : '';

  const [selectedRoom, setSelectedRoom] = useState<RoomType | null>(null);
  const [selectedMealPlan, setSelectedMealPlan] = useState<RoomMealPlan | undefined>(undefined);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [isBooking, setIsBooking] = useState(false);
  const [wishlisted, setWishlisted] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'rooms' | 'reviews' | 'location' | 'policies'>('overview');

  const { data, isLoading, error } = useQuery({
    queryKey: ['property', slug, ctx.checkin, ctx.checkout, ctx.rooms],
    queryFn: () => getPropertyDetail(slug, ctx.checkin, ctx.checkout, ctx.rooms),
    enabled: !!slug,
    retry: 2,
  });

  const property = (data as PropertyDetailShape | undefined) ?? null;
  const roomTypes = property?.room_types ?? [];

  useEffect(() => {
    if (!property) return;

    bookingFunnel.enter('hotel_page_viewed', {
      property_id: property.id,
      property_name: property.name,
      source: 'direct',
    });
  }, [property]);

  const handleRoomSelect = useCallback(
    (room: RoomType, mealPlan?: RoomMealPlan) => {
      setSelectedRoom(room);
        setTimeout(() => {
          const bookBtn = document.getElementById('book-now-btn');
          if (bookBtn) bookBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);;
      setSelectedMealPlan(mealPlan);
      setBookingError(null);
      analytics.track('room_selected', {
        property_id: property?.id,
        room_type_id: room.id,
        meal_plan: mealPlan?.code,
      });
    },
    [property?.id],
  );

  const scrollToRooms = useCallback(() => {
    setActiveTab('rooms');
    document.getElementById('rooms-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const handleBookNow = useCallback(async () => {
    if (!property) return;

    if (!selectedRoom) {
      scrollToRooms();
      return;
    }

    if (!ctx.checkin || !ctx.checkout) {
      setBookingError('Please select check-in and check-out dates before booking.');
      return;
    }

    setIsBooking(true);
    setBookingError(null);

    try {
      analytics.track('booking_started', {
        property_id: property.id,
        room_type_id: selectedRoom.id,
        checkin: ctx.checkin,
        checkout: ctx.checkout,
      });

      const session = await checkoutService.startCheckout({
        property_id: property.id,
        room_type_id: selectedRoom.id,
        check_in: ctx.checkin,
        check_out: ctx.checkout,
        guests: ctx.adults + ctx.children,
        rooms: ctx.rooms,
        meal_plan_code: selectedMealPlan?.code || '',
        device_type: 'web',
        traffic_source: 'hotel_detail',
      });

      router.push(`/checkout/${session.session_id}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : (err as { response?: { data?: { error?: string } } })?.response?.data?.error ||
            'Could not initiate booking. Please try again.';
      setBookingError(message);
      analytics.track('booking_failed', { property_id: property.id, error: message });
    } finally {
      setIsBooking(false);
    }
  }, [property, selectedRoom, selectedMealPlan, ctx, router, scrollToRooms]);

  const handleBack = () => {
    const sp = new URLSearchParams();
    if (ctx.checkin) sp.set('checkin', ctx.checkin);
    if (ctx.checkout) sp.set('checkout', ctx.checkout);
    if (ctx.adults) sp.set('adults', String(ctx.adults));
    if (ctx.children) sp.set('children', String(ctx.children));
    if (ctx.rooms) sp.set('rooms', String(ctx.rooms));
    if (ctx.location) sp.set('location', ctx.location);
    router.push(`/hotels?${sp.toString()}`);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen page-listing-bg">
        <div className="max-w-6xl mx-auto px-4 pt-6 pb-16">
          <Skeleton className="h-80 w-full rounded-2xl mb-6" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-48 w-full rounded-xl" />
            </div>
            <div>
              <Skeleton className="h-72 w-full rounded-xl" />
            </div>
          </div>
        </div>
</div>
    );
  }

  if (error || !property) {
    return (
      <div className="min-h-screen page-listing-bg">
        <div className="max-w-2xl mx-auto px-4 py-20 text-center">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-neutral-900 mb-2">Hotel Not Found</h1>
          <p className="text-neutral-500 mb-6">
            The property you are looking for does not exist or is currently unavailable.
          </p>
          <Link
            href="/hotels"
            className="bg-primary-600 text-white font-bold px-6 py-3 rounded-xl hover:bg-primary-700 transition-colors inline-block"
          >
            Search Hotels
          </Link>
        </div>
</div>
    );
  }

  const computedMin = roomTypes.length
    ? roomTypes.reduce((min, r) => Math.min(min, Number(r.base_price) || min), Number(roomTypes[0].base_price) || 0)
    : 0;
  const minPrice = property.min_price || computedMin || 0;
  const ratingNum = parseFloat(String(property.rating || '0'));

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'rooms', label: `Room Options ${roomTypes.length ? `(${roomTypes.length})` : ''}` },
    { id: 'reviews', label: `Reviews ${(property.review_count || 0) ? `(${property.review_count})` : ''}` },
    { id: 'location', label: 'Location' },
    { id: 'policies', label: 'Policies' },
  ];

  const galleryImages =
    property.images && property.images.length > 0
      ? property.images
      : property.primary_image
        ? [{ id: 0, url: property.primary_image, caption: property.name, is_featured: true, display_order: 0 }]
        : [];

  const amenityObjects: PropertyAmenity[] =
    property.amenities && property.amenities.length > 0
      ? property.amenities
      : (property.amenity_names || []).map((name, idx) => ({ id: idx, name }));

  return (
    <div className="min-h-screen page-listing-bg">
      <StickyBookingBar property={property} minPrice={minPrice} onBookNow={handleBookNow} />

      <div className="max-w-6xl mx-auto px-4 pt-4">
        <button
          onClick={handleBack}
          className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-primary-600 transition-colors mb-3"
        >
          <ChevronLeft size={16} /> Back to results
        </button>

        {ctx.checkin && ctx.checkout && (
          <div className="flex items-center gap-2 text-sm font-medium text-neutral-700 bg-white/80 border border-neutral-200 rounded-xl px-4 py-2 mb-4 w-fit shadow-sm">
            <Clock size={14} className="text-primary-500" />
            <span>{ctx.checkin}</span>
            <ChevronRight size={14} className="text-neutral-300" />
            <span>{ctx.checkout}</span>
            <span className="text-neutral-400 mx-1">·</span>
            <span>
              {ctx.adults} Guest{ctx.adults > 1 ? 's' : ''}
            </span>
            <span className="text-neutral-400 mx-1">·</span>
            <span>
              {ctx.rooms} Room{ctx.rooms > 1 ? 's' : ''}
            </span>
          </div>
        )}
      </div>

      <div className="max-w-6xl mx-auto px-4 mb-6">
        <PropertyGallery images={galleryImages} propertyName={property.name} />
      </div>

      <div className="max-w-6xl mx-auto px-4 pb-16">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white/80 rounded-2xl p-5 shadow-sm border border-neutral-100">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex-1 min-w-0">
                  <span className="text-xs text-primary-600 font-semibold uppercase tracking-wide">
                    {property.property_type || 'Hotel'}
                    {property.star_category && ` · ${property.star_category}★`}
                  </span>
                  <h1 className="text-2xl font-black text-neutral-900 mt-1 leading-tight">{property.name}</h1>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => setWishlisted((v) => !v)}
                    className="p-2 rounded-full border border-neutral-200 hover:bg-red-50 transition-colors"
                  >
                    <Heart size={16} fill={wishlisted ? '#eb5757' : 'none'} stroke={wishlisted ? '#eb5757' : '#374151'} />
                  </button>
                  <button className="p-2 rounded-full border border-neutral-200 hover:bg-page transition-colors">
                    <Share2 size={16} className="text-neutral-600" />
                  </button>
                </div>
              </div>

              {ratingNum > 0 && (
                <div className="flex items-center gap-2 mb-3">
                  <div className="flex items-center gap-1 bg-green-600 text-white text-sm font-bold px-2.5 py-1 rounded-lg">
                    <Star size={13} fill="white" stroke="none" />
                    {ratingNum.toFixed(1)}
                  </div>
                  {property.rating_tier && <span className="text-sm font-semibold text-green-700">{property.rating_tier}</span>}
                  {!!property.review_count && <span className="text-sm text-neutral-500">({property.review_count} reviews)</span>}
                </div>
              )}

              <p className="flex items-center gap-1.5 text-sm text-neutral-600 mb-3">
                <MapPin size={14} className="text-primary-500 shrink-0" />
                <span>{property.address || `${property.area || ''}, ${property.city_name}`}</span>
              </p>
              {property.landmark_distance && (
                <p className="flex items-center gap-1.5 text-xs text-neutral-400 mb-3">
                  <Navigation size={12} />
                  {property.landmark_distance}
                </p>
              )}

              <div className="flex flex-wrap gap-2 mb-4">
                {property.has_free_cancellation && (
                  <span className="flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-50 border border-green-100 px-2.5 py-1 rounded-full">
                    <Shield size={11} /> Free Cancellation
                  </span>
                )}
                {property.has_breakfast && (
                  <span className="flex items-center gap-1 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-100 px-2.5 py-1 rounded-full">
                    <Coffee size={11} /> Breakfast Included
                  </span>
                )}
                <span className="flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-100 px-2.5 py-1 rounded-full">
                  <CheckCircle size={11} /> Instant Confirmation
                </span>
              </div>
            </div>

            <div className="bg-white/80 rounded-2xl shadow-sm border border-neutral-100 overflow-hidden">
              <div className="flex overflow-x-auto border-b border-neutral-100 scrollbar-hide">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as 'overview' | 'rooms' | 'reviews' | 'location' | 'policies')}
                    className={[
                      'px-5 py-3 text-sm font-semibold whitespace-nowrap transition-colors border-b-2 -mb-px',
                      activeTab === tab.id
                        ? 'border-primary-600 text-primary-600'
                        : 'border-transparent text-neutral-500 hover:text-neutral-700',
                    ].join(' ')}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="p-5">
                {activeTab === 'overview' && <AmenityBreakdown amenities={amenityObjects} />}

                {activeTab === 'rooms' && (
                  <div id="rooms-section">
                    {(!ctx.checkin || !ctx.checkout) && (
                      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4 flex items-start gap-3">
                        <Info size={16} className="text-amber-600 shrink-0 mt-0.5" />
                        <p className="text-sm text-amber-800">Select your dates above to see availability and exact pricing.</p>
                      </div>
                    )}

                    {roomTypes.length > 0 ? (
                      <RoomSelector
                        rooms={roomTypes}
                        selectedRoomId={selectedRoom?.id}
                        selectedMealPlanCode={selectedMealPlan?.code}
                        onSelect={handleRoomSelect}
                      />
                    ) : (
                      <div className="text-center py-10 text-neutral-400">
                        <AlertCircle className="w-10 h-10 mx-auto mb-3 opacity-40" />
                        <p className="text-sm font-medium">No rooms available for selected dates</p>
                        <p className="text-xs mt-1">Try different dates or fewer guests</p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'reviews' && (
                  <ReviewSection
                    propertyId={property.id}
                    propertySlug={slug}
                    propertyName={property.name}
                    overallRating={ratingNum}
                    reviewCount={property.review_count || 0}
                  />
                )}

                {activeTab === 'location' && (
                  <div className="space-y-4">
                    <p className="flex items-start gap-2 text-sm text-neutral-600">
                      <MapPin size={16} className="text-primary-500 shrink-0 mt-0.5" />
                      {property.address || property.city_name}
                    </p>
                    {property.latitude && property.longitude && (
                      <PropertyMap
                        latitude={property.latitude}
                        longitude={property.longitude}
                        name={property.name}
                        address={property.address}
                      />
                    )}
                  </div>
                )}

                {activeTab === 'policies' && (
                  <CancellationPolicy
                    type={property.has_free_cancellation ? 'free' : 'non_refundable'}
                    checkinDate={ctx.checkin || undefined}
                  />
                )}
              </div>
            </div>

            {property.id ? (
              <div className="bg-white/80 rounded-2xl p-5 shadow-sm border border-neutral-100">
                <h3 className="font-bold text-neutral-900 text-base mb-4">Price Calendar</h3>
                <PriceCalendar
                  propertyId={property.id}
                  roomTypeId={selectedRoom?.id}
                  onDateSelect={(newCheckin, newCheckout) => {
                    const sp = new URLSearchParams(window.location.search);
                    sp.set('checkin', newCheckin);
                    sp.set('checkout', newCheckout);
                    router.replace(`/hotels/${slug}?${sp.toString()}`);
                  }}
                />
              </div>
            ) : null}
          </div>

          <div className="lg:col-span-1">
            <div className="sticky top-4 space-y-4">
              <div className="bg-white/80 rounded-2xl shadow-card border border-neutral-100 p-5">
                <div className="mb-4">
                  {minPrice > 0 && (
                    <div className="flex items-end gap-2">
                      <span className="text-3xl font-black text-neutral-900">{formatPrice(minPrice)}</span>
                      <span className="text-sm text-neutral-400 pb-1">/ night + taxes</span>
                    </div>
                  )}
                  {!!property.rack_rate && property.rack_rate > minPrice && (
                    <p className="text-sm text-neutral-400 line-through">{formatPrice(property.rack_rate)}</p>
                  )}
                </div>

                {selectedRoom ? (
                  <div className="bg-primary-50 border border-primary-200 rounded-xl p-3 mb-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-primary-600 font-semibold">Selected Room</p>
                        <p className="text-sm font-bold text-neutral-900">{selectedRoom.name}</p>
                        {selectedMealPlan && <p className="text-xs text-neutral-500">{selectedMealPlan.name}</p>}
                      </div>
                      <Check size={18} className="text-primary-600" />
                    </div>
                  </div>
                ) : (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-4">
                    <p className="text-xs text-amber-700 font-medium">Select a room from the Rooms tab to proceed</p>
                  </div>
                )}

                {bookingError && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-3 mb-4 flex items-start gap-2">
                    <AlertCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-red-700">{bookingError}</p>
                  </div>
                )}

                <button
                  onClick={handleBookNow}
                  disabled={isBooking}
                  className={[
                    'w-full py-4 rounded-xl font-bold text-white text-base transition-all',
                    isBooking
                      ? 'bg-neutral-400 cursor-not-allowed'
                      : 'bg-primary-600 hover:bg-primary-700 active:bg-primary-800 shadow-md hover:shadow-lg',
                  ].join(' ')}
                >
                  {isBooking ? 'Processing...' : selectedRoom ? `Book ${selectedRoom.name} Now →` : 'Select a Room to Book'}
                </button>

                <div className="mt-4 space-y-2">
                  <p className="flex items-center gap-2 text-xs text-neutral-500">
                    <Shield size={12} className="text-green-500" /> Secure checkout — SSL encrypted
                  </p>
                  <p className="flex items-center gap-2 text-xs text-neutral-500">
                    <CheckCircle size={12} className="text-green-500" /> Instant booking confirmation
                  </p>
                  <p className="flex items-center gap-2 text-xs text-neutral-500">
                    <Phone size={12} className="text-blue-500" /> 24/7 customer support
                  </p>
                </div>
              </div>

              <div className="bg-blue-50 rounded-xl p-4 text-center">
                <p className="text-xs text-blue-700 font-medium mb-1">Need help booking?</p>
                <p className="text-xs text-blue-600">Call us: +91 1800-XXX-XXXX</p>
              </div>
            </div>
          </div>
        </div>
      </div>
</div>
  );
}
