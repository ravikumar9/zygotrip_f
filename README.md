# ZygoTrip — Production OTA Platform

A full-stack Online Travel Agency platform built with Django REST Framework (backend) and Next.js 14 (frontend). Designed to the same standard as Goibibo, MakeMyTrip, and Booking.com.

---

## Architecture

```
zygotrip/
├── backend/                    ← Django API backend
│   ├── apps/
│   │   ├── accounts/api/v1/    ← JWT auth endpoints
│   │   ├── booking/api/v1/     ← Booking lifecycle endpoints
│   │   ├── hotels/api/v1/      ← Property + availability endpoints
│   │   ├── wallet/api/v1/      ← Wallet + transactions endpoints
│   │   ├── pricing/            ← 13-step pricing engine
│   │   ├── rooms/              ← RoomType + RoomInventory
│   │   ├── payments/           ← Gateway webhook handler
│   │   └── promos/             ← Coupon system
│   ├── zygotrip_project/       ← Django settings + URL config
│   ├── manage.py
│   └── requirements.txt
├── frontend/                   ← Next.js 14 App Router frontend
│   ├── app/                    ← Pages (hotels, booking, wallet, account)
│   ├── components/             ← React UI components
│   ├── services/               ← API client (axios + JWT interceptors)
│   ├── hooks/                  ← React Query data hooks
│   └── types/                  ← TypeScript interfaces
├── deployment/
│   ├── docker/                 ← Dockerfiles + docker-compose.prod.yml
│   ├── nginx/                  ← nginx reverse proxy config
│   └── scripts/                ← entrypoint.sh, wait-for-it.sh
└── .env.example                ← Environment variable template
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register/` | Create account + JWT tokens |
| POST | `/api/v1/auth/login/` | Login + JWT tokens |
| POST | `/api/v1/auth/token/refresh/` | Refresh access token |
| GET/PUT | `/api/v1/users/me/` | Profile management |
| GET | `/api/v1/properties/` | Hotel listing (filterable, paginated) |
| GET | `/api/v1/properties/<slug>/` | Hotel detail |
| GET | `/api/v1/properties/<id>/availability/` | Room availability by date range |
| POST | `/api/v1/pricing/quote/` | Full itemized price breakdown |
| POST | `/api/v1/booking/context/` | Create price-locked booking session |
| GET | `/api/v1/booking/context/<id>/` | Retrieve booking context |
| POST | `/api/v1/booking/` | Confirm booking (atomic, inventory-locked) |
| GET | `/api/v1/booking/my/` | User's booking history |
| GET | `/api/v1/booking/<uuid>/` | Booking detail |
| POST | `/api/v1/booking/<uuid>/cancel/` | Cancel booking |
| GET | `/api/v1/wallet/` | Wallet balance |
| GET | `/api/v1/wallet/transactions/` | Transaction history |
| POST | `/api/v1/wallet/topup/` | Add funds to wallet |

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Backend

```bash
cd backend
pip install -r requirements.txt

# Set environment variables (copy .env.example → .env)
export DJANGO_SECRET_KEY=dev-secret-key
export POSTGRES_PASSWORD=postgres
export DEBUG=true

python manage.py migrate
python manage.py seed_roles_and_users   # creates demo users
python manage.py seed_ota_data          # seeds demo hotels
python manage.py runserver
```

Backend runs at: http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:3000

The Next.js dev server proxies `/api/v1/*` → Django at `http://localhost:8000`.

---

## Production Deployment

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your production values

# 2. Build and start all services
docker-compose -f deployment/docker/docker-compose.prod.yml up -d --build

# Services started:
# - postgres:5432   (PostgreSQL 15)
# - redis:6379      (Redis 7, persistent)
# - backend:8000    (Django + Gunicorn, 4 workers)
# - celery_worker   (4 concurrency, booking + settlement queues)
# - celery_beat     (scheduled tasks: hold expiry, reports)
# - frontend:3000   (Next.js standalone)
# - nginx:80/443    (reverse proxy + SSL)
```

### First deploy only:
The entrypoint script auto-runs `migrate`, `collectstatic`, and creates the superuser from `DJANGO_SUPERUSER_EMAIL` + `DJANGO_SUPERUSER_PASSWORD` env vars.

---

## Key Technical Decisions

| Decision | Implementation |
|----------|---------------|
| Booking atomicity | `select_for_update()` + DB transaction in `create_booking()` |
| Price locking | `BookingContext` with 30-minute TTL before booking confirmation |
| Inventory | `RoomInventory` per-date with DB-level non-negative constraint |
| Pricing | 13-step `PriceEngine` with demand multiplier + GST (5% ≤ ₹7500, 18% > ₹7500) |
| Settlement | `SettlementService` gated on `CHECKED_OUT` status only |
| JWT | 12-hour access + 30-day refresh, token rotation + blacklisting |
| Caching | Redis (5-min wallet balance, search results) with LocMemCache fallback |
| N+1 prevention | `ota_visible_properties()` with `select_related` + `prefetch_related` + `min_room_price` annotation |
| Frontend state | React Query (server state) + in-memory JWT (XSS-safe) |
| Frontend rendering | Server Components for listing (SEO), Client Components for booking flow |

---

## Booking State Machine

```
INITIATED → HOLD → PAYMENT_PENDING → CONFIRMED → CHECKED_IN → CHECKED_OUT → SETTLED
                ↘               ↘             ↘           ↘
              CANCELLED       FAILED        CANCELLED   REFUND_PENDING → REFUNDED
```
