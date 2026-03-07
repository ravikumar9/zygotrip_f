# DEPRECATED — Legacy UI Components

**Moved on:** 2026-03-05  
**Reason:** OTA UI architecture migration to React/Next.js

## What's Here

This directory contains legacy UI code that has been superseded by the
production React/Next.js component system in `frontend/`.

### `react_router_components/`
React Router-based JSX components + CSS modules. These used `react-router-dom`
and were part of an earlier SPA architecture. Replaced by Next.js App Router
equivalents.

| Legacy File | Replaced By |
|---|---|
| `property/PropertyCard.jsx` | `frontend/components/hotels/HotelCard.tsx` |
| `property/PropertyFilters.jsx` | `frontend/components/filters/FilterSidebar.tsx` |
| `property/PropertyGallery.jsx` | `frontend/components/hotels/HotelGallery.tsx` |
| `booking/BookingSummary.jsx` | `frontend/components/booking/BookingSummary.tsx` |
| `booking/PriceBreakdown.jsx` | `frontend/components/booking/PriceBreakdown.tsx` |

### `react_router_pages/`
Legacy page-level components using `react-router-dom`.

| Legacy File | Replaced By |
|---|---|
| `ListingPage.jsx` | `frontend/app/hotels/HotelListingPage.tsx` |
| `DetailsPage.jsx` | `frontend/app/hotels/[slug]/page.tsx` |

### `django_templates/`
Django template partials that rendered OTA UI server-side. The OTA frontend
is now fully controlled by Next.js; these templates are retained for reference
only.

### `static_js/`
Vanilla JS scripts that handled search, filters, hotel interactions.
All functionality is now in React components with proper state management.

### `static_css/`
CSS files that styled Django-rendered OTA pages. Styling is now managed
via Tailwind CSS in the Next.js frontend.

## Safe to Delete?

These files can be safely deleted after confirming:
1. All production pages render correctly from Next.js
2. No Django views reference the moved templates
3. E2E tests pass without these files

**Do NOT delete until production migration is verified.**
