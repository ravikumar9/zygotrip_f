'use client';

















































































































































































































    return points    logger.info('Loyalty bonus: user=%s points=%d desc=%s', user.id, points, description)    account._refresh_tier()    )        reference_id=str(reference_id),        reference_type=reference_type,        description=description,        points=points,        txn_type=LoyaltyTransaction.TYPE_BONUS,        account=account,    LoyaltyTransaction.objects.create(    account.save(update_fields=['total_points_earned', 'available_points', 'updated_at'])    account.available_points += points    account.total_points_earned += points    account = get_or_create_loyalty_account(user)    """Award bonus loyalty points (review, referral, birthday, etc.)."""def award_bonus(user, points: int, description: str, reference_type='', reference_id=''):@transaction.atomic    return discount    logger.info('Loyalty redeem: user=%s points=%d discount=₹%s', user.id, points_to_redeem, discount)    )        description=f'Redeemed {points_to_redeem} pts for ₹{discount} discount',        points=-points_to_redeem,        txn_type=LoyaltyTransaction.TYPE_REDEEM,        account=account,    LoyaltyTransaction.objects.create(    account.save(update_fields=['available_points', 'updated_at'])    account.available_points -= points_to_redeem    discount = Decimal(points_to_redeem) / 100 * 10  # 100 pts = ₹10        raise ValueError(f'Insufficient points: {account.available_points} available, {points_to_redeem} requested')    if account.available_points < points_to_redeem:    account = get_or_create_loyalty_account(user)        raise ValueError('Minimum 500 points required to redeem')    if points_to_redeem < 500:    """    Returns the discount amount in INR.    100 points = ₹10. Minimum 500 points.    Redeem loyalty points for a discount.    """def redeem_points(user, points_to_redeem: int) -> Decimal:@transaction.atomic    return final_points    logger.info('Loyalty earn: user=%s points=%d ref=%s:%s', user.id, final_points, reference_type, reference_id)    account._refresh_tier()    )        reference_id=str(reference_id),        reference_type=reference_type,        description=f'Earned {final_points} pts for ₹{amount_spent} spend',        points=final_points,        txn_type=LoyaltyTransaction.TYPE_EARN,        account=account,    LoyaltyTransaction.objects.create(    account.save(update_fields=['total_points_earned', 'available_points', 'updated_at'])    account.available_points += final_points    account.total_points_earned += final_points        return 0    if final_points <= 0:    final_points = int(Decimal(base_points) * multiplier)    base_points = int(amount_spent / 100) * 10    multiplier = LoyaltyTier.MULTIPLIERS.get(account.tier, Decimal('1.0'))    account = get_or_create_loyalty_account(user)    """    10 points per ₹100 spent, multiplied by tier multiplier.    Award loyalty points for a purchase.    """def earn_points(user, amount_spent: Decimal, reference_type='booking', reference_id=''):@transaction.atomic    return account    account, _ = LoyaltyAccount.objects.get_or_create(user=user)    """Get or create a loyalty account for the user."""def get_or_create_loyalty_account(user):# ── Service functions ──────────────────────────────────────────────────────────        ordering = ['-created_at']        db_table = 'core_loyalty_transaction'        app_label = 'core'    class Meta:    reference_id = models.CharField(max_length=50, blank=True)    reference_type = models.CharField(max_length=50, blank=True)  # 'booking', 'review', 'referral'    description = models.CharField(max_length=200, blank=True)    points = models.IntegerField()  # positive for credits, negative for debits    txn_type = models.CharField(max_length=10, choices=TYPE_CHOICES)    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name='transactions')    ]        (TYPE_BONUS, 'Bonus'),        (TYPE_EXPIRE, 'Expire'),        (TYPE_REDEEM, 'Redeem'),        (TYPE_EARN, 'Earn'),    TYPE_CHOICES = [    TYPE_BONUS = 'bonus'    TYPE_EXPIRE = 'expire'    TYPE_REDEEM = 'redeem'    TYPE_EARN = 'earn'    """Audit log for every points credit/debit."""class LoyaltyTransaction(TimeStampedModel):            logger.info('Loyalty tier change: user=%s %s→%s', self.user_id, old, new_tier)            self.save(update_fields=['tier', 'updated_at'])            self.tier = new_tier            old = self.tier        if new_tier != self.tier:        new_tier = LoyaltyTier.for_points(self.total_points_earned)    def _refresh_tier(self):        return f'{self.user.email} — {self.tier} ({self.available_points} pts)'    def __str__(self):        db_table = 'core_loyalty_account'        app_label = 'core'    class Meta:    ])        (LoyaltyTier.PLATINUM, 'Platinum'),        (LoyaltyTier.GOLD, 'Gold'),        (LoyaltyTier.SILVER, 'Silver'),        (LoyaltyTier.BRONZE, 'Bronze'),    tier = models.CharField(max_length=10, default=LoyaltyTier.BRONZE, choices=[    available_points = models.IntegerField(default=0)    total_points_earned = models.IntegerField(default=0)    )        related_name='loyalty_account',        on_delete=models.CASCADE,        settings.AUTH_USER_MODEL,    user = models.OneToOneField(    """Per-user loyalty account tracking points balance and tier."""class LoyaltyAccount(TimeStampedModel):        return cls.BRONZE            return cls.SILVER        elif total_points >= cls.THRESHOLDS[cls.SILVER]:            return cls.GOLD        elif total_points >= cls.THRESHOLDS[cls.GOLD]:            return cls.PLATINUM        if total_points >= cls.THRESHOLDS[cls.PLATINUM]:    def for_points(cls, total_points: int) -> str:    @classmethod    }        PLATINUM: Decimal('2.0'),        GOLD: Decimal('1.5'),        SILVER: Decimal('1.25'),        BRONZE: Decimal('1.0'),    MULTIPLIERS = {    }        PLATINUM: 50000,        GOLD: 15000,        SILVER: 5000,        BRONZE: 0,    THRESHOLDS = {    PLATINUM = 'platinum'    GOLD = 'gold'    SILVER = 'silver'    BRONZE = 'bronze'class LoyaltyTier:logger = logging.getLogger('zygotrip.loyalty')from apps.core.models import TimeStampedModelfrom django.utils import timezonefrom django.db import models, transactionfrom django.conf import settingsfrom decimal import Decimalimport logging"""  - Minimum 500 points to redeem  - 100 points = ₹10 discountPoints redemption:  - 100 bonus points on birthday  - 5 bonus points for leaving a review  - 10 points per ₹100 spent on bookingsPoints earning:  - Platinum (50000+ points): 2x points, lounge access, late checkout  - Gold (15000+ points): 1.5x points, priority support, room upgrades  - Silver (5000+ points): 1.25x points, free cancellation  - Bronze (default): 1x points, no perksTier system:import { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Check, ChevronRight, User, CreditCard, CheckCircle, Clock, Shield } from 'lucide-react';
import { useBookingContext, useCreateBooking } from '@/hooks/useBooking';
import PriceBreakdown from '@/components/booking/PriceBreakdown';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import type { BookingContext } from '@/types';
import toast from 'react-hot-toast';

type Step = 'guests' | 'review' | 'payment' | 'confirmed';

const STEPS: { id: Step; label: string; icon: React.ReactNode }[] = [
  { id: 'guests', label: 'Guest Details', icon: <User className="w-4 h-4" /> },
  { id: 'review', label: 'Review & Pay', icon: <CreditCard className="w-4 h-4" /> },
  { id: 'confirmed', label: 'Confirmed', icon: <CheckCircle className="w-4 h-4" /> },
];

export default function BookingFlow() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const contextId = searchParams.get('context_id');

  const { data: context, isLoading, error } = useBookingContext(contextId || '');
  const createBooking = useCreateBooking();

  const [step, setStep] = useState<Step>('guests');
  const [bookingId, setBookingId] = useState<string | null>(null);
  const [guestDetails, setGuestDetails] = useState({
    guest_name: '',
    guest_email: '',
    guest_phone: '',
  });
  const [promoCode, setPromoCode] = useState('');
  const [timeLeft, setTimeLeft] = useState(0);

  // Countdown timer for price lock expiry
  useEffect(() => {
    if (!context?.expires_at) return;
    const update = () => {
      const remaining = Math.max(0, Math.floor((new Date(context.expires_at!).getTime() - Date.now()) / 1000));
      setTimeLeft(remaining);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [context?.expires_at]);

  if (!contextId) {
    router.push('/hotels');
    return null;
  }
  if (isLoading) return <LoadingSpinner />;
  if (error || !context) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-sm">
          <Clock className="w-16 h-16 text-neutral-300 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-neutral-800 mb-2">Session Expired</h2>
          <p className="text-neutral-500 mb-4">Your booking session has expired. Please start again.</p>
          <button onClick={() => router.push('/hotels')} className="btn-primary">
            Search Hotels
          </button>
        </div>
      </div>
    );
  }

  const nights = Math.round(
    (new Date(context.checkout).getTime() - new Date(context.checkin).getTime()) / 86400000
  );

  const handleSubmitGuests = (e: React.FormEvent) => {
    e.preventDefault();
    setStep('review');
  };

  const handleConfirmBooking = async () => {
    try {
      const booking = await createBooking.mutateAsync({
        // context_uuid is preferred over context_id — UUID-based lookup
        context_uuid: context?.uuid || contextId,
        guest_name: guestDetails.guest_name,
        guest_email: guestDetails.guest_email,
        guest_phone: guestDetails.guest_phone,
        promo_code: promoCode || undefined,
      });
      setBookingId(booking.uuid);
      setStep('confirmed');
    } catch (err: any) {
      toast.error(err?.response?.data?.error?.message || 'Booking failed. Please try again.');
    }
  };

  const handleApplyPromo = async () => {
    if (!promoCode.trim()) return;
    toast.success(`Promo code "${promoCode}" will be applied at checkout.`);
  };

  const currentStepIndex = STEPS.findIndex(s => s.id === step);

  return (
    <div className="min-h-screen py-8">
      <div className="max-w-5xl mx-auto px-4">
        {/* Stepper */}
        {step !== 'confirmed' && (
          <div className="flex items-center justify-center mb-10">
            {STEPS.filter(s => s.id !== 'confirmed').map((s, idx) => (
              <div key={s.id} className="flex items-center">
                <div className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  STEPS.findIndex(x => x.id === s.id) <= currentStepIndex
                    ? 'bg-primary-600 text-white'
                    : 'bg-white border border-neutral-200 text-neutral-400'
                }`}>
                  {s.icon}
                  {s.label}
                </div>
                {idx < STEPS.filter(s => s.id !== 'confirmed').length - 1 && (
                  <ChevronRight className="w-4 h-4 text-neutral-300 mx-2" />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Price lock timer */}
        {step !== 'confirmed' && timeLeft > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-6 flex items-center gap-3">
            <Clock className="w-5 h-5 text-amber-600 shrink-0" />
            <p className="text-sm text-amber-700">
              <span className="font-semibold">Price locked</span> for {Math.floor(timeLeft / 60)}:{String(timeLeft % 60).padStart(2, '0')} — complete your booking to secure this price
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main form area */}
          <div className="lg:col-span-2">
            {step === 'guests' && (
              <GuestDetailsStep
                context={context}
                nights={nights}
                guestDetails={guestDetails}
                onChange={setGuestDetails}
                onSubmit={handleSubmitGuests}
              />
            )}

            {step === 'review' && (
              <ReviewStep
                context={context}
                nights={nights}
                guestDetails={guestDetails}
                promoCode={promoCode}
                onPromoChange={setPromoCode}
                onApplyPromo={handleApplyPromo}
                onBack={() => setStep('guests')}
                onConfirm={handleConfirmBooking}
                loading={createBooking.isPending}
              />
            )}

            {step === 'confirmed' && bookingId && (
              <ConfirmedStep bookingId={bookingId} context={context} router={router} />
            )}
          </div>

          {/* Booking summary sidebar */}
          {step !== 'confirmed' && (
            <div className="space-y-4">
              <div className="bg-white rounded-2xl p-5 shadow-card">
                <h3 className="font-semibold text-neutral-800 mb-4">Booking Summary</h3>
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="font-medium text-neutral-900">{context.property_name}</p>
                    <p className="text-neutral-500">{context.room_type_name}</p>
                  </div>
                  <div className="border-t border-neutral-100 pt-3 space-y-1">
                    <div className="flex justify-between text-neutral-600">
                      <span>Check-in</span>
                      <span className="font-medium">{context.checkin}</span>
                    </div>
                    <div className="flex justify-between text-neutral-600">
                      <span>Check-out</span>
                      <span className="font-medium">{context.checkout}</span>
                    </div>
                    <div className="flex justify-between text-neutral-600">
                      <span>Duration</span>
                      <span className="font-medium">{nights} night{nights !== 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex justify-between text-neutral-600">
                      <span>Guests</span>
                      <span className="font-medium">{context.adults} adult{context.adults !== 1 ? 's' : ''}{context.children ? `, ${context.children} child` : ''}</span>
                    </div>
                  </div>
                </div>
              </div>
              <PriceBreakdown
                basePrice={context.base_price}
                propertyDiscount={context.property_discount}
                platformDiscount={context.platform_discount}
                couponDiscount={context.promo_discount}
                serviceFee={context.service_fee}
                gst={context.tax}
                finalPrice={context.final_price}
                nights={nights}
              />
              <div className="bg-green-50 rounded-xl p-3 flex items-start gap-2">
                <Shield className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
                <p className="text-xs text-green-700">
                  Your payment is 100% secure. We use bank-grade encryption.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Step Components ─────────────────────────────────────────────── */

function GuestDetailsStep({ context, nights, guestDetails, onChange, onSubmit }: {
  context: BookingContext;
  nights: number;
  guestDetails: { guest_name: string; guest_email: string; guest_phone: string };
  onChange: (v: typeof guestDetails) => void;
  onSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <div className="bg-white rounded-2xl shadow-card p-6">
      <h2 className="text-xl font-bold text-neutral-900 mb-6">Guest Details</h2>
      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">Full Name *</label>
          <input
            type="text"
            required
            value={guestDetails.guest_name}
            onChange={e => onChange({ ...guestDetails, guest_name: e.target.value })}
            placeholder="As on government ID"
            className="input-field"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">Email Address *</label>
          <input
            type="email"
            required
            value={guestDetails.guest_email}
            onChange={e => onChange({ ...guestDetails, guest_email: e.target.value })}
            placeholder="Booking confirmation will be sent here"
            className="input-field"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1.5">Phone Number *</label>
          <input
            type="tel"
            required
            value={guestDetails.guest_phone}
            onChange={e => onChange({ ...guestDetails, guest_phone: e.target.value })}
            placeholder=" "
            className="input-field"
          />
        </div>

        <div className="bg-blue-50 rounded-xl p-4 text-sm text-blue-700">
          <p className="font-medium mb-1">Important Information</p>
          <ul className="list-disc list-inside space-y-1 text-blue-600">
            <li>Check-in: {context.checkin} (usually after 2:00 PM)</li>
            <li>Check-out: {context.checkout} (usually before 12:00 PM)</li>
            <li>{nights} night{nights !== 1 ? 's' : ''} stay</li>
          </ul>
        </div>

        <button type="submit" className="w-full btn-primary py-3 text-base">
          Continue to Review
          <ChevronRight className="w-5 h-5 ml-2 inline" />
        </button>
      </form>
    </div>
  );
}

function ReviewStep({ context, nights, guestDetails, promoCode, onPromoChange, onApplyPromo, onBack, onConfirm, loading }: {
  context: BookingContext;
  nights: number;
  guestDetails: { guest_name: string; guest_email: string; guest_phone: string };
  promoCode: string;
  onPromoChange: (v: string) => void;
  onApplyPromo: () => void;
  onBack: () => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  return (
    <div className="space-y-4">
      {/* Guest info review */}
      <div className="bg-white rounded-2xl shadow-card p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-neutral-900">Review Booking</h2>
          <button onClick={onBack} className="text-sm text-primary-600 hover:underline">Edit</button>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-neutral-500">Guest Name</span>
            <span className="font-medium">{guestDetails.guest_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Email</span>
            <span className="font-medium">{guestDetails.guest_email}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-500">Phone</span>
            <span className="font-medium">{guestDetails.guest_phone}</span>
          </div>
        </div>
      </div>

      {/* Promo code */}
      <div className="bg-white rounded-2xl shadow-card p-6">
        <h3 className="font-semibold text-neutral-800 mb-3">Promo Code</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={promoCode}
            onChange={e => onPromoChange(e.target.value.toUpperCase())}
            placeholder="Enter promo code"
            className="input-field flex-1"
          />
          <button
            onClick={onApplyPromo}
            disabled={!promoCode.trim()}
            className="btn-secondary px-4 disabled:opacity-50"
          >
            Apply
          </button>
        </div>
      </div>

      {/* Cancellation policy */}
      <div className="bg-white rounded-2xl shadow-card p-6">
        <h3 className="font-semibold text-neutral-800 mb-2">Cancellation Policy</h3>
        <p className="text-sm text-neutral-600">
          Free cancellation available. Cancel before check-in to receive a full refund.
          Cancellations after check-in may incur charges as per property policy.
        </p>
      </div>

      {/* Confirm CTA */}
      <div className="bg-white rounded-2xl shadow-card p-6">
        <p className="text-sm text-neutral-500 mb-4">
          By confirming, you agree to our Terms of Service and Privacy Policy.
          Your payment will be processed securely.
        </p>
        <button
          onClick={onConfirm}
          disabled={loading}
          className="w-full btn-primary py-3 text-base disabled:opacity-50"
        >
          {loading ? 'Processing...' : `Confirm & Pay ₹${parseFloat(context.final_price).toLocaleString('en-IN')}`}
        </button>
      </div>
    </div>
  );
}

function ConfirmedStep({ bookingId, context, router }: {
  bookingId: string;
  context: BookingContext;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="bg-white rounded-2xl shadow-card p-8 text-center">
      <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <CheckCircle className="w-12 h-12 text-green-500" />
      </div>
      <h2 className="text-2xl font-bold text-neutral-900 mb-2">Booking Confirmed!</h2>
      <p className="text-neutral-500 mb-1">
        Your booking ID: <span className="font-mono font-semibold text-neutral-800">{bookingId}</span>
      </p>
      <p className="text-sm text-neutral-400 mb-8">
        A confirmation has been sent to your email.
      </p>

      <div className="bg-neutral-50 rounded-xl p-4 text-sm text-left mb-8 space-y-2">
        <div className="flex justify-between">
          <span className="text-neutral-500">Property</span>
          <span className="font-medium">{context.property_name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-500">Room</span>
          <span className="font-medium">{context.room_type_name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-500">Check-in</span>
          <span className="font-medium">{context.checkin}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-500">Check-out</span>
          <span className="font-medium">{context.checkout}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-neutral-500">Amount Paid</span>
          <span className="font-bold text-primary-600">₹{parseFloat(context.final_price).toLocaleString('en-IN')}</span>
        </div>
      </div>

      <div className="flex gap-3 justify-center">
        <button onClick={() => router.push('/account')} className="btn-secondary">
          View My Bookings
        </button>
        <button onClick={() => router.push('/hotels')} className="btn-primary">
          Book Another Hotel
        </button>
      </div>
    </div>
  );
}
