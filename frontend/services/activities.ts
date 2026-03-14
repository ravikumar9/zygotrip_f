import api from './api';
import type { ActivitySearchParams, ActivitySearchResult, Activity, ActivityTimeSlot } from '@/types/activities';

function normalizeActivity(activity: any): Activity {
  return {
    id: activity.id,
    slug: activity.slug,
    name: activity.name || activity.title || '',
    category: activity.category?.name || activity.category || '',
    city: activity.city || '',
    country: activity.country || '',
    description: activity.description || '',
    short_description: activity.short_description || '',
    primary_image: activity.primary_image || activity.images?.[0]?.image || activity.images?.[0]?.url,
    images: (activity.images || []).map((image: any) => ({
      url: image.url || image.image || '',
      caption: image.caption || '',
    })),
    duration_hours: activity.duration_hours,
    duration_display: activity.duration_display || '',
    price_adult: activity.price_adult ?? activity.adult_price ?? 0,
    price_child: activity.price_child ?? activity.child_price ?? 0,
    currency: activity.currency || 'INR',
    rating: activity.rating ?? activity.avg_rating ?? 0,
    review_count: activity.review_count ?? 0,
    max_participants: activity.max_participants,
    is_instant_confirm: activity.is_instant_confirm ?? activity.is_instant_confirmation ?? false,
    is_free_cancellation: activity.is_free_cancellation ?? false,
    cancellation_hours: activity.cancellation_hours ?? 0,
    highlights: activity.highlights || [],
    inclusions: activity.inclusions || activity.includes || [],
    exclusions: activity.exclusions || activity.excludes || [],
    meeting_point: activity.meeting_point || activity.address,
    latitude: activity.latitude,
    longitude: activity.longitude,
    available_languages: activity.available_languages || activity.languages || [],
    supplier: activity.supplier || '',
  };
}

export async function searchActivities(params: ActivitySearchParams): Promise<ActivitySearchResult> {
  const { data } = await api.get('/activities/search/', { params });
  return {
    results: (data.results || []).map(normalizeActivity),
    filters: data.filters || { categories: [], price_range: { min: 0, max: 0 }, durations: [] },
    total: data.total || (data.results || []).length,
    page: data.page || 1,
    total_pages: data.total_pages || 1,
  };
}

export async function getActivityDetail(slug: string): Promise<Activity> {
  const { data } = await api.get(`/activities/detail/${slug}/`);
  return normalizeActivity(data);
}

export async function getActivityTimeSlots(activityId: number, date: string): Promise<ActivityTimeSlot[]> {
  const { data } = await api.get(`/activities/${activityId}/slots/`, { params: { date } });
  return (data.slots || []).map((slot: any) => ({
    id: slot.id,
    start_time: slot.start_time,
    end_time: slot.end_time,
    remaining_seats: slot.available_spots ?? Math.max((slot.max_capacity || 0) - (slot.booked_count || 0), 0),
    price_adult: slot.price_adult ?? slot.effective_price ?? 0,
    price_child: slot.price_child ?? 0,
  }));
}

export async function getPopularActivities(city?: string): Promise<Activity[]> {
  if (!city) return [];
  const results = await searchActivities({ city, sort: 'popular' });
  return results.results.slice(0, 8);
}

export async function getActivityCategories(): Promise<{ value: string; label: string; count: number }[]> {
  const { data } = await api.get('/activities/categories/');
  return (data.categories || []).map((category: { slug?: string; name: string; activity_count?: number }) => ({
    value: category.slug || category.name,
    label: category.name,
    count: category.activity_count || 0,
  }));
}
