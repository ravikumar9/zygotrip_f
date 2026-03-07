# ZygoTrip → Production OTA: Architecture Audit & Implementation Plan

> Generated: March 6, 2026  
> Scope: Full codebase audit + production transformation roadmap  
> Stack: Django 4.x + DRF + Next.js 14.2.5 + React + TypeScript + Tailwind + PostgreSQL + Redis + Celery

---

## TABLE OF CONTENTS

1. [Current State Assessment](#current-state-assessment)
2. [Gap Analysis: 21 Critical Items](#gap-analysis-21-critical-items)
3. [Implementation Plan (6 Phases)](#implementation-plan)
4. [API Integration Matrix](#api-integration-matrix)
5. [UI Component Architecture](#ui-component-architecture)
6. [Mobile-Ready API Design](#mobile-ready-api-design)
7. [Priority Execution Order](#priority-execution-order)
8. [Appendix A: Complete Backend Audit](#appendix-a-complete-backend-audit)
9. [Appendix B: Complete Frontend Audit](#appendix-b-complete-frontend-audit)

---

## CURRENT STATE ASSESSMENT

### What Works (End-to-End Connected)

| Flow Step | Backend | Frontend | Status |
|---|---|---|---|
| Hotel Search | `GET /api/v1/properties/` + `/search/` + `/autosuggest/` | `useHotels()` → `HotelListingPage` | **Working** |
| Hotel Detail | `GET /api/v1/properties/:slug/` | `useQuery` → `PropertyDetailPage` | **Working** |
| Room Selection | Nested in `PropertyDetailSerializer` → `RoomTypeSerializer` with live inventory | `RoomSelector` → Goibibo-style 3-col table | **Working** |
| Booking Context | `POST /api/v1/booking/context/` (15-min price-lock) | `bookingsService.createContext()` | **Working** |
| Booking Create | `POST /api/v1/booking/` → atomic inventory lock → HOLD status | `bookingsService.confirmBooking()` | **Working** |
| Booking Detail | `GET /api/v1/booking/:uuid/` | Confirmation page fetches + displays | **Working** |
| My Bookings | `GET /api/v1/booking/my/` | Account page + `useMyBookings()` | **Working** |
| Cancel Booking | `POST /api/v1/booking/:uuid/cancel/` → `RefundCalculator` | Cancel button on account page | **Working** |
| Promo Apply | `POST /api/v1/promo/apply/` → `calculate_promo_discount()` | Promo input on booking page | **Working** |
| Wallet | `GET /wallet/`, `POST /wallet/topup/`, transactions | Wallet page with balance + history | **Working** |
| Auth (email/pass) | JWT (SimpleJWT) register/login/refresh/logout | `AuthContext` + `RegisterForm` + login page | **Working** |
| Hold Expiry | Celery beat → `release_expired_holds()` every 2 min | Timer display on booking page | **Working** |

---

## GAP ANALYSIS: 21 CRITICAL ITEMS

### P0 — Blocking Production Launch

| # | Gap | Backend | Frontend | Impact |
|---|---|---|---|---|
| **1** | **Payment Gateway Integration** | 3 gateway classes are stubs (`raise NotImplementedError`). `process_payment()` returns hardcoded success. | Payment page uses `setTimeout` simulation. No SDK loaded. | **Cannot collect money** |
| **2** | **Payment API Endpoint (REST)** | No `POST /api/v1/payment/initiate/` or `/verify/` REST endpoint. Only legacy Django template views exist in `payment_views.py`. | Frontend has no service function to initiate real payment. | **Booking flow dead-ends at payment** |
| **3** | **Webhook Signature Verification** | All 3 webhooks have `# TODO: Verify webhook signature`. | N/A | **Security vulnerability — anyone can fake payment confirmation** |
| **4** | **Payment Config in Settings** | `PAYTM_MERCHANT_ID`, `CASHFREE_APP_ID`, `STRIPE_SECRET_KEY` not defined anywhere. | `NEXT_PUBLIC_CASHFREE_APP_ID` / `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` not defined. | **Gateways won't initialize** |
| **5** | **Mobile OTP Login** | No OTP model, no SMS send function, no verify endpoint. Only email+password exists. | No OTP UI, no phone input on login page. | **Requirement unmet — no phone-based auth** |
| **6** | **Booking → Payment State Transition** | `create_booking_view` creates booking in HOLD but never transitions to PAYMENT_PENDING. Webhook expects PAYMENT_PENDING. | Frontend navigates to `/payment/:uuid` but that page simulates. | **State machine gap** |

### P1 — Major UX Gaps

| # | Gap | Description |
|---|---|---|
| **7** | **Two duplicate booking service files** | `services/booking.ts` and `services/bookings.ts` have overlapping functions. Hooks import from one, pages from the other. |
| **8** | **No SSR for SEO** | Every page is `'use client'`. Hotel listing and detail pages need server-side rendering for Google indexing. |
| **9** | **GST Rate Mismatch** | `settings.GST_RATE = 0.12` vs `pricing/services.py` uses 5%/18% slab vs `financial_services.py` uses flat 18%. Three competing calculations. |
| **10** | **No Email Notifications** | No booking confirmation email, no payment receipt, no cancellation email. No email service configured. |
| **11** | **No Review/Rating Submission** | `RatingAggregate` model exists but no `Review` model. `review_service.py` has TODO comments. |
| **12** | **Legacy Code Pollution** | 4 duplicate search bars, 2 duplicate galleries, legacy Navbar, legacy QueryProvider, local `formatPrice` copies. |

### P2 — Feature Completeness

| # | Gap | Description |
|---|---|---|
| **13** | **No Bus/Cab/Package React Frontend** | All three show "Coming soon" placeholders. Django template views exist but aren't wired to React. |
| **14** | **No Vendor Dashboard in React** | Property owner, bus operator, cab owner dashboards only exist as Django templates. |
| **15** | **Refund Flow UI** | Backend has `RefundCalculator` + cancellation policies. No refund tracking UI in frontend. |
| **16** | **No Social Auth** | No Google/Facebook login. No `allauth` or social provider. |
| **17** | **Footer Links Dead** | About, Careers, Blog, Press, Help Centre all point to `#`. |
| **18** | **Dual Booking Flow Pages** | `/booking?context_id=` (old) and `/booking/[context_uuid]` (new) both exist. The old one is never navigated to from the detail page. |
| **19** | **No Booking Modification** | No reschedule or date-change flow. |
| **20** | **Google Maps Key Hardcoded** | Hardcoded `'xxx'` in `apps/hotels/maps.py`. PropertyMap uses OpenStreetMap iframe (works but limited). |
| **21** | **CSP `unsafe-inline`** | Content Security Policy allows inline scripts. Has `# TODO prod-csp-hardening`. |

---

## IMPLEMENTATION PLAN

### Phase 1: Payment Gateway Integration (P0 — Week 1-2)

#### Backend Changes Required

**1.1 — Create REST Payment API** (`apps/payments/api/v1/views.py` — new file)

```
POST /api/v1/payment/initiate/
  Input: { booking_uuid, gateway: 'wallet' | 'cashfree' | 'stripe' | 'paytm_upi' }
  Logic:
    1. Validate booking in HOLD state
    2. Transition to PAYMENT_PENDING
    3. Route to PaymentRouter.get_gateway(gateway)
    4. For wallet: instant debit → CONFIRMED
    5. For Cashfree: call Cashfree Create Order API → return cf_order_id + payment_session_id
    6. For Stripe: call stripe.checkout.Session.create() → return session_url
    7. For Paytm: call initiate txn API → return txn_token + mid + order_id
  Response: { payment_url?, transaction_id, gateway, client_data? }

GET /api/v1/payment/status/:transaction_id/
  Returns current payment transaction status

GET /api/v1/payment/gateways/:booking_uuid/
  Returns available gateways for this booking amount + user's wallet balance
```

**1.2 — Implement Cashfree Gateway** (`apps/payments/gateways.py` — CashfreeGateway class)

```
initiate_payment():
  1. POST https://api.cashfree.com/pg/orders (production) or sandbox URL
  2. Send: order_id, order_amount, currency=INR, customer_details, return_url, notify_url
  3. Return: { payment_session_id, cf_order_id, payment_url }

verify_payment():
  1. GET https://api.cashfree.com/pg/orders/:order_id
  2. Check order_status == 'PAID'

Webhook signature:
  1. cashfree_sdk.Cashfree.verify_payment_signature(headers, body, client_secret)
```

**1.3 — Implement Stripe Gateway** (`apps/payments/gateways.py` — StripeGateway class)

```
initiate_payment():
  1. stripe.checkout.Session.create(
       line_items=[{price_data: {currency: 'inr', unit_amount: amount*100}, quantity: 1}],
       mode='payment',
       success_url, cancel_url,
       metadata={transaction_id, booking_uuid}
     )
  2. Return: { session_url, session_id }

Webhook signature:
  1. stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
```

**1.4 — Implement Paytm UPI Gateway** (`apps/payments/gateways.py` — PaytmUPIGateway class)

```
initiate_payment():
  1. POST https://securegw.paytm.in/theia/api/v1/initiateTransaction
  2. Send: mid, orderId, txnAmount, callbackUrl (signed with merchant key)
  3. Return: { txn_token, mid, order_id }

Webhook/callback:
  1. Verify checksum using PaytmChecksum.verifySignature()
```

**1.5 — Add Settings Config** (`zygotrip_project/settings.py`)

```python
# Payment Gateway Configuration
CASHFREE_APP_ID = env('CASHFREE_APP_ID', default='')
CASHFREE_SECRET_KEY = env('CASHFREE_SECRET_KEY', default='')
CASHFREE_API_VERSION = '2023-08-01'
CASHFREE_ENV = env('CASHFREE_ENV', default='sandbox')  # sandbox | production

STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

PAYTM_MERCHANT_ID = env('PAYTM_MERCHANT_ID', default='')
PAYTM_MERCHANT_KEY = env('PAYTM_MERCHANT_KEY', default='')
PAYTM_ENV = env('PAYTM_ENV', default='staging')  # staging | production

PAYMENT_SUCCESS_URL = env('PAYMENT_SUCCESS_URL', default='http://localhost:3000/confirmation/')
PAYMENT_CANCEL_URL = env('PAYMENT_CANCEL_URL', default='http://localhost:3000/payment-failed/')
```

**1.6 — Fix Booking State Transition** (`apps/booking/api/v1/views.py`)

After `create_booking()` returns HOLD status and before response — if `payment_method == 'wallet'`:
1. Call `WalletGateway.initiate_payment()` → if success, transition HOLD → CONFIRMED
2. Otherwise return booking in HOLD state for frontend to initiate gateway payment

#### Frontend Changes Required

**1.7 — Create Payment Service** (`frontend/services/payment.ts` — new file)

```typescript
// Functions needed:
getAvailableGateways(bookingUuid: string): Promise<Gateway[]>
initiatePayment(bookingUuid: string, gateway: string): Promise<PaymentInitiation>
checkPaymentStatus(transactionId: string): Promise<PaymentStatus>
```

**1.8 — Rewrite Payment Page** (`frontend/app/payment/[booking_uuid]/page.tsx`)

Replace `setTimeout` simulation with:
1. Call `getAvailableGateways()` on load → show wallet balance + gateway options
2. Wallet selected → call `initiatePayment(uuid, 'wallet')` → redirect to confirmation
3. Cashfree selected → load Cashfree JS SDK (`cashfree-pg`) → open drop-in checkout
4. Stripe selected → redirect to `stripe.checkout.Session.url` returned by backend
5. Paytm selected → redirect to Paytm hosted page with txn_token

**1.9 — Add Frontend Environment** (`frontend/.env.local`)

```
NEXT_PUBLIC_CASHFREE_APP_ID=...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=...
NEXT_PUBLIC_PAYTM_MID=...
```

---

### Phase 2: Mobile OTP Authentication (P0 — Week 2)

#### Backend Changes

**2.1 — Create OTP Model** (`apps/accounts/models.py`)

```python
class OTPRequest(TimeStampedModel):
    phone = CharField(max_length=15, db_index=True)
    otp_hash = CharField(max_length=128)  # bcrypt hash, never store plain OTP
    purpose = CharField(choices=['login', 'register', 'verify'])
    attempts = IntegerField(default=0)
    expires_at = DateTimeField()
    is_used = BooleanField(default=False)
    
    class Meta:
        indexes = [Index(fields=['phone', 'purpose', '-created_at'])]
```

**2.2 — Create OTP Endpoints** (`apps/accounts/api/v1/urls.py`)

```
POST /api/v1/auth/otp/send/
  Input: { phone: '+91XXXXXXXXXX', purpose: 'login' | 'register' }
  Logic: Rate-limit 5/hr per phone, generate 6-digit OTP, hash+store, send via SMS provider
  
POST /api/v1/auth/otp/verify/
  Input: { phone, otp, purpose }
  Logic: Verify hash, check expiry (5 min), check attempts (3 max)
  If login: find user by phone → return JWT tokens
  If register: return verified_phone_token (short-lived)
  
POST /api/v1/auth/register-with-otp/
  Input: { verified_phone_token, full_name, email?, role }
  Logic: Create user with verified phone, skip email requirement
```

**2.3 — SMS Provider Integration** (`apps/accounts/sms_service.py` — new file)

Support two providers (India-focused):
- **MSG91** (primary): `POST https://api.msg91.com/api/v5/flow/` with template
- **Twilio** (fallback): `client.messages.create()` with verify service

**2.4 — Settings**

```python
SMS_PROVIDER = env('SMS_PROVIDER', default='msg91')  # msg91 | twilio
MSG91_AUTH_KEY = env('MSG91_AUTH_KEY', default='')
MSG91_TEMPLATE_ID = env('MSG91_TEMPLATE_ID', default='')
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_VERIFY_SID = env('TWILIO_VERIFY_SID', default='')
OTP_EXPIRY_SECONDS = 300
OTP_MAX_ATTEMPTS = 3
OTP_RATE_LIMIT_PER_HOUR = 5
```

#### Frontend Changes

**2.5 — Create OTP Login Component** (`frontend/components/auth/OTPLogin.tsx` — new file)

States: `phone_input` → `otp_sent` → `verifying` → `authenticated`
- Phone input with +91 prefix, 10-digit validation
- Auto-submit on 6-digit entry
- Resend timer (30s cooldown)
- Falls back to email/password link

**2.6 — Update Login Page** (`frontend/app/account/login/page.tsx`)

Add tab toggle: "Login with OTP" | "Login with Email" (OTP as default for Indian OTA)

---

### Phase 3: Code Cleanup & Consolidation (P1 — Week 2-3)

| Task | Action | Files |
|---|---|---|
| **3.1** Merge booking services | Delete `services/booking.ts`, keep `services/bookings.ts`. Update all hook imports. | `hooks/useBooking.ts` |
| **3.2** Delete duplicate gallery | Delete `HotelGallery.tsx`. Ensure only `PropertyGallery` is imported. | Check all imports |
| **3.3** Delete legacy search bars | Delete `HeroSearch.tsx`, `OtaHeroSearch.tsx`. Keep `GlobalSearchBar.tsx` only. | |
| **3.4** Delete legacy layout components | Remove `Navbar.tsx`, `QueryProvider.tsx`. | |
| **3.5** Fix `PropertyCard.tsx` formatPrice | Import from `@/lib/formatPrice` instead of local copy. | `PropertyCard.tsx` |
| **3.6** Fix double Toaster | Remove `<Toaster>` from either `layout.tsx` or `providers.tsx`. | |
| **3.7** Delete old booking page | Remove `/booking` (query-param based). Only keep `/booking/[context_uuid]`. | `app/booking/page.tsx` |
| **3.8** Unify GST calculation | Single source of truth: use slab system (5% ≤₹7500/night, 18% >₹7500) everywhere. Update `settings.py`, `financial_services.py`, `pricing/services.py`. | 3 backend files |

---

### Phase 4: SEO & Server-Side Rendering (P1 — Week 3)

**4.1 — Convert Hotel Listing to Server Component**

`app/hotels/page.tsx` should:
1. Accept `searchParams` as server component prop
2. Fetch `listHotels(params)` server-side using internal API URL
3. Pass pre-fetched data to `HotelListingPage` client component via `initialData` prop
4. Add `generateMetadata()` for dynamic SEO titles: "Hotels in {city} - ZygoTrip"

**4.2 — Convert Hotel Detail to Server Component**

`app/hotels/[slug]/page.tsx` should:
1. Fetch property data server-side
2. Generate structured data (JSON-LD Hotel schema)
3. `generateMetadata()` with property name, city, rating, price range
4. Pass to client component for interactive features

---

### Phase 5: Email & Notification System (P1 — Week 3)

**5.1 — Create Email Service** (`apps/core/email_service.py` — new file)

```python
# Transactional email templates:
send_booking_confirmation(booking)  # On CONFIRMED status
send_payment_receipt(booking, payment)
send_cancellation_notice(booking, refund_amount)
send_welcome_email(user)
send_otp_email(user, otp)  # Fallback for OTP via email
```

**5.2 — Settings**

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
# Or use SES/SendGrid for production
```

**5.3 — Celery Tasks** — Send emails asynchronously via Celery task to avoid blocking API responses.

---

### Phase 6: Review & Rating System (P2 — Week 4)

**6.1 — Create Review Model** (`apps/hotels/models.py`)

```python
class Review(TimeStampedModel):
    property = ForeignKey(Property)
    booking = OneToOneField(Booking)  # One review per booking
    user = ForeignKey(User)
    overall_rating = DecimalField(max_digits=2, decimal_places=1)  # 1.0-5.0
    cleanliness = IntegerField(validators=[1-5])
    service = IntegerField(validators=[1-5])
    location = IntegerField(validators=[1-5])
    value_for_money = IntegerField(validators=[1-5])
    title = CharField(max_length=200)
    body = TextField()
    status = CharField(choices=['pending', 'approved', 'rejected'])
```

**6.2 — Endpoints**

```
POST /api/v1/reviews/               # Submit review (only after checkout)
GET  /api/v1/properties/:slug/reviews/  # Paginated reviews for a property
```

**6.3 — Frontend** — Review submission form on confirmation page (post-checkout), reviews tab in property detail.

---

## API INTEGRATION MATRIX

### Currently Connected (Working)

| Frontend Function | Backend Endpoint | Status |
|---|---|---|
| `listHotels()` | `GET /api/v1/properties/` | **Connected** |
| `getHotel()` | `GET /api/v1/properties/:slug/` | **Connected** |
| `fetchAutosuggest()` | `GET /api/v1/autosuggest/` | **Connected** |
| `searchHotels()` | `GET /api/v1/search/` | **Connected** |
| `checkAvailability()` | `GET /api/v1/properties/:slug/availability/` | **Connected** |
| `getPricingQuote()` | `POST /api/v1/pricing/quote/` | **Connected** |
| `fetchPricingIntelligence()` | `GET /api/v1/pricing/intelligence/:uuid/` | **Connected** |
| `bookingsService.createContext()` | `POST /api/v1/booking/context/` | **Connected** |
| `bookingsService.getContext()` | `GET /api/v1/booking/context/:uuid/` | **Connected** |
| `bookingsService.confirmBooking()` | `POST /api/v1/booking/` | **Connected** |
| `bookingsService.applyPromo()` | `POST /api/v1/promo/apply/` | **Connected** |
| `bookingsService.getBooking()` | `GET /api/v1/booking/:uuid/` | **Connected** |
| `bookingsService.getMyBookings()` | `GET /api/v1/booking/my/` | **Connected** |
| `bookingsService.cancelBooking()` | `POST /api/v1/booking/:uuid/cancel/` | **Connected** |
| `login()` / `register()` / `logout()` | `/api/v1/auth/*` | **Connected** |
| `getWalletBalance()` / `topUpWallet()` | `/api/v1/wallet/*` | **Connected** |

### Missing (Need to Build)

| Frontend Function | Backend Endpoint | Phase |
|---|---|---|
| `initiatePayment()` | `POST /api/v1/payment/initiate/` | Phase 1 |
| `getPaymentGateways()` | `GET /api/v1/payment/gateways/:uuid/` | Phase 1 |
| `checkPaymentStatus()` | `GET /api/v1/payment/status/:txn_id/` | Phase 1 |
| `sendOTP()` | `POST /api/v1/auth/otp/send/` | Phase 2 |
| `verifyOTP()` | `POST /api/v1/auth/otp/verify/` | Phase 2 |
| `submitReview()` | `POST /api/v1/reviews/` | Phase 6 |
| `getPropertyReviews()` | `GET /api/v1/properties/:slug/reviews/` | Phase 6 |

---

## UI COMPONENT ARCHITECTURE

```
app/layout.tsx
├── Header (auth-aware nav)
├── Toaster (react-hot-toast)
└── {children}

/ (Home)
├── HeroSection (static + GlobalSearchBar)
├── DestinationsSection (API: aggregations)
└── Footer

/hotels
├── SearchHeroBand + GlobalSearchBar  
├── FilterSidebar (URL-driven)
│   ├── PriceFilter
│   ├── RatingFilter
│   └── AmenityFilter
└── HotelCard[] (API: properties)

/hotels/[slug]
├── StickyContextBar
├── PropertyGallery (lightbox)
├── CouponStrip
├── HeaderCard (name, rating, trust badges, View Map, View Reviews)
├── Tabs: Room Options | Amenities | Location | Policies
│   └── RoomSelector (3-col Goibibo table)
│       └── Per Room: Image+Specs | MealPlan rows with benefits | Price+Discount+SELECT
└── BookingPanel (sidebar)
    ├── Date picker, Guest/Room counter
    ├── Promo code input
    ├── Price estimate
    └── Book Now CTA

/booking/[context_uuid]
├── BookingSummary
├── GuestDetailsForm
├── PriceBreakdown (with promo)
├── PaymentMethodSelector  ← NEEDS REAL GATEWAY OPTIONS
└── HoldExpiryTimer

/payment/[booking_uuid]  ← NEEDS COMPLETE REWRITE
├── AmountDue card
├── GatewaySelector (wallet | UPI | card)
├── CashfreeDropIn / StripeRedirect / PaytmRedirect
└── PaymentStatusPolling

/confirmation/[booking_uuid]
├── SuccessAnimation
├── BookingDetail card
├── PriceBreakdown
├── ReviewPrompt (post-checkout only)  ← NEW
└── ActionButtons (download PDF, share)

/account
├── ProfileCard (edit name/phone)
├── BookingsList (paginated)
└── LogoutButton

/wallet
├── BalanceCard
├── TopUpForm
└── TransactionHistory (infinite scroll)
```

---

## MOBILE-READY API DESIGN

The current API is already mobile-ready with these characteristics:

| Aspect | Current State | Recommendation |
|---|---|---|
| **Auth** | JWT with refresh tokens | Add OTP flow for mobile-first login |
| **Pagination** | `PageNumberPagination(page_size=20)` | Add `CursorPagination` option for infinite scroll |
| **Throttling** | 100/min anon, 300/min user | Sufficient for mobile. Add per-device fingerprint |
| **Response format** | `{ success, data }` envelope | Already consistent. Add `error.field_errors` for form validation |
| **Image URLs** | CDN-first with fallback | Add `?w=` `&h=` params for responsive image serving |
| **Offline support** | None | Add `ETag` + `If-None-Match` headers for conditional GET |
| **Push notifications** | None | Add FCM token registration endpoint for booking status updates |
| **Deep linking** | URL-based routing | Already supported via slug-based URLs |

### New Endpoints Needed for Mobile

```
POST /api/v1/auth/otp/send/          # Phone-based login
POST /api/v1/auth/otp/verify/         # OTP verification
POST /api/v1/devices/register/         # FCM push token
POST /api/v1/payment/initiate/         # Gateway payment
GET  /api/v1/payment/status/:txn_id/   # Poll payment result
GET  /api/v1/payment/gateways/:uuid/   # Available gateways
POST /api/v1/reviews/                  # Submit review
GET  /api/v1/properties/:slug/reviews/ # Property reviews
```

---

## PRIORITY EXECUTION ORDER

| Week | Phase | Deliverable |
|---|---|---|
| **Week 1** | Payment REST API + Cashfree integration | Real UPI/card payments working end-to-end |
| **Week 1** | Stripe integration | International card support |
| **Week 2** | Paytm UPI + Webhook hardening | All 3 gateways live with signature verification |
| **Week 2** | OTP authentication | Phone-based login for mobile users |
| **Week 2-3** | Code cleanup (Phase 3) | Remove all duplicates, unify services |
| **Week 3** | SSR for SEO (Phase 4) | Hotel pages indexed by Google |
| **Week 3** | Email notifications (Phase 5) | Booking confirmations, receipts |
| **Week 4** | Reviews system (Phase 6) | User reviews on properties |

---

## APPENDIX A: COMPLETE BACKEND AUDIT

### A.1 — All REST API v1 Endpoints

| Method | Path | View | Auth |
|--------|------|------|------|
| **Hotels** | | | |
| GET | `/api/v1/properties/` | `property_list_api` | AllowAny |
| GET | `/api/v1/search/` | `property_search_api` | AllowAny |
| GET | `/api/v1/properties/<slug>/` | `property_detail_api` | AllowAny |
| GET | `/api/v1/properties/<slug>/availability/` | `property_availability_api` | AllowAny |
| POST | `/api/v1/pricing/quote/` | `pricing_quote_api` | AllowAny |
| GET | `/api/v1/pricing/intelligence/<uuid>/` | `pricing_intelligence_api` | AllowAny |
| GET | `/api/v1/autosuggest/` | `autosuggest_api` | AllowAny |
| GET | `/api/v1/hotels/aggregations/` | `aggregations_api` | AllowAny |
| **Auth** | | | |
| POST | `/api/v1/auth/register/` | `register_view` | AllowAny |
| POST | `/api/v1/auth/login/` | `login_view` | AllowAny |
| POST | `/api/v1/auth/token/refresh/` | `TokenRefreshView` | AllowAny |
| POST | `/api/v1/auth/logout/` | `logout_view` | IsAuthenticated |
| GET/PUT/PATCH | `/api/v1/users/me/` | `me_view` | IsAuthenticated |
| **Booking** | | | |
| POST | `/api/v1/booking/context/` | `create_booking_context` | AllowAny |
| GET | `/api/v1/booking/context/<uuid>/` | `get_booking_context` | AllowAny |
| GET | `/api/v1/booking/context/<int>/` | `get_booking_context_by_id` (deprecated) | AllowAny |
| POST | `/api/v1/booking/` | `create_booking_view` | IsAuthenticated |
| GET | `/api/v1/booking/my/` | `my_bookings` | IsAuthenticated |
| GET | `/api/v1/booking/<uuid>/` | `booking_detail` | IsAuthenticated |
| POST | `/api/v1/booking/<uuid>/cancel/` | `cancel_booking` | IsAuthenticated |
| **Wallet** | | | |
| GET | `/api/v1/wallet/` | `wallet_balance` | IsAuthenticated |
| GET | `/api/v1/wallet/transactions/` | `wallet_transactions` | IsAuthenticated |
| POST | `/api/v1/wallet/topup/` | `wallet_topup` | IsAuthenticated |
| GET | `/api/v1/wallet/owner/` | `owner_wallet_balance` | IsAuthenticated (property_owner) |
| GET | `/api/v1/wallet/owner/transactions/` | `owner_wallet_transactions` | IsAuthenticated (property_owner) |
| **Promo** | | | |
| POST | `/api/v1/promo/apply/` | `apply_promo` | IsAuthenticated |

### A.2 — Legacy API Endpoints (non-versioned)

| Method | Path | View |
|--------|------|------|
| GET | `/api/hotels/suggest/` | `suggest_hotels` |
| GET | `/api/search/` | `search_index_api` |
| GET | `/api/cities/` | `cities_autocomplete` |
| GET | `/api/locations/` | `location_autocomplete` |
| GET | `/api/search-autocomplete` | `SearchAutocompleteAPI` |
| GET | `/api/trending-destinations` | `TrendingDestinationsAPI` |
| GET | `/api/categories` | `CategoriesAPI` |
| GET | `/api/offers` | `OffersAPI` |
| GET | `/health/` | `health_check` |

### A.3 — Complete Model List

#### `apps.accounts`
| Model | Key Fields |
|-------|-----------|
| **User** | `email` (unique), `full_name`, `phone`, `role` (traveler/property_owner/cab_owner/bus_operator/package_provider/admin), `is_verified_vendor`, `is_staff`, `roles` M2M |
| **Role** | `code` (unique), `name`, `description`, permissions M2M |
| **Permission** | `code` (unique), `name`, `description` |

#### `apps.hotels`
| Model | Key Fields |
|-------|-----------|
| **Property** | `uuid`, `owner` FK, `name`, `slug`, `property_type`, `city` FK, `locality` FK, `area`, `address`, `description`, `rating`, `review_count`, `star_category`, `latitude`, `longitude`, `has_free_cancellation`, `pay_at_hotel`, `status`, `commission_percentage`, `is_trending` |
| **PropertyImage** | `property` FK, `image`, `image_url`, `caption`, `is_featured`, `display_order` |
| **RatingAggregate** | `property` FK, `cleanliness`, `service`, `location`, `amenities`, `value_for_money`, `total_reviews` |
| **PropertyPolicy** | `property` FK, `title`, `description` |
| **PropertyAmenity** | `property` FK, `name`, `icon` |
| **RecentSearch** | `user` FK, `session_key`, `search_text`, dates, guests |

#### `apps.rooms`
| Model | Key Fields |
|-------|-----------|
| **RoomType** | `uuid`, `property` FK, `name`, `description`, `capacity`, `max_occupancy`, `room_size`, `available_count`, `price_per_night`, `base_price`, `bed_type`, `meal_plan` |
| **RoomInventory** | `room_type` FK, `date` (unique_together), `available_rooms` (≥0 constraint), `price`, `is_closed` |
| **RoomImage** | `room_type` FK, `image`, `image_url`, `alt_text`, `is_primary`, `display_order` |
| **RoomMealPlan** | `room_type` FK, `code`, `name`, `price_modifier`, `description`, `is_available` |
| **RoomAmenity** | `room_type` FK, `name`, `icon` |

#### `apps.booking`
| Model | Key Fields |
|-------|-----------|
| **Booking** | `uuid`, `public_booking_id`, `idempotency_key`, `user` FK, `property` FK, status (15 states), financial fields, guest info, `hold_expires_at` |
| **BookingRoom** | `booking` FK, `room_type` FK, `quantity` |
| **BookingGuest** | `booking` FK, `full_name`, `age`, `email` |
| **BookingPriceBreakdown** | `booking` 1-to-1, `base_amount`, `meal_amount`, `service_fee`, `gst`, `promo_discount`, `total_amount` |
| **BookingStatusHistory** | `booking` FK, `status`, `note` |
| **BookingContext** | `uuid`, property/room/dates/guests, price snapshot fields, `promo_code`, `context_status`, `expires_at` |
| **CancellationPolicy** | `property` 1-to-1, `policy_type`, refund windows, `display_note` |
| **Settlement** | `hotel` FK, period, amounts, `status`, `payment_reference_id` |

#### `apps.payments`
| Model | Key Fields |
|-------|-----------|
| **Payment** | `booking` FK, `user` FK, `amount`, `payment_method`, `transaction_id` (unique), `status` |

#### `apps.wallet`
| Model | Key Fields |
|-------|-----------|
| **Wallet** | `user` 1-to-1, `balance`, `locked_balance`, `currency`, `is_active` |
| **WalletTransaction** | `uid`, `wallet` FK, `txn_type`, `amount`, `balance_after`, `reference`, `note` |
| **OwnerWallet** | `owner` 1-to-1, `balance`, `pending_balance`, `total_earned`, bank details, `is_verified` |
| **OwnerWalletTransaction** | `uid`, `owner_wallet` FK, `txn_type`, `amount`, `balance_after`, `booking_reference` |

#### `apps.pricing`
| Model | Key Fields |
|-------|-----------|
| **CompetitorPrice** | `property` FK, `competitor_name`, `source`, `price_per_night`, `date` |

#### `apps.inventory`
| Model | Key Fields |
|-------|-----------|
| **SupplierPropertyMap** | `property` FK, `supplier_name`, `external_id`, `confidence_score` |
| **PropertyInventory** | `property` 1-to-1, `total_rooms`, `available_rooms`, `version` (optimistic locking) |

#### `apps.offers`
| Model | Key Fields |
|-------|-----------|
| **Offer** | `title`, `offer_type`, `coupon_code` (unique), discount fields, dates, `is_active` |
| **PropertyOffer** | `offer` FK + `property` FK |

#### `apps.promos`
| Model | Key Fields |
|-------|-----------|
| **Promo** | `code` (unique), `discount_type`, `value`, `max_discount`, `max_uses`, dates, `is_active` |
| **PromoUsage** | `promo` FK, `booking` FK, `user` FK |
| **CashbackCampaign** | `name`, `cashback_type`, limits, dates, `applicable_properties` M2M |
| **CashbackCredit** | `campaign` FK, `booking` FK, `user` FK, `amount`, `expires_at` |

#### `apps.buses`
| Model | Key Fields |
|-------|-----------|
| **Bus** | `uuid`, `operator` FK, `registration_number`, routes, pricing, `available_seats` |
| **BusSeat** | `bus` FK, `seat_number`, `row`, `column`, `state` |
| **BusBooking** | `uuid`, `user` FK, `bus` FK, `status`, `total_amount` |

#### `apps.cabs`
| Model | Key Fields |
|-------|-----------|
| **Cab** | `uuid`, `owner` FK, `name`, `city`, `seats`, pricing, `is_active` |
| **CabBooking** | `uuid`, `cab` FK, `user` FK, `status`, `total_price` |

#### `apps.packages`
| Model | Key Fields |
|-------|-----------|
| **Package** | `provider` FK, `name`, `destination`, `duration_days`, `base_price`, inclusions |
| **PackageItinerary** | `package` FK, `day_number`, `title`, `description` |

### A.4 — Complete Serializer List

| Serializer | Model/Purpose | App |
|-----------|---------------|-----|
| `PropertyImageSerializer` | → `PropertyImage` | hotels |
| `PropertyAmenitySerializer` | → `PropertyAmenity` | hotels |
| `RoomImageSerializer` | → `RoomImage` (CDN-first URL) | hotels |
| `RoomAmenitySerializer` | → `RoomAmenity` | hotels |
| `RoomMealPlanSerializer` | → `RoomMealPlan` | hotels |
| `RoomTypeSerializer` | → `RoomType` + nested images/amenities/meal_plans + live inventory | hotels |
| `PropertyPolicySerializer` | → `PropertyPolicy` | hotels |
| `PropertyCardSerializer` | → `Property` (compact card for listings) | hotels |
| `PropertyDetailSerializer` | → `Property` (full detail with nested rooms, images, amenities, policies) | hotels |
| `UserSerializer` | → `User` (public profile) | accounts |
| `RegisterSerializer` | email+password+name+role → creates User | accounts |
| `LoginSerializer` | email+password → authenticates | accounts |
| `UpdateProfileSerializer` | → `User` (full_name, phone only) | accounts |
| `BookingContextCreateSerializer` | Input for context creation | booking |
| `BookingContextSerializer` | → `BookingContext` (full price snapshot) | booking |
| `BookingCreateSerializer` | Input for booking creation | booking |
| `BookingDetailSerializer` | → `Booking` (full detail) | booking |
| `BookingListSerializer` | → `Booking` (compact for lists) | booking |
| `WalletSerializer` | → `Wallet` | wallet |
| `WalletTransactionSerializer` | → `WalletTransaction` | wallet |
| `TopUpSerializer` | Input for wallet top-up | wallet |

### A.5 — Business Logic Services

| Service | Location | Purpose |
|---------|----------|---------|
| `create_booking()` | `booking/services.py` | Atomic booking with inventory locking, idempotency |
| `transition_booking_status()` | `booking/services.py` | State machine enforcement |
| `BookingStateMachine` | `booking/state_machine.py` | Hardened status transitions with audit trail |
| `set_booking_financials()` | `booking/financial_services.py` | Commission (15%), GST (18%), gateway fee (2%), net payable |
| `RefundCalculator` | `booking/cancellation_models.py` | Tiered refund: free/partial/non-refundable windows |
| `release_expired_holds()` | `booking/hold_expiry_service.py` | Celery job to release expired inventory |
| `handle_payment_webhook()` | `payments/services.py` | Idempotent webhook processing |
| `PaymentRouter` | `payments/gateways.py` | Gateway routing (wallet→paytm→cashfree→stripe) |
| `calculate_price_breakdown()` | `pricing/services.py` | GST slab (5%/18%), service fee (5% capped at ₹500) |
| `PriceEngine.calculate()` | `pricing/price_engine.py` | Full pricing engine |
| `calculate_promo_discount()` | `promos/services.py` | Promo application (percent/flat) |
| `get_or_create_wallet()` | `wallet/services.py` | Wallet CRUD + debit/credit/refund |
| `reserve_inventory()` / `release_inventory()` | `inventory/services.py` | Atomic inventory operations with select_for_update |
| Distributed locks | `booking/distributed_locks.py` | Redis SET NX PX lock with thread-local fallback |

### A.6 — Payment Gateway Status

| Gateway | Class | Status |
|---------|-------|--------|
| **ZygoTrip Wallet** | `WalletGateway` | **Fully implemented** |
| **Paytm UPI** | `PaytmUPIGateway` | **Stub** — `raise NotImplementedError` |
| **Cashfree** | `CashfreeGateway` | **Stub** — `raise NotImplementedError` |
| **Stripe** | `StripeGateway` | **Stub** — `raise NotImplementedError` |
| **PaymentRouter** | Routing logic | **Implemented** |
| **Webhook handler** | `handle_payment_webhook()` | **Implemented** (no signature verification) |
| **process_payment()** | `payments/services.py` | **Stub** — always returns success |

### A.7 — Authentication

| Mechanism | Details |
|-----------|---------|
| **JWT** | SimpleJWT. Access: 12h, Refresh: 30d. Rotation + blacklisting enabled. |
| **Session** | Django sessions for template views |
| **CORS** | `localhost:3000`, `127.0.0.1:3000` allowed |
| **OTP/SMS** | **Not implemented** |
| **Social Auth** | **Not implemented** |

### A.8 — Key Settings

| Setting | Value |
|---------|-------|
| `AUTH_USER_MODEL` | `accounts.User` |
| Database | PostgreSQL (statement_timeout=10s, CONN_MAX_AGE=60) |
| REST Framework Auth | JWT (primary) + Session (fallback) |
| Pagination | PAGE_SIZE=20 |
| Throttling | Anon: 100/min, User: 300/min |
| Cache | Redis |
| Celery | Redis broker |
| Currency | INR (₹) |
| Feature flags | Hotels, Buses, Cabs, Packages enabled; Flights, Trains disabled |

### A.9 — Booking State Machine (15 states)

```
initiated → hold → payment_pending → confirmed → checked_in → checked_out → settlement_pending → settled
                                    → refund_pending → refunded
                                    → cancelled / failed
```

---

## APPENDIX B: COMPLETE FRONTEND AUDIT

### B.1 — Page Route Tree

| Route | Component | Data Source |
|---|---|---|
| `/` | `HomePage` | Static + `DestinationsSection` API |
| `/account` | `AccountPage` | `useMyBookings()`, `updateProfile()`, `useAuth()` |
| `/account/login` | `LoginForm` | `POST /auth/login/` |
| `/account/register` | Redirect → `/account/register/customer` | — |
| `/account/register/customer` | `RegisterForm` | `POST /auth/register/` |
| `/account/register/property` | `RegisterForm` (role=property_owner) | `POST /auth/register/` |
| `/account/register/bus` | `RegisterForm` (role=bus_operator) | `POST /auth/register/` |
| `/account/register/cab` | `RegisterForm` (role=cab_operator) | `POST /auth/register/` |
| `/account/register/package` | `RegisterForm` (role=tour_operator) | `POST /auth/register/` |
| `/hotels` | `HotelListingPage` | `GET /properties/` |
| `/hotels/[slug]` | `PropertyDetailPage` | `GET /properties/:slug/`, pricing intelligence |
| `/booking` | `BookingFlow` (legacy) | `GET /booking/context/:id/` |
| `/booking/[context_uuid]` | `BookingContent` (primary) | `GET /booking/context/:uuid/`, `POST /booking/`, promo |
| `/confirmation/[booking_uuid]` | `ConfirmationContent` | `GET /booking/:uuid/` |
| `/payment/[booking_uuid]` | `PaymentContent` | `GET /booking/:uuid/` — **SIMULATED PAYMENT** |
| `/wallet` | `WalletPage` | Wallet balance, transactions, top-up |
| `/buses` | Coming soon | Static |
| `/cabs` | Coming soon | Static |
| `/packages` | Coming soon | Static |
| `/list-property` | Vendor role selector | Static |

### B.2 — Services Layer

| Service File | Functions | Backend Endpoints |
|---|---|---|
| `services/api.ts` | Authenticated axios instance | Base URL, interceptors, token refresh |
| `services/apiClient.ts` | `fetchAutosuggest()`, `fetchAggregations()` | `/autosuggest/`, `/hotels/aggregations/` |
| `services/auth.ts` | `login()`, `register()`, `logout()`, `getCurrentUser()`, `updateProfile()` | `/auth/*`, `/users/me/` |
| `services/bookings.ts` | `createContext()`, `getContext()`, `confirmBooking()`, `applyPromo()`, `getMyBookings()`, `getBooking()`, `cancelBooking()` | `/booking/*`, `/promo/apply/` |
| `services/booking.ts` | **Duplicate** — same functions as bookings.ts | `/booking/*` |
| `services/hotels.ts` | `listHotels()`, `getHotel()`, `checkAvailability()`, `getPricingQuote()`, `searchHotels()`, `fetchPricingIntelligence()` | `/properties/*`, `/search/`, `/pricing/*` |
| `services/wallet.ts` | `getWalletBalance()`, `getWalletTransactions()`, `topUpWallet()`, `getOwnerWallet()` | `/wallet/*` |

### B.3 — React Hooks

| Hook | Purpose |
|---|---|
| `useHotels(params)` | React Query → `listHotels()` |
| `useHotelSearch(query, params)` | React Query → `searchHotels()` |
| `useHotelDetail(slug)` | React Query → `getHotel()` |
| `useAvailability(...)` | React Query → `checkAvailability()` |
| `useBookingContext(contextId)` | React Query → booking context (auto-refresh 60s) |
| `useMyBookings()` | Infinite query → booking history |
| `useBookingDetail(uuid)` | React Query → single booking |
| `useCreateBookingContext()` | Mutation → `createBookingContext()` |
| `useCreateBooking()` | Mutation → `createBooking()` |
| `useCancelBooking()` | Mutation → `cancelBooking()` |
| `useWalletBalance()` | React Query → wallet balance |
| `useWalletTransactions()` | Infinite query → transaction history |
| `useTopUp()` | Mutation → wallet top-up |
| `useDebounce<T>(value, delay)` | Generic debounce |

### B.4 — Contexts

| Context | State Managed |
|---|---|
| `AuthContext` | `user`, `isAuthenticated`, `isLoading`, `login()`, `logout()`, `refreshUser()` |

### B.5 — TypeScript Types

**Auth:** `User`, `AuthTokens`, `AuthData`  
**Property:** `Property`, `PropertyDetail`, `PropertyImage`, `PropertyAmenity`, `PropertyPolicy`, `RatingBreakdown`  
**Room:** `RoomType`, `RoomImage`, `RoomAmenity`, `RoomMealPlan`, `RoomAvailability`, `RoomAvailabilityPricing`  
**Booking:** `BookingContext`, `BookingSummary`, `BookingDetail`, `BookingStatus`  
**Wallet:** `WalletBalance`, `WalletTransaction`, `OwnerWallet`  
**Search:** `HotelSearchParams`  
**Pricing:** `PricingBreakdown`, `PricingQuote`, `PricingIntelligence`, `CompetitorPrice`  
**Promo:** `PromoResult`  
**API:** `ApiSuccess<T>`, `ApiError`, `ApiResponse<T>`, `PaginatedData<T>`

### B.6 — Known Issues

| Issue | Description |
|---|---|
| **Duplicate booking services** | `booking.ts` and `bookings.ts` overlap |
| **Duplicate gallery** | `PropertyGallery.tsx` ≡ `HotelGallery.tsx` |
| **4 search bars** | GlobalSearchBar (current), SearchBar, HeroSearch, OtaHeroSearch (legacy) |
| **Legacy components** | Navbar.tsx, QueryProvider.tsx unused |
| **Local formatPrice** | PropertyCard.tsx has its own copy |
| **Double Toaster** | Both layout.tsx and providers.tsx render `<Toaster>` |
| **DestinationsSection raw fetch** | Calls `fetch()` directly, may 404 without trailing slash |
| **Payment page stub** | Uses `setTimeout` simulation |
| **No SSR** | All pages are `'use client'` — no SEO |
| **Footer dead links** | About, Careers, Blog, Press → `#` |

---

*End of document. This audit covers every model, serializer, view, service, page, component, hook, type, and config file in the ZygoTrip codebase.*
