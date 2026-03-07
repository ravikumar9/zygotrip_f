# ZygoTrip Django Backend — Complete Inventory

> Auto-generated comprehensive audit of the entire Django backend.
> Workspace: `c:\Users\ravi9\Downloads\Zygo\Copilot_code\deployment`

---

## Table of Contents

1. [Platform Configuration](#1-platform-configuration)
2. [App: accounts](#2-app-accounts)
3. [App: booking](#3-app-booking)
4. [App: hotels](#4-app-hotels)
5. [App: rooms](#5-app-rooms)
6. [App: core](#6-app-core)
7. [App: buses](#7-app-buses)
8. [App: cabs](#8-app-cabs)
9. [App: payments](#9-app-payments)
10. [App: wallet](#10-app-wallet)
11. [App: promos](#11-app-promos)
12. [App: pricing](#12-app-pricing)
13. [App: inventory](#13-app-inventory)
14. [App: offers](#14-app-offers)
15. [App: meals](#15-app-meals)
16. [App: packages](#16-app-packages)
17. [App: search](#17-app-search)
18. [App: dashboard_owner](#18-app-dashboard_owner)
19. [App: dashboard_admin](#19-app-dashboard_admin)
20. [App: dashboard_finance](#20-app-dashboard_finance)
21. [App: registration (Unlisted)](#21-app-registration-unlisted)
22. [Root URL Configuration](#22-root-url-configuration)
23. [Celery Tasks](#23-celery-tasks)
24. [Payment Gateways](#24-payment-gateways)
25. [Issues, Gaps & Recommendations](#25-issues-gaps--recommendations)

---

## 1. Platform Configuration

### Django & Python Stack

| Setting | Value |
|---|---|
| Django | 5.1.5 |
| Python | 3.x (psycopg2-binary) |
| DRF | ≥ 3.15.2 |
| Auth | Custom User model (`accounts.User`) via `AbstractBaseUser + PermissionsMixin` |
| JWT | `djangorestframework-simplejwt` with token blacklist |
| Filtering | `django-filter` |
| Celery | 5.3.4 + `django-celery-beat` + `django-celery-results` |
| Static files | WhiteNoise (`CompressedManifestStaticFilesStorage`) |
| CORS | `django-cors-headers` (allowed: `localhost:3000`, `127.0.0.1:3000`) |
| Frontend | Next.js (separate `/frontend/` directory) |

### Database

```python
ENGINE   = 'django.db.backends.postgresql'
NAME     = env('DB_NAME', 'zygotrip_db')
HOST     = env('DB_HOST', 'localhost')
PORT     = env('DB_PORT', '5432')
CONN_MAX_AGE = 60
OPTIONS  = {'options': '-c statement_timeout=10000'}
```

### Cache

```python
# Primary: Redis
BACKEND = 'django.core.cache.backends.redis.RedisCache'
LOCATION = 'redis://{REDIS_HOST}:6379/1'

# Fallback (if REDIS_HOST not set): LocMemCache
```

### Celery

```python
BROKER_URL       = 'redis://{REDIS_HOST}:6379/0'
RESULT_BACKEND   = 'django-db'
TASK_ALWAYS_EAGER = True  # In DEBUG mode
```

### INSTALLED_APPS (complete, in order)

```
django.contrib.admin
django.contrib.auth
django.contrib.contenttypes
django.contrib.sessions
django.contrib.messages
django.contrib.staticfiles
corsheaders
rest_framework
rest_framework_simplejwt
rest_framework_simplejwt.token_blacklist
django_filters
django_extensions
apps.accounts
apps.core
apps.search
apps.hotels
apps.rooms
apps.meals
apps.pricing
apps.booking
apps.payments
apps.wallet
apps.promos
apps.buses
apps.packages
apps.cabs
apps.inventory
apps.offers
apps.dashboard_owner
apps.dashboard_admin
apps.dashboard_finance
django_celery_beat
django_celery_results
```

### requirements.txt (key packages)

Django==5.1.5, djangorestframework>=3.15.2, djangorestframework-simplejwt>=5.3.1, django-cors-headers, django-filter, django-extensions, celery==5.3.4, django-celery-beat, django-celery-results, psycopg2-binary, redis, whitenoise, gunicorn, requests, Pillow, stripe, cashfree-sdk, razorpay

---

## 2. App: accounts

**Purpose:** Authentication, user management, RBAC, OTP-based phone auth.

### Models

#### `User` (extends `AbstractBaseUser + PermissionsMixin + TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| email | EmailField | `unique=True`, used as `USERNAME_FIELD` |
| full_name | CharField(150) | |
| phone | CharField(15) | blank/null |
| role | CharField(20) | choices: customer, property_owner, cab_owner, bus_owner, package_provider, admin |
| is_verified_vendor | BooleanField | default `False` |
| roles | M2M → Role | through `UserRole` |

Custom Manager: `UserManager` (creates with email normalization).

#### `Role`

| Field | Type | Notes |
|---|---|---|
| code | CharField(50) | unique |
| name | CharField(100) | |
| description | TextField | blank |
| permissions | M2M → Permission | through `RolePermission` |

#### `Permission`

| Field | Type | Notes |
|---|---|---|
| code | CharField(100) | unique |
| name | CharField(200) | |
| description | TextField | blank |

#### `UserRole`

| Field | Type | Notes |
|---|---|---|
| user | FK → User | |
| role | FK → Role | |
| | | `unique_together = (user, role)` |

#### `RolePermission`

| Field | Type | Notes |
|---|---|---|
| role | FK → Role | |
| permission | FK → Permission | |
| | | `unique_together = (role, permission)` |

#### `OTP` (in `otp_models.py`)

| Field | Type | Notes |
|---|---|---|
| phone | CharField(15) | |
| code | CharField(6) | |
| purpose | CharField(20) | choices: login, registration, verification |
| is_verified | BooleanField | default `False` |
| expires_at | DateTimeField | |
| attempts | IntegerField | default 0 |
| max_attempts | IntegerField | default 5 |

### API Endpoints (v1)

| Method | URL | View | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register/` | `register_view` | Public |
| POST | `/api/v1/auth/login/` | `login_view` | Public |
| POST | `/api/v1/auth/token/refresh/` | `TokenRefreshView` (simplejwt) | Public |
| POST | `/api/v1/auth/logout/` | `logout_view` | JWT |
| POST | `/api/v1/auth/otp/send/` | `otp_send` | Public |
| POST | `/api/v1/auth/otp/verify/` | `otp_verify` | Public |
| GET/PUT/PATCH | `/api/v1/users/me/` | `me_view` | JWT |

### Serializers (DRF)

- `UserSerializer` — read-only user profile
- `RegisterSerializer` — email, password, full_name, phone, role
- `LoginSerializer` — email + password → JWT tokens
- `UpdateProfileSerializer` — full_name, phone

### Services

| Function | Location | Purpose |
|---|---|---|
| `assign_customer_role(user)` | services.py | Assign default customer role on registration |
| `assign_role(user, role_code)` | services.py | Generic role assignment |

### Selectors

| Function | Purpose |
|---|---|
| `user_has_role(user, role_code)` | Check if user has a specific role |
| `user_has_permission(user, perm_code)` | Check permission through role chain |
| `get_customer_bookings(user)` | Return user's booking queryset |
| `get_booking_stats(user)` | Booking statistics for dashboard |

### Template Views

| URL Pattern | View | Method |
|---|---|---|
| `/auth/login/` | `LoginView` | GET/POST |
| `/auth/register/` | `register_view` | GET/POST |
| `/auth/register/traveler/` | `register_traveler` | GET/POST |
| `/auth/register/property-owner/` | `register_property_owner` | GET/POST |
| `/auth/register/cab-owner/` | `register_cab_owner` | GET/POST |
| `/auth/register/bus-operator/` | `register_bus_operator` | GET/POST |
| `/auth/register/package-provider/` | `register_package_provider` | GET/POST |
| `/auth/logout/` | `logout_view` | GET |
| `/auth/profile/` | `profile` | GET/POST |
| `/auth/dashboard/` | `customer_dashboard` | GET |

### Admin

- `User` — custom `UserAdmin`
- `Role`, `Permission`, `UserRole`, `RolePermission` — all registered

### Decorators

- `role_required(role_code)` — decorator in `decorators.py` (also in `permissions.py`)

### SMS Service

- `sms_service.py` — SMS backend abstraction (get_sms_backend, send OTP)

---

## 3. App: booking

**Purpose:** Hotel booking lifecycle — context creation, booking, payment, cancellation, refund, settlement.

### Models

#### `Booking` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique, default uuid4 |
| public_booking_id | CharField(20) | unique, auto-generated |
| idempotency_key | CharField(64) | unique, nullable — dedup key |
| user | FK → accounts.User | |
| property | FK → hotels.Property | |
| check_in | DateField | |
| check_out | DateField | |
| status | CharField(20) | 15 choices — enforced via state machine |
| total_amount | DecimalField(12,2) | |
| gross_amount | DecimalField(12,2) | |
| commission_amount | DecimalField(12,2) | |
| gst_amount | DecimalField(12,2) | |
| gateway_fee | DecimalField(12,2) | |
| net_payable_to_hotel | DecimalField(12,2) | |
| refund_amount | DecimalField(12,2) | |
| settlement_status | CharField | |
| payment_reference_id | CharField | |
| refund_reference_id | CharField | |
| hold_expires_at | DateTimeField | nullable |
| guest_name | CharField | |
| guest_email | EmailField | |
| guest_phone | CharField | |
| timer_expires_at | DateTimeField | nullable |

**Status choices:** `hold`, `payment_pending`, `confirmed`, `cancelled`, `completed`, `refund_pending`, `refunded`, `checked_in`, `checked_out`, `no_show`, `disputed`, `expired`, `failed`, `pending`, `settlement_pending`

**State machine transitions** (`VALID_TRANSITIONS` dict on model + `BookingStateMachine` class):

```
hold → payment_pending, expired, cancelled
payment_pending → confirmed, failed, cancelled
confirmed → checked_in, cancelled, no_show, refund_pending
checked_in → checked_out
checked_out → completed, settlement_pending
refund_pending → refunded, disputed
completed → (terminal)
```

#### `BookingRoom`

| Field | Type | Notes |
|---|---|---|
| booking | FK → Booking | |
| room_type | FK → rooms.RoomType | |
| quantity | IntegerField | |

#### `BookingGuest`

| Field | Type | Notes |
|---|---|---|
| booking | FK → Booking | |
| full_name | CharField | |
| age | IntegerField | nullable |
| email | EmailField | blank |

#### `BookingPriceBreakdown`

| Field | Type | Notes |
|---|---|---|
| booking | OneToOne → Booking | |
| base_amount | DecimalField | |
| meal_amount | DecimalField | |
| service_fee | DecimalField | |
| gst_amount | DecimalField | |
| promo_discount | DecimalField | |
| total | DecimalField | |

#### `BookingStatusHistory`

| Field | Type | Notes |
|---|---|---|
| booking | FK → Booking | |
| status | CharField | |
| note | TextField | |
| created_at | DateTimeField | auto_now_add |

#### `BookingContext`

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| session_key | CharField | |
| user | FK → User | nullable |
| property | FK → hotels.Property | |
| room_type | FK → rooms.RoomType | nullable |
| checkin / checkout | DateField | |
| adults / children / rooms | IntegerField | |
| meal_plan | CharField | |
| pricing snapshot fields | Decimal | base/meal/service_fee/gst/promo/total |
| promo_code | CharField | blank |
| booking | FK → Booking | nullable (linked after conversion) |
| context_status | CharField | active / converted / expired / abandoned |
| expires_at | DateTimeField | |

#### `CancellationPolicy` (in `cancellation_models.py`)

| Field | Type | Notes |
|---|---|---|
| property | OneToOne → hotels.Property | |
| policy_type | CharField | free / moderate / strict / super_strict / non_refundable |
| free_cancel_hours | IntegerField | default 72 |
| partial_refund_enabled | BooleanField | |
| partial_refund_percent | DecimalField | |
| partial_refund_hours | IntegerField | default 24 |
| non_refundable_hours | IntegerField | default 0 |
| platform_fee_always_withheld | BooleanField | default True |
| display_note | TextField | |

#### `Settlement` (in `settlement_models.py`)

| Field | Type | Notes |
|---|---|---|
| property | FK → hotels.Property | |
| period_start / period_end | DateField | |
| total_gross | DecimalField | |
| total_commission | DecimalField | |
| total_gateway_fee | DecimalField | |
| total_payable | DecimalField | |
| total_refunded | DecimalField | |
| status | CharField | pending / processing / paid / failed |
| paid_at | DateTimeField | nullable |
| payment_reference_id | CharField | |

#### `SettlementLineItem` (in `settlement_models.py`)

| Field | Type | Notes |
|---|---|---|
| settlement | FK → Settlement | |
| booking | FK → Booking | |
| gross_amount / commission / gateway_fee / payable | DecimalField | |
| is_refunded | BooleanField | |

#### `BookingRetryQueue` (in `distributed_locks.py`)

| Field | Type | Notes |
|---|---|---|
| booking_uuid | UUIDField | unique |
| retry_count | IntegerField | |
| last_error | TextField | |
| next_retry_at | DateTimeField | |

### API Endpoints (v1)

| Method | URL | View | Auth |
|---|---|---|---|
| POST | `/api/v1/booking/context/` | `create_booking_context` | JWT |
| GET | `/api/v1/booking/context/<uuid>/` | `get_booking_context` | JWT |
| GET | `/api/v1/booking/context/<int>/` | `get_booking_context_by_id` | JWT (legacy) |
| POST | `/api/v1/booking/` | `create_booking_view` | JWT |
| GET | `/api/v1/booking/my/` | `my_bookings` | JWT |
| GET | `/api/v1/booking/<uuid>/` | `booking_detail` | JWT |
| POST | `/api/v1/booking/<uuid>/cancel/` | `cancel_booking` | JWT |

### Serializers (DRF)

- `BookingContextCreateSerializer` — property, room_type, checkin/checkout, adults/children/rooms, meal_plan, promo_code
- `BookingContextSerializer` — full context with computed GST fields
- `BookingCreateSerializer` — context_uuid, guest_name/email/phone, idempotency_key
- `BookingRoomSerializer` — room_type, quantity
- `BookingPriceBreakdownSerializer` — all price fields
- `BookingDetailSerializer` — full booking with nested breakdown, rooms, guests
- `BookingListSerializer` — summary for list views

### Services

| Function | File | Purpose |
|---|---|---|
| `create_booking(context, user, guest_data)` | services.py | Atomic booking with `select_for_update` inventory locking |
| `create_simple_booking(...)` | services.py | Simplified booking path |
| `transition_booking_status(booking, status, note)` | services.py | Wrapper around state machine |
| `BookingStateMachine.transition(booking, new_status, note)` | state_machine.py | Enforced state transitions with audit trail |
| `BookingStateMachine.can_transition(booking, target)` | state_machine.py | Check if transition is allowed |
| `calculate_booking_financials(booking, gross)` | financial_services.py | Commission (15%), GST (18%), gateway fee (2%), net payable |
| `set_booking_financials(booking, gross)` | financial_services.py | Atomic update of all financial fields |
| `get_booking_financial_summary(booking)` | financial_services.py | Human-readable breakdown |
| `calculate_refund_amount(booking, cancel_time)` | refund_services.py | 3-tier refund: 100% (>72h), 50% (24-72h), 0% (<24h) |
| `initiate_refund(booking, reason)` | refund_services.py | Full refund flow: calculate → transition → gateway API → mark |
| `RedisDistributedLock` | distributed_locks.py | Redis-first + thread-lock fallback for concurrency |

### Pricing Engine (`pricing_engine.py`)

Class `PricingEngine`:
- `__init__(base_price_per_night, nights, room_count)`
- `apply_property_discount(percent/amount)` — early booking, loyalty
- `apply_platform_discount(percent/amount)` — day sale
- `apply_coupon(coupon_code, percent/amount)` — promo code
- `apply_gst()` — 5% for total ≤ ₹7500, 18% for > ₹7500
- `finalize()` → complete breakdown dict

### Template Views

| URL | View | Method |
|---|---|---|
| `/booking/property/<id>/` | `create` | GET/POST |
| `/booking/<uuid>/review/` | `review` | GET |
| `/booking/<uuid>/payment/` | `payment` | GET/POST |
| `/booking/<uuid>/success/` | `success` | GET |
| `/booking/<uuid>/cancel/` | `cancel` | GET/POST |
| `/booking/checkout/<ref>/` | `checkout` | GET/POST |
| `/booking/create-booking/` | `create_booking_from_form` | POST |

---

## 4. App: hotels

**Purpose:** Property listings, search, reviews, approval workflow, autosuggest.

### Models

#### `Property` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| owner | FK → accounts.User | |
| name | CharField(200) | |
| slug | SlugField | unique |
| property_type | CharField | choices: hotel, resort, homestay, villa, apartment, hostel, guest_house |
| city | FK → core.City | nullable |
| locality | FK → core.Locality | nullable |
| city_text | CharField | **deprecated** — use FK city |
| area | CharField | |
| landmark | CharField | |
| country | CharField | default "India" |
| address | TextField | |
| description | TextField | |
| rating | DecimalField(3,1) | auto-updated from reviews |
| review_count | IntegerField | auto-updated |
| popularity_score | IntegerField | |
| star_category | IntegerField | 1–5 |
| latitude / longitude | DecimalField | |
| place_id | CharField | Google Places |
| formatted_address | TextField | |
| bookings_today / this_week | IntegerField | |
| is_trending | BooleanField | |
| tags | JSONField | |
| has_free_cancellation | BooleanField | |
| cancellation_hours | IntegerField | |
| pay_at_hotel | BooleanField | |
| status | CharField | pending / approved / rejected / suspended |
| commission_percentage | DecimalField | |
| agreement_file | FileField | |
| agreement_signed | BooleanField | |

**Indexes:** Multiple composite indexes on (city, status), (status, rating), (status, agreement_signed).

#### `PropertyImage`

| Field | Type | Notes |
|---|---|---|
| property | FK → Property | related_name=`images` |
| image | ImageField | |
| image_url | URLField | blank |
| caption | CharField | |
| is_featured | BooleanField | |
| display_order | IntegerField | |

#### `RatingAggregate`

| Field | Type | Notes |
|---|---|---|
| property | FK → Property | |
| cleanliness / service / location / amenities / value_for_money | DecimalField(3,1) | |
| total_reviews | IntegerField | |

#### `Category`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| slug | SlugField | unique |
| description | TextField | |
| icon | CharField | |
| image | ImageField | |
| display_order | IntegerField | |

#### `PropertyCategory`

| Field | Type | Notes |
|---|---|---|
| property | FK → Property | |
| category | FK → Category | |
| | | `unique_together = (property, category)` |

#### `PropertyPolicy`

| Field | Type | Notes |
|---|---|---|
| property | FK → Property | |
| title | CharField | |
| description | TextField | |

#### `PropertyAmenity`

| Field | Type | Notes |
|---|---|---|
| property | FK → Property | |
| name | CharField | |
| icon | CharField | |

#### `RecentSearch`

| Field | Type | Notes |
|---|---|---|
| user | FK → User | nullable |
| session_key | CharField | |
| search_text | CharField | |
| checkin / checkout | DateField | |
| adults / children / rooms | IntegerField | |

#### `Review` (in `review_models.py`)

| Field | Type | Notes |
|---|---|---|
| booking | OneToOne → booking.Booking | |
| property | FK → Property | |
| user | FK → User | |
| overall_rating | DecimalField(2,1) | 1.0 – 5.0 |
| cleanliness / service / location / amenities / value_for_money | DecimalField(2,1) | 1.0 – 5.0 each |
| title | CharField(200) | |
| comment | TextField(2000) | |
| traveller_type | CharField | solo / couple / family / business / group |
| status | CharField | pending / approved / rejected |
| moderation_note | TextField | |
| owner_response | TextField | |
| owner_responded_at | DateTimeField | |

On `save()` (if status == approved) → auto-recalculates `Property.rating`, `Property.review_count`, and `RatingAggregate`.

#### `AutoApprovalSettings` (in `approval_models.py`)

| Field | Type | Notes |
|---|---|---|
| auto_approve_enabled | BooleanField | default True |
| auto_approve_hours | IntegerField | choices: 3, 6, 12, 24 |
| notify_admins / notify_owners | BooleanField | |

Singleton pattern via `get_settings()`.

#### `PendingPropertyChange` (in `approval_models.py`)

| Field | Type | Notes |
|---|---|---|
| property | FK → Property | |
| field_name | CharField(100) | |
| field_label | CharField(200) | |
| old_value / new_value | TextField | |
| status | CharField | pending / approved / rejected / auto_approved |
| requested_at | DateTimeField | |
| reviewed_at | DateTimeField | nullable |
| reviewed_by | FK → User | nullable |
| admin_notes | TextField | |

Methods: `approve()`, `reject()`, `auto_approve()`, `is_ready_for_auto_approval`.

### API Endpoints (v1)

| Method | URL | View | Auth |
|---|---|---|---|
| GET | `/api/v1/hotels/properties/` | `property_list_api` | Public |
| GET | `/api/v1/hotels/search/` | `property_search_api` | Public |
| GET | `/api/v1/hotels/properties/<slug>/` | `property_detail_api` | Public |
| GET | `/api/v1/hotels/properties/<slug>/availability/` | `property_availability_api` | Public |
| GET | `/api/v1/hotels/properties/<slug>/reviews/` | `property_reviews` | Public |
| POST | `/api/v1/hotels/reviews/` | `submit_review` | JWT |
| GET | `/api/v1/hotels/reviews/my/` | `my_reviews` | JWT |
| POST | `/api/v1/hotels/pricing/quote/` | `pricing_quote_api` | Public |
| GET | `/api/v1/hotels/pricing/intelligence/<uuid>/` | `pricing_intelligence_api` | JWT |
| GET | `/api/v1/hotels/autosuggest/` | `autosuggest_api` | Public |
| GET | `/api/v1/hotels/hotels/aggregations/` | `aggregations_api` | Public |

### Legacy API (non-versioned)

| Method | URL | View |
|---|---|---|
| GET | `/api/hotels/suggest/` | `suggest_hotels` (in `hotels/api/__init__.py`) |

### Serializers (DRF)

- `PropertyImageSerializer`, `PropertyAmenitySerializer`
- `RoomImageSerializer`, `RoomAmenitySerializer`, `RoomMealPlanSerializer`, `RoomTypeSerializer`
- `PropertyPolicySerializer`
- `PropertyCardSerializer` — for list cards
- `PropertyDetailSerializer` — full detail with nested rooms, images, amenities, policies

### Services

Located in `hotels/services/` directory (service layer):
- Property CRUD services
- Availability checking
- Image handling (`image_handler.py`, `image_optimization.py`)
- Autosuggest (`autosuggest_service.py`)
- Review management (`review_service.py`)
- Filter service (`filter_service.py`)

### Template Views

Located in `hotels/views/` directory:
- Property listing, detail, search result views
- Approval views (`approval_views.py`)

### Admin

- `Property`, `PropertyImage`, `PropertyAmenity`, `PropertyPolicy`, `Category`, `PropertyCategory` — all registered

---

## 5. App: rooms

**Purpose:** Room types, per-date inventory, meal plans, amenities.

### Models

#### `RoomType` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| property | FK → hotels.Property | related_name=`room_types` |
| name | CharField | |
| description | TextField | |
| capacity | IntegerField | |
| max_occupancy | IntegerField | |
| room_size | CharField | |
| available_count | IntegerField | |
| price_per_night | DecimalField | |
| base_price | DecimalField | |
| max_guests | IntegerField | |
| bed_type | CharField | |
| room_size_sqm | DecimalField | |
| meal_plan | CharField | choices: room_only, breakfast, half_board, full_board, all_inclusive |

#### `RoomInventory`

| Field | Type | Notes |
|---|---|---|
| room_type | FK → RoomType | |
| date | DateField | |
| available_rooms | IntegerField | `CheckConstraint ≥ 0` |
| price | DecimalField | date-specific override |
| is_closed | BooleanField | |
| available_count | IntegerField | |
| booked_count | IntegerField | |
| | | `unique_together = (room_type, date)` |

#### `RoomImage`

| Field | Type | Notes |
|---|---|---|
| room_type | FK → RoomType | |
| image | ImageField | |
| image_url | URLField | |
| alt_text | CharField | |
| is_primary / is_featured | BooleanField | |
| display_order | IntegerField | |

#### `RoomMealPlan`

| Field | Type | Notes |
|---|---|---|
| room_type | FK → RoomType | |
| code | CharField | choices: RO, CP, MAP, AP, AI |
| name | CharField | |
| price_modifier | DecimalField | |
| description | TextField | |
| is_available | BooleanField | |
| display_order | IntegerField | |
| | | `unique_together = (room_type, code)` |

#### `RoomAmenity`

| Field | Type | Notes |
|---|---|---|
| room_type | FK → RoomType | |
| name | CharField | |
| icon | CharField | |

---

## 6. App: core

**Purpose:** Shared base models, location hierarchy, marketplace entities, notifications, middleware, health checks, Celery tasks.

### Models

#### `TimeStampedModel` (abstract)

| Field | Type | Notes |
|---|---|---|
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |
| is_active | BooleanField | default True |

Used as base by almost every model in the project.

#### `OperationLog`

| Field | Type | Notes |
|---|---|---|
| operation_type | CharField | |
| status | CharField | |
| details | JSONField | |
| timestamp | DateTimeField | |

#### `PlatformSettings`

| Field | Type | Notes |
|---|---|---|
| default_commission_property | DecimalField | |
| default_commission_cab | DecimalField | |
| default_commission_bus | DecimalField | |
| default_commission_package | DecimalField | |
| require_agreement_signature | BooleanField | |
| platform_name | CharField | |
| support_email | EmailField | |
| service_fee_percent | DecimalField | |

### Location Models (in `location_models.py`)

#### `Country`

| Field | Type | Notes |
|---|---|---|
| code | CharField(3) | unique |
| name | CharField(100) | |
| display_name | CharField(200) | |
| is_active | BooleanField | |

#### `State`

| Field | Type | Notes |
|---|---|---|
| country | FK → Country | |
| code | CharField(10) | unique |
| name | CharField(100) | |
| display_name | CharField(200) | |

#### `City`

| Field | Type | Notes |
|---|---|---|
| state | FK → State | |
| code | CharField(20) | unique |
| name | CharField(100) | |
| display_name | CharField(200) | |
| slug | SlugField | unique |
| alternate_names | JSONField | |
| latitude / longitude | DecimalField | |
| bounding_box (ne_lat, ne_lng, sw_lat, sw_lng) | DecimalField | |
| hotel_count | IntegerField | |
| popularity_score | IntegerField | |
| is_top_destination | BooleanField | |

#### `Locality`

| Field | Type | Notes |
|---|---|---|
| city | FK → City | |
| name | CharField(100) | |
| display_name | CharField(200) | |
| slug | SlugField | |
| latitude / longitude | DecimalField | |
| hotel_count | IntegerField | |
| avg_price | DecimalField | |
| popularity_score | IntegerField | |
| landmarks | JSONField | |
| locality_type | CharField | choices: neighbourhood, suburb, area, zone |

#### `LocationSearchIndex`

| Field | Type | Notes |
|---|---|---|
| entity_type | CharField | city / locality / state |
| entity_id | IntegerField | |
| display_name | CharField | |
| search_text | CharField | |
| alternate_names | JSONField | |
| city / state / country | FK | nullable |
| search_score / search_count | IntegerField | |
| conversion_rate | DecimalField | |
| latitude / longitude | DecimalField | |

#### `RegionGroup`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |

### Marketplace Models (in `marketplace_models.py`)

#### `Destination`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| slug | SlugField | unique |
| country / state | CharField | |
| description | TextField | |
| image | ImageField | |
| is_trending | BooleanField | |
| priority | IntegerField | |
| search_count | IntegerField | |

#### `Category` (marketplace)

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| slug | SlugField | unique |
| icon | CharField | |
| description | TextField | |

> **Note:** This is DIFFERENT from `hotels.Category`. Potential naming collision.

#### `Offer` (marketplace)

| Field | Type | Notes |
|---|---|---|
| title | CharField | |
| subtitle | CharField | |
| offer_type | CharField | percentage / flat / cashback |
| discount_value | DecimalField | |
| code | CharField | unique |
| category | FK → Category (marketplace) | |
| image | ImageField | |
| valid_from / valid_until | DateTimeField | |
| min_booking_amount | DecimalField | |
| max_discount | DecimalField | |

> **Note:** This is DIFFERENT from `offers.Offer`. Another naming collision.

#### `SearchIndex` (marketplace)

| Field | Type | Notes |
|---|---|---|
| search_type | CharField | |
| name / normalized_name | CharField | |
| city / state | CharField | |
| content_type | FK → ContentType | |
| object_id | IntegerField | |
| search_count | IntegerField | |

### Observability Models (in `observability.py`)

#### `SystemMetrics`

Booking metrics, performance metrics, inventory metrics, revenue metrics, health check fields.

#### `InventoryHealthCheck`

| Field | Type | Notes |
|---|---|---|
| hotel_id | IntegerField | |
| issue_type | CharField | |
| description | TextField | |
| severity | CharField | |
| is_resolved | BooleanField | |

#### `PerformanceLog`

| Field | Type | Notes |
|---|---|---|
| operation_type | CharField | |
| duration_ms | DecimalField | |
| etc. | | |

### Notification Model (in `notifications.py`)

#### `Notification`

| Field | Type | Notes |
|---|---|---|
| user | FK → User | |
| category | CharField | booking / payment / cancellation / payout / promo / system |
| title | CharField(200) | |
| message | TextField | |
| data | JSONField | nullable — structured routing payload |
| is_read | BooleanField | indexed |
| read_at | DateTimeField | nullable |

**Index:** `(user, is_read, -created_at)`

### Notification Dispatcher Functions (in `notifications.py`)

| Function | Channels | Calls |
|---|---|---|
| `notify_booking_confirmed(booking)` | Email + SMS + In-app + Owner email | → Celery task |
| `notify_payment_received(booking, txn_id, amount)` | Email + In-app | → Celery task |
| `notify_booking_cancelled(booking, refund_amount)` | Email + SMS + In-app | → Celery task |
| `notify_owner_payout(owner, amount, booking_count)` | Email + In-app | → Celery task |

### API Endpoints

| Method | URL | View | Notes |
|---|---|---|---|
| GET | `/` or `/home/` | `home` | Homepage |
| GET | `/dashboard/` | `dashboard` | Role-based redirect |
| GET | `/component-library/` | `component_library_preview` | UI preview |
| POST | `/test/seed/` | `seed_test_data` | Dev only |
| GET | `/health/` | `health_check` | Simple health |
| GET | `/health/detailed/` | `health_check` detailed | DB + cache check |

### Notification API (under root urls.py → `/api/v1/notifications/`)

| Method | URL | View |
|---|---|---|
| GET | `/api/v1/notifications/` | `notification_list` |
| POST | `/api/v1/notifications/mark-read/` | `mark_notifications_read` |
| GET | `/api/v1/notifications/unread-count/` | `unread_count` |

### Marketplace API (under core urls.py)

| Method | URL | View |
|---|---|---|
| GET | `/api/search-autocomplete/` | `SearchAutocompleteAPI` |
| GET | `/api/trending-destinations/` | `TrendingDestinationsAPI` |
| GET | `/api/categories/` | `CategoriesAPI` |
| GET | `/api/offers/` | `OffersAPI` |

### Middleware

| Middleware | File | Purpose |
|---|---|---|
| `GlobalExceptionMiddleware` | middleware/ | Catch unhandled exceptions, return structured JSON errors |
| `RateLimitMiddleware` | middleware/ | Per-IP rate limiting |
| `StructuredLoggingMiddleware` | middleware/ | Request/response structured logging |

### Services

| Function | File | Purpose |
|---|---|---|
| `user_has_role(user, role_code)` | services.py | **Duplicate** of accounts.selectors.user_has_role |
| `get_dashboard_data(user)` | services.py | Dashboard context |
| `get_home_data()` | services.py | Home page context |

### Utilities

- `cache_utils.py` — cache helpers
- `date_utils.py` — date range utilities
- `geo_search.py` — geographic search helpers
- `throttles.py` — DRF custom throttle classes
- `api_validators.py` — request validation
- `property_validator.py` — property data validation
- `logging_formatters.py` — custom log formatters
- `logging_service.py` — `OperationLogger` class
- `startup_validator.py` — boot-time config validation
- `ui_consistency.py` — UI consistency checks

---

## 7. App: buses

**Purpose:** Bus listings, seat selection, bus booking.

### Models

#### `BusType`

| Field | Type | Notes |
|---|---|---|
| name | CharField | choices: AC Sleeper, Non-AC Sleeper, AC Semi-Sleeper, Volvo, etc. |
| base_fare | DecimalField | |
| capacity | IntegerField | |

#### `Bus` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| operator | FK → User | |
| registration_number | CharField | unique |
| bus_type | FK → BusType | |
| operator_name | CharField | |
| from_city / to_city | CharField | |
| departure_time / arrival_time | TimeField | |
| journey_date | DateField | |
| price_per_seat | DecimalField | |
| available_seats | IntegerField | |
| is_active | BooleanField | |
| amenities | JSONField | |

#### `BusSeat`

| Field | Type | Notes |
|---|---|---|
| bus | FK → Bus | |
| seat_number | CharField | |
| row / column | IntegerField | |
| is_ladies_seat | BooleanField | |
| state | CharField | available / booked / ladies / selected |
| | | `unique_together = (bus, seat_number)` |

#### `BusBooking` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| public_booking_id | CharField(20) | unique |
| idempotency_key | CharField(64) | unique, nullable |
| user | FK → User | |
| bus | FK → Bus | |
| journey_date | DateField | |
| status | CharField | |
| total_amount | DecimalField | |
| promo_code | CharField | |

#### `BusBookingPassenger`

| Field | Type | Notes |
|---|---|---|
| booking | FK → BusBooking | |
| seat | FK → BusSeat | |
| full_name / age / gender / phone | Fields | |
| id_proof | CharField | |

#### `BusPriceBreakdown`

| Field | Type | Notes |
|---|---|---|
| booking | OneToOne → BusBooking | |
| base / service_fee / gst / promo_discount / total | DecimalField | |

### Services

| Function | Purpose |
|---|---|
| `ensure_bus_seats(bus)` | Auto-create seat records for a bus |
| `create_bus_booking(user, bus, seats, passengers, promo)` | Atomic booking with seat locking |
| `ensure_default_bus_type()` | Create default bus type if none exist |

### Serializers

- `BusRenderReadySerializer` — **Custom (non-DRF)** serializer for template rendering

### Template Views

| URL | View | Method |
|---|---|---|
| `/buses/` | `list_buses` | GET/POST |
| `/buses/<id>/` | `bus_detail` | GET |
| `/buses/<id>/book/` | `bus_booking` | GET/POST |
| `/buses/booking/<uuid>/` | `booking_review` | GET |
| `/buses/booking/<uuid>/success/` | `booking_success` | GET |
| `/buses/dashboard/` | `owner dashboard` | GET |
| `/buses/dashboard/buses/<id>/` | `bus detail (owner)` | GET |
| `/buses/dashboard/buses/create/` | `owner_bus_add` | GET/POST |
| `/buses/owner/register/` | registration redirect | GET |

---

## 8. App: cabs

**Purpose:** Cab listings, per-km pricing, cab booking lifetime.

### Models

#### `CabType`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| description | TextField | |

#### `Cab` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| owner | FK → User | |
| name | CharField | |
| city | CharField | choices: bangalore, mumbai, delhi, etc. |
| seats | CharField | choices: 4, 6, 7 |
| fuel_type | CharField | |
| base_price_per_km | DecimalField | |
| system_price_per_km | DecimalField | |
| is_active | BooleanField | |

**Indexes:** `(city, is_active)`, `(is_active, base_price_per_km)`

#### `CabImage`

| Field | Type | Notes |
|---|---|---|
| cab | FK → Cab | |
| image | ImageField | |
| is_primary | BooleanField | |

#### `CabAvailability`

| Field | Type | Notes |
|---|---|---|
| cab | FK → Cab | |
| date | DateField | |
| is_available | BooleanField | |
| | | `unique_together = (cab, date)` |

#### `CabBooking` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| uuid | UUIDField | unique |
| public_booking_id | CharField(20) | unique |
| idempotency_key | CharField(64) | unique, nullable |
| cab | FK → Cab | |
| user | FK → User | |
| booking_date | DateField | |
| distance_km | DecimalField | |
| base_fare / price_per_km | DecimalField | |
| total_price / discount_amount / final_price | DecimalField | |
| status | CharField | |
| promo_code | CharField | |

**Indexes:** `(user, status)`, `(cab, booking_date)`

### Services

| Function | Purpose |
|---|---|
| `get_best_coupon(module, amount)` | Find best applicable promo |
| `apply_promo_to_booking(booking, promo)` | Apply promo discount |
| `create_cab_booking(user, cab, date, distance, promo_code)` | Atomic cab booking |
| `set_system_price(cab_id, price_per_km)` | Admin price override |
| `update_cab_details(cab_id, data)` | Update cab info |
| `deactivate_cab(cab_id)` | Soft-deactivate |

### Serializers

- `CabRenderReadySerializer` — **Custom (non-DRF)** serializer for templates

### Template Views

| URL | View | Method |
|---|---|---|
| `/cabs/` | `cab_list` | GET |
| `/cabs/<id>/` | `cab_detail` | GET |
| `/cabs/<id>/book/` | `cab_booking` | GET/POST |
| `/cabs/booking/<id>/success/` | `booking_success` | GET |
| `/cabs/dashboard/` | `owner dashboard` | GET |
| `/cabs/dashboard/cabs/` | `owner_cab_list` | GET |
| `/cabs/dashboard/cabs/create/` | `owner_cab_add` | GET/POST |
| `/cabs/owner/register/` | registration | GET |
| `/cabs/owner/all/` | `owner_cab_list` | GET |
| `/cabs/owner/<id>/edit/` | `owner_cab_edit` | GET/POST |
| `/cabs/owner/<id>/delete/` | `owner_cab_delete` | POST |

### Additional

- `routing_engine.py` — distance/fare calculation logic
- `selectors/` directory — query selectors
- `ota_selectors.py` — OTA-specific queries

---

## 9. App: payments

**Purpose:** Multi-gateway payment processing, webhook handling, reconciliation.

### Models

#### `Payment`

| Field | Type | Notes |
|---|---|---|
| booking | FK → booking.Booking | nullable |
| user | FK → User | |
| amount | DecimalField | |
| payment_method | CharField | |
| transaction_id | CharField | unique |
| status | CharField | |

#### `PaymentTransaction`

| Field | Type | Notes |
|---|---|---|
| transaction_id | CharField | unique, auto-generated |
| idempotency_key | CharField | unique, nullable |
| gateway_transaction_id | CharField | |
| gateway | CharField | wallet / cashfree / stripe / paytm_upi |
| user | FK → User | |
| booking | FK → booking.Booking | nullable |
| booking_reference | CharField | |
| amount | DecimalField | |
| currency | CharField | default INR |
| status | CharField | initiated / pending / success / failed / cancelled / refunded |
| gateway_response | JSONField | |
| failure_reason | TextField | |
| webhook_received_at | DateTimeField | |
| webhook_payload | JSONField | |
| refund_amount | DecimalField | |
| refund_initiated_at | DateTimeField | |
| refund_gateway_id | CharField | |

Methods: `mark_pending()`, `mark_success()`, `mark_failed()`, `initiate_refund()`

#### `PaymentReconciliation`

| Field | Type | Notes |
|---|---|---|
| date | DateField | |
| gateway | CharField | |
| expected_amount / settled_amount / discrepancy_amount | DecimalField | |
| transactions_matched / transactions_unmatched | IntegerField | |
| status | CharField | |

### API Endpoints (v1)

| Method | URL | View | Auth |
|---|---|---|---|
| POST | `/api/v1/payment/initiate/` | `initiate_payment` | JWT |
| GET | `/api/v1/payment/status/<txn_id>/` | `payment_status` | JWT |
| GET | `/api/v1/payment/gateways/<booking_uuid>/` | `available_gateways` | JWT |
| POST | `/api/v1/payment/webhook/cashfree/` | `webhook_cashfree` | Public (signature verified) |
| POST | `/api/v1/payment/webhook/stripe/` | `webhook_stripe` | Public (signature verified) |
| POST | `/api/v1/payment/webhook/paytm/` | `webhook_paytm` | Public (signature verified) |

### Services

| Function | File | Purpose |
|---|---|---|
| `process_payment(booking, amount, gateway, user)` | services.py | Create PaymentTransaction, route to gateway |
| `handle_payment_webhook(gateway, payload)` | services.py | Idempotent webhook handler, transitions booking status |

### Template Views

| URL | View |
|---|---|
| `/payments/<uuid>/` | `invoice_detail` |
| `/payments/webhook/` | `payment_webhook` |

---

## 10. App: wallet

**Purpose:** Customer wallet (payments/refunds) + Owner wallet (settlement payouts).

### Models

#### `Wallet`

| Field | Type | Notes |
|---|---|---|
| user | OneToOne → User | |
| balance | DecimalField(12,2) | default 0.00 |
| locked_balance | DecimalField(12,2) | |
| currency | CharField | default INR |
| is_active | BooleanField | |

Methods: `can_debit(amount)`, `debit(amount, txn_type, reference, note)`, `credit(...)`.

#### `WalletTransaction`

| Field | Type | Notes |
|---|---|---|
| uid | UUIDField | unique |
| wallet | FK → Wallet | |
| txn_type | CharField | credit / debit / payment / refund / cashback / settlement / lock / unlock / promo |
| amount | DecimalField(12,2) | Positive=credit, Negative=debit |
| balance_after | DecimalField(12,2) | snapshot |
| reference | CharField | indexed |
| note | CharField(300) | |
| is_reversed | BooleanField | |

#### `OwnerWallet`

| Field | Type | Notes |
|---|---|---|
| owner | OneToOne → User | |
| balance | DecimalField(15,2) | settled earnings |
| pending_balance | DecimalField(15,2) | confirmed but not checked out |
| total_earned | DecimalField(15,2) | lifetime |
| currency | CharField | INR |
| bank_account_name / number / ifsc / bank_name | CharField | |
| upi_id | CharField | |
| is_verified | BooleanField | admin-verified before payout |

Methods: `credit_settlement(amount, booking_reference, note)`, `mark_pending(amount, booking_reference)`.

#### `OwnerWalletTransaction`

| Field | Type | Notes |
|---|---|---|
| uid | UUIDField | unique |
| owner_wallet | FK → OwnerWallet | |
| txn_type | CharField | settlement / pending / reversal / withdrawal / adjustment |
| amount | DecimalField(15,2) | |
| balance_after | DecimalField(15,2) | |
| booking_reference | CharField | indexed |
| note | CharField(300) | |

### API Endpoints (v1)

| Method | URL | View | Auth |
|---|---|---|---|
| GET | `/api/v1/wallet/` | `wallet_balance` | JWT |
| GET | `/api/v1/wallet/transactions/` | `wallet_transactions` | JWT |
| POST | `/api/v1/wallet/topup/` | `wallet_topup` | JWT |
| GET | `/api/v1/wallet/owner/` | `owner_wallet_balance` | JWT (owner) |
| GET | `/api/v1/wallet/owner/transactions/` | `owner_wallet_transactions` | JWT (owner) |

### Serializers (DRF)

- `WalletSerializer`, `WalletTransactionSerializer`, `TopUpSerializer`
- `OwnerWalletSerializer`, `OwnerTransactionSerializer`

### Services

| Function | Purpose |
|---|---|
| `get_or_create_wallet(user)` | Ensure wallet exists |
| `get_or_create_owner_wallet(user)` | Ensure owner wallet exists |
| `check_wallet_balance(user, amount)` | Balance check |
| `use_wallet_for_payment(user, amount, booking_ref)` | Debit for booking payment |
| `refund_to_wallet(user, amount, booking_ref)` | Credit refund |
| `get_wallet_balance(user)` | Read balance |
| `get_transaction_history(user)` | Transaction list |

---

## 11. App: promos

**Purpose:** Coupon codes, cashback campaigns, promo discount application.

### Models

#### `Promo`

| Field | Type | Notes |
|---|---|---|
| code | CharField | unique |
| discount_type | CharField | percent / amount |
| value | DecimalField | |
| max_discount | DecimalField | cap for percent type |
| max_uses | IntegerField | |
| starts_at / ends_at | DateTimeField | |
| applicable_module | CharField | hotels / buses / cabs / packages / flights / trains / all |
| is_active | BooleanField | |

#### `PromoUsage`

| Field | Type | Notes |
|---|---|---|
| promo | FK → Promo | |
| booking | FK → booking.Booking | |
| user | FK → User | |

#### `CashbackCampaign`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| slug | SlugField | unique |
| description | TextField | |
| cashback_type / cashback_value | CharField / DecimalField | |
| max_cashback_per_booking / per_user | DecimalField | |
| min_booking_value | DecimalField | |
| cashback_expiry_days | IntegerField | |
| status | CharField | |
| start_date / end_date | DateField | |
| properties | M2M → hotels.Property | |
| created_by | FK → User | |

#### `CashbackCredit`

| Field | Type | Notes |
|---|---|---|
| campaign | FK → CashbackCampaign | |
| booking | FK → booking.Booking | |
| user | FK → User | |
| amount | DecimalField | |
| wallet_txn_reference | CharField | |
| expires_at | DateTimeField | |
| is_expired | BooleanField | |

### API Endpoints (v1)

| Method | URL | View | Auth |
|---|---|---|---|
| POST | `/api/v1/promo/apply/` | `apply_promo` | JWT |

### Services

| Function | File | Purpose |
|---|---|---|
| `calculate_promo_discount(code, module, amount)` | services.py | Validate + calculate discount |
| `CouponService.get_best_coupon(module, amount)` | coupon_service.py | Find best promo for amount |
| `CouponService.validate_coupon(code, module, amount, user)` | coupon_service.py | Full coupon validation |

### Additional Files

- `abuse_protection.py` — rate limiting / abuse detection for promo usage
- `hardening.py` — promo system hardening rules

---

## 12. App: pricing

**Purpose:** Price breakdown calculation with GST slabs, competitor pricing.

### Models

#### `CompetitorPrice`

| Field | Type | Notes |
|---|---|---|
| property | FK → hotels.Property | |
| competitor_name | CharField | |
| source | CharField | |
| price_per_night | DecimalField | |
| date | DateField | |
| fetched_at | DateTimeField | |
| is_available | BooleanField | |
| | | `unique_together = (property, competitor_name, date)` |

### Services

| Function | File | Purpose |
|---|---|---|
| `calculate_price_breakdown(base, meal, rooms, nights)` | services.py | Base + meal + service fee (capped at ₹500) + GST slab (5% ≤ ₹7500, 18% > ₹7500) |

### Additional Files

- `price_engine.py` — advanced pricing engine
- `pricing_service.py` — alternative pricing service
- `core_engine.py` — core pricing calculations

---

## 13. App: inventory

**Purpose:** Supplier mapping, property inventory tracking, price history, concurrency.

### Models

#### `SupplierPropertyMap`

| Field | Type | Notes |
|---|---|---|
| property | FK → hotels.Property | |
| supplier_name | CharField | booking / airbnb / expedia / oyo / tripadvisor |
| external_id | CharField | |
| supplier_property_name / city / lat / lng | Fields | |
| confidence_score | DecimalField | |
| verified | BooleanField | |
| manual_override | BooleanField | |
| verified_by | FK → User | nullable |
| | | `unique_together = (supplier_name, external_id)` |

#### `PropertyInventory`

| Field | Type | Notes |
|---|---|---|
| property | OneToOne → hotels.Property | |
| total_rooms | IntegerField | |
| available_rooms | IntegerField | |
| last_supplier_sync | DateTimeField | |
| sync_status | CharField | |
| version | IntegerField | optimistic locking |

#### `PriceHistory`

| Field | Type | Notes |
|---|---|---|
| property | FK → hotels.Property | |
| base_price | DecimalField | |
| final_price | DecimalField | |
| | | **immutable** — append-only ledger |

### Services

| Function | File | Purpose |
|---|---|---|
| `initialize_inventory(room_type, start, end, total)` | services.py | Create inventory records for date range |
| `reserve_inventory(room_type, start, end, qty)` | services.py | Atomic reservation with `select_for_update` |
| `release_inventory(room_type, start, end, qty)` | services.py | Release on cancellation |
| `update_inventory_total(room_type, start, end, new_total)` | services.py | Adjust total rooms |

### Additional Files

- `concurrency.py` — optimistic locking helpers
- `matching_engine.py` — supplier property matching algorithm
- `selectors.py` — inventory query selectors

---

## 14. App: offers

**Purpose:** Property-specific and global offers/coupons (separate from promos).

### Models

#### `Offer`

| Field | Type | Notes |
|---|---|---|
| title | CharField | |
| description | TextField | |
| offer_type | CharField | percentage / flat / bogo / bundle |
| coupon_code | CharField | unique |
| discount_percentage | DecimalField | |
| discount_flat | DecimalField | |
| start_datetime / end_datetime | DateTimeField | |
| is_active | BooleanField | |
| is_global | BooleanField | |
| created_by | FK → User | |

#### `PropertyOffer`

| Field | Type | Notes |
|---|---|---|
| offer | FK → Offer | |
| property | FK → hotels.Property | |
| | | `unique_together = (offer, property)` |

### Selectors

- `selectors.py` — get active offers, get offers for property

> **Observation:** `offers.Offer` vs `core.marketplace_models.Offer` — naming collision. Two different Offer models exist.

---

## 15. App: meals

**Purpose:** Stub app for meal plan management.

### Models

#### `MealPlan`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| description | TextField | |
| price | DecimalField | |
| meal_type | CharField | |
| icon | CharField | |

> **Note:** This appears to be a stub — `rooms.RoomMealPlan` is the actively used model. Potential redundancy.

---

## 16. App: packages

**Purpose:** Travel packages with itineraries.

### Models

#### `PackageCategory`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| slug | SlugField | unique |
| description | TextField | |
| is_active | BooleanField | |

#### `Package` (extends `TimeStampedModel`)

| Field | Type | Notes |
|---|---|---|
| provider | FK → User | |
| category | FK → PackageCategory | |
| name | CharField | |
| slug | SlugField | unique |
| description | TextField | |
| destination | CharField | |
| duration_days | IntegerField | |
| base_price | DecimalField | |
| rating / review_count | DecimalField / IntegerField | |
| image_url | URLField | |
| inclusions / exclusions | TextField | |
| max_group_size | IntegerField | |
| difficulty_level | CharField | |
| hotel_included / meals_included / transport_included / guide_included | BooleanField | |
| is_active | BooleanField | |

#### `PackageImage`

| Field | Type | Notes |
|---|---|---|
| package | FK → Package | |
| image_url | URLField | |
| is_featured | BooleanField | |
| display_order | IntegerField | |

#### `PackageItinerary`

| Field | Type | Notes |
|---|---|---|
| package | FK → Package | |
| day_number | IntegerField | |
| title | CharField | |
| description | TextField | |
| accommodation | CharField | |
| meals_included | CharField | |

### Template Views

| URL | View | Method |
|---|---|---|
| `/packages/` | `package_list` | GET |
| `/packages/<id>/` | `package_detail` | GET |
| `/packages/<id>/book/` | `package_booking` | GET/POST |

> **Note:** No DRF API — packages are template-only.

---

## 17. App: search

**Purpose:** Unified search index, autocomplete, search engine abstraction.

### Models

#### `SearchIndex`

| Field | Type | Notes |
|---|---|---|
| name | CharField | |
| type | CharField | city / area / property |
| property_count | IntegerField | |
| slug | SlugField | |
| is_active | BooleanField | |
| | | `unique_together = (type, slug)` |

#### `SearchResult` (non-DB class)

Used as a unified result format for search across properties, cities, areas.

### Views (`views_production.py`)

| Function | Method | Purpose |
|---|---|---|
| `search_list` | GET/POST | Main search with filters |
| `search_autocomplete` | GET | Type-ahead search |
| `search_api` | GET | API search endpoint |
| `cities_autocomplete` | GET | City-only autocomplete |
| `location_autocomplete` | GET | Location-based autocomplete |
| `search_index_api` | GET | SearchIndex query |

### URL Patterns

| URL | View |
|---|---|
| `/search/` | `search_list` |
| `/search/autocomplete/` | `search_autocomplete` |
| `/search/api/` | `search_api` |

### Additional

- `engine/` directory — search engine implementations
- `index_builder.py` — SearchIndex population script
- `signals.py` — auto-update index on Property save

---

## 18. App: dashboard_owner

**Purpose:** Property owner dashboard — property CRUD, inventory management, booking management, revenue.

### Models

None (uses models from other apps).

### Template Views

#### Main views (in `views.py`)

| URL Pattern | View | Method |
|---|---|---|
| `/owner/` | `dashboard` | GET |
| `/owner/property/<id>/features/` | `edit_property_features` | GET/POST |
| `/owner/property/add/` | `add_property` | GET/POST |
| `/owner/property/<id>/image/add/` | `add_property_image` | POST |
| `/owner/property/<id>/room/add/` | `add_room` | GET/POST |
| `/owner/property/<id>/room/<id>/image/add/` | `add_room_image` | POST |
| `/owner/property/<id>/meal/add/` | `add_meal` | POST |
| `/owner/property/<id>/offer/add/` | `add_offer` | POST |
| `/owner/property/<id>/room/<id>/amenity/add/` | `add_room_amenity` | POST |
| `/owner/room/amenity/<id>/delete/` | `delete_room_amenity` | POST |
| `/owner/property/<id>/cancellation/` | `cancellation_policy` | GET/POST |
| `/owner/property/<id>/submit-approval/` | `submit_approval` | POST |
| `/owner/property/<id>/set-price/` | `set_price` | POST |
| `/owner/property/<id>/update-ratings/` | `update_ratings` | POST |

#### Owner views (in `owner_views.py`)

| URL Pattern | View | Method |
|---|---|---|
| `/owner/property/<id>/bookings/` | `booking_list` | GET |
| `/owner/property/<id>/revenue/` | `revenue_dashboard` | GET |
| `/owner/property/<id>/checkin/` | `checkin_management` | GET |
| `/owner/property/<id>/inventory/` | `inventory_management` | GET/POST |
| `/owner/property/<id>/bookings/export/` | `export_bookings_csv` | GET |
| `/owner/api/booking/<id>/checkin/` | `api_booking_checkin` | POST (JSON) |
| `/owner/api/booking/<id>/checkout/` | `api_booking_checkout` | POST (JSON) |
| `/owner/api/booking/<id>/cancel/` | `api_booking_cancel` | POST (JSON) |

### Services

- `services.py` — owner dashboard service functions

### Selectors

- `selectors.py` — owner-specific queries (property list, booking stats, revenue)

### Forms

- `forms.py` — PropertyForm, RoomForm, etc.
- `forms_property_features.py` — property feature editing forms

---

## 19. App: dashboard_admin

**Purpose:** Admin/founder dashboard — property approvals, audit logging, metrics.

### Models

#### `PropertyApproval`

| Field | Type | Notes |
|---|---|---|
| property | OneToOne → hotels.Property | |
| status | CharField | pending / approved / rejected (with STATUS_ constants) |
| decided_by | FK → User | |
| decided_at | DateTimeField | |
| notes | TextField | |

#### `AuditLog`

| Field | Type | Notes |
|---|---|---|
| actor | FK → User | |
| action | CharField | |
| object_type | CharField | |
| object_id | IntegerField | |
| metadata | JSONField | |

### Template Views

| URL | View | Auth |
|---|---|---|
| `/admin-dashboard/` | `dashboard` | admin role |
| `/admin-dashboard/approvals/<id>/approve/` | `approve_property` | admin role |
| `/admin-dashboard/approvals/<id>/reject/` | `reject_property` | admin role |

### Additional

- `founder_metrics.py` — founder-only metrics calculations
- `selectors.py` — admin queries (pending approvals, stats)

---

## 20. App: dashboard_finance

**Purpose:** Finance dashboard for revenue/settlement overview.

### Models

None.

### Template Views

| URL | View | Auth |
|---|---|---|
| `/finance/` | `dashboard` | finance_admin role |

### Selectors

- `selectors.py` — financial data queries

---

## 21. App: registration (Unlisted)

**Purpose:** Multi-role registration forms for property owners, bus operators, cab operators.

> ⚠️ **NOT in INSTALLED_APPS.** No `__init__.py` or `apps.py`. Accessed via URL include only.

### Views

| URL | View | Method |
|---|---|---|
| `/register/property/property/` | `register_property` | GET/POST |
| `/register/property/bus/` | `register_bus` | GET/POST |
| `/register/property/cab/` | `register_cab` | GET/POST |

### Services

| Function | Purpose |
|---|---|
| `ensure_role(user, role_code, role_name)` | Get-or-create role + UserRole |
| `create_property_from_form(form, user)` | Create Property + auto-approve via PropertyApproval |
| `create_bus_from_form(form, user)` | Create Bus from form data |
| `create_cab_from_form(form, user)` | Create Cab from form data |

### Forms

- `PropertyRegistrationForm`, `BusRegistrationForm`, `CabRegistrationForm` — in `forms.py`

---

## 22. Root URL Configuration

**File:** `zygotrip_project/urls.py`

### API v1 Routes

| Prefix | Include | App |
|---|---|---|
| `api/v1/hotels/` | `apps.hotels.api.v1.urls` | hotels |
| `api/v1/auth/` + `api/v1/users/` | `apps.accounts.api.v1.urls` | accounts |
| `api/v1/booking/` | `apps.booking.api.v1.urls` | booking |
| `api/v1/wallet/` | `apps.wallet.api.v1.urls` | wallet |
| `api/v1/payment/` | `apps.payments.api.v1.urls` | payments |
| `api/v1/promo/apply/` | `apps.promos.api_views.apply_promo` | promos |
| `api/v1/notifications/` | notification views | core |

### Legacy API Routes

| URL | View |
|---|---|
| `api/hotels/suggest/` | `hotels.api.suggest_hotels` |
| `api/search/` | `search.views_production.search_api` |
| `api/cities/autocomplete/` | `search.views_production.cities_autocomplete` |
| `api/locations/autocomplete/` | `search.views_production.location_autocomplete` |

### Template / Page Routes

| Prefix | Include | App |
|---|---|---|
| `` (root) | `apps.core.urls` | core |
| `auth/` | `apps.accounts.urls` | accounts |
| `hotels/` | `apps.hotels.urls` | hotels |
| `search/` | `apps.search.urls` | search |
| `buses/` | `apps.buses.urls` | buses |
| `packages/` | `apps.packages.urls` | packages |
| `cabs/` | `apps.cabs.urls` | cabs |
| `booking/` | `apps.booking.urls` | booking |
| `payments/` | `apps.payments.urls` | payments |
| `register/property/` | `apps.registration.urls` | registration |
| `owner/` | `apps.dashboard_owner.urls` | dashboard_owner |
| `admin-dashboard/` | `apps.dashboard_admin.urls` | dashboard_admin |
| `finance/` | `apps.dashboard_finance.urls` | dashboard_finance |
| `admin/` | Django admin | django.contrib.admin |
| `legal/privacy/` | TemplateView | legal/privacy.html |
| `legal/terms/` | TemplateView | legal/terms.html |

### Error Handlers

- `handler403 = apps.core.views.permission_denied`

---

## 23. Celery Tasks

### `core/tasks.py`

| Task | Schedule | Purpose |
|---|---|---|
| `cleanup_expired_bookings` | Every 5 min (Beat) | Expire abandoned bookings, refund wallets |
| `generate_daily_reports` | Daily 00:00 | Revenue/booking daily report → cache |
| `send_booking_confirmation_email` | On demand | Legacy email sender |
| `update_search_cache` | On demand | Invalidate search cache on property update |
| `sync_operator_inventory` | On demand | Bus/cab/package inventory → cache |
| `sync_supplier_inventory` | Periodic | Supplier inventory sync via adapter |
| `reconcile_inventory_mismatches` | Periodic | Detect/correct supplier vs local inventory |

### `core/notification_tasks.py`

| Task | Channels | Purpose |
|---|---|---|
| `send_booking_confirmation_notification` | In-app + Email + SMS + Owner email | Booking confirmed |
| `send_payment_notification` | In-app + Email | Payment received |
| `send_cancellation_notification` | In-app + Email + SMS | Booking cancelled |
| `send_owner_payout_notification` | In-app + Email | Settlement payout |

---

## 24. Payment Gateways

**File:** `apps/payments/gateways.py` (682 lines)

### Abstract Base: `PaymentGateway`

All gateways implement:
- `initiate_payment(booking, amount, user, txn)` → dict
- `verify_payment(txn)` → (bool, dict)
- `process_refund(txn, amount)` → (bool, dict)
- `verify_webhook_signature(request)` → (bool, dict)

### Gateway Implementations

| Class | Gateway | Payment Methods | Notes |
|---|---|---|---|
| `WalletGateway` | Internal | ZygoTrip Wallet | Instant debit, no redirect |
| `CashfreeGateway` | Cashfree PG | UPI + Cards | HMAC SHA256 webhook verification |
| `StripeGateway` | Stripe | International cards | Checkout Sessions |
| `PaytmUPIGateway` | Paytm | UPI | |

### `PaymentRouter`

Factory class that maps gateway string → gateway class:
```python
GATEWAY_MAP = {
    'wallet': WalletGateway,
    'cashfree': CashfreeGateway,
    'stripe': StripeGateway,
    'paytm_upi': PaytmUPIGateway,
}
```

All gateways are **idempotent**: duplicate calls with the same `PaymentTransaction` return existing results.

---

## 25. Issues, Gaps & Recommendations

### Critical Issues

1. **`registration` app not in INSTALLED_APPS**
   - Missing `__init__.py` and `apps.py`
   - Works via URL include due to Django URL routing, but not proper app
   - `create_bus_from_form()` references field names (`bus_name`, `route_from`, `route_to`, `base_fare`) that may not match `Bus` model fields (`name`, `from_city`, `to_city`, `price_per_seat`)
   - Same for `create_cab_from_form()` — references `vehicle_type`, `registration_number`, `city_coverage`, `base_fare` which don't match `Cab` model fields

2. **Naming Collisions — Multiple Offer & Category models**
   - `core.marketplace_models.Offer` vs `offers.Offer` — two completely different Offer models
   - `core.marketplace_models.Category` vs `hotels.Category` — two different Category models
   - `core.marketplace_models.SearchIndex` vs `search.SearchIndex` — two different SearchIndex models
   - Risk: import confusion, query ambiguity

3. **Deprecated field still present**
   - `Property.city_text` (CharField) marked deprecated but not removed
   - Should be migrated to `Property.city` FK → `core.City`

### Duplicated Logic

4. **`user_has_role()` duplicated**
   - `apps.accounts.selectors.user_has_role(user, role_code)`
   - `apps.core.services.user_has_role(user, role_code)`
   - Same function in two places — violation of DRY

5. **Pricing/GST calculation spread across multiple files**
   - `pricing/services.py` — `calculate_price_breakdown()` (GST slab: 5%/18% at ₹7500)
   - `booking/financial_services.py` — `calculate_booking_financials()` (flat 18% GST)
   - `booking/pricing_engine.py` — `PricingEngine.apply_gst()` (slab-based)
   - **Inconsistent GST logic**: flat 18% in financial_services vs slab-based in pricing — which is correct?

6. **Two booking confirmation email tasks**
   - `core/tasks.py` → `send_booking_confirmation_email` (simple email)
   - `core/notification_tasks.py` → `send_booking_confirmation_notification` (multi-channel)
   - The old one in `tasks.py` appears to be legacy/dead code

7. **Serializer pattern inconsistency**
   - Hotels, booking, wallet, accounts use proper DRF serializers
   - Buses, cabs use custom `RenderReadySerializer` (non-DRF, template-oriented)
   - Packages have no serializers at all (template-only)

### Missing Pieces

8. **No DRF API for these entities:**
   - Buses — no REST API, only template views
   - Cabs — no REST API, only template views
   - Packages — no REST API, only template views
   - Offers — no API at all (only admin + selectors)
   - Meals — no views, no API (stub app)
   - Dashboard Finance — no API
   - Dashboard Admin — no API

9. **Missing test coverage**
   - Most `tests.py` files contain only `from django.test import TestCase` (empty)
   - No visible test suite for booking, payments, wallet, promos

10. **No explicit migrations check**
    - No CI script visible to verify all migrations are up to date

11. **Missing `apps.py` for registration app**
    - Cannot use Django management commands targeting this app

### Potential Circular Import Risks

12. **Cross-app imports that could be problematic:**
    - `booking.refund_services` → `payments.models` + `payments.gateways`
    - `payments.gateways` → `wallet.models`
    - `booking.services` → `inventory.services` (if exists)
    - `core.notification_tasks` → `booking.models`, `accounts.sms_service`
    - `registration.services` → `dashboard_admin.models`
    - Most are mitigated by lazy imports (inside functions) — good practice observed

13. **`booking.models` has 15+ status choices** with a state machine, but `VALID_TRANSITIONS` is defined on the model class. Consider moving to a dedicated enum or configuration.

### Architecture Observations

14. **Monolithic but well-layered** — clear service/selector/view separation in most apps
15. **Idempotency keys** present on Booking, BusBooking, CabBooking, PaymentTransaction — good for payment safety
16. **Distributed locks** via Redis with thread-lock fallback — good concurrency handling
17. **Settlement pipeline** exists (Booking → Settlement → OwnerWallet) but settlement_service.py needs verification
18. **Notification system** is well-structured: dispatcher → Celery tasks → multi-channel delivery
19. **Property approval workflow** with auto-approval timer is sensible for marketplace

### Summary Statistics

| Metric | Count |
|---|---|
| Django apps in INSTALLED_APPS | 20 |
| Unlisted apps on disk | 1 (registration) |
| Total model classes | ~60+ |
| DRF API endpoints (v1) | ~30 |
| Template view endpoints | ~60+ |
| Celery tasks | ~10 |
| Payment gateways | 4 (Wallet, Cashfree, Stripe, Paytm UPI) |
| Service modules | 15+ |
| Serializer classes (DRF) | ~20 |
| Duplicate/conflicting models | 3 pairs (Offer, Category, SearchIndex) |
