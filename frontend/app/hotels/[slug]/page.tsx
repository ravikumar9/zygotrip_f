import type { Metadata } from 'next';
import HotelDetailClient from './HotelDetailClient';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

interface HotelMeta {
  name: string;
  city: string;
  state: string;
  description: string;
  star_rating: number;
  cover_image: string;
  slug: string;
}

async function fetchHotelMeta(slug: string): Promise<HotelMeta | null> {
  try {
    const res = await fetch(`${API_BASE}/properties/${slug}/`, {
      next: { revalidate: 3600 }, // ISR: revalidate every hour
    });
    if (!res.ok) return null;
    const json = await res.json();
    const data = json?.data ?? json;
    return {
      name: data?.name || '',
      city: data?.city || '',
      state: data?.state || '',
      description: data?.description || '',
      star_rating: data?.star_rating || 0,
      cover_image: data?.cover_image || data?.images?.[0]?.url || '',
      slug: data?.slug || slug,
    };
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const hotel = await fetchHotelMeta(params.slug);

  if (!hotel) {
    return {
      title: 'Hotel Not Found',
      description: 'The requested hotel could not be found.',
    };
  }

  const title = `${hotel.name} — ${hotel.city} | Book Now on ZygoTrip`;
  const description =
    hotel.description?.slice(0, 160) ||
    `Book ${hotel.name} in ${hotel.city}, ${hotel.state}. ${hotel.star_rating}★ rated. Best prices, free cancellation & instant confirmation on ZygoTrip.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: 'website',
      siteName: 'ZygoTrip',
      locale: 'en_IN',
      images: hotel.cover_image
        ? [{ url: hotel.cover_image, width: 1200, height: 630, alt: hotel.name }]
        : [],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: hotel.cover_image ? [hotel.cover_image] : [],
    },
    alternates: {
      canonical: `/hotels/${hotel.slug}`,
    },
  };
}

export default function PropertyDetailPage() {
  return <HotelDetailClient />;
}
