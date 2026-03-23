'use client';

import { useState } from 'react';
import { Star, ThumbsUp, User, Camera, Send, Loader2 } from 'lucide-react';
import api from '@/services/api';
import toast from 'react-hot-toast';
import { format, parseISO } from 'date-fns';
import { ReviewShareButton } from '@/components/social/ShareButton';

interface Review {
  id: number;
  user_name: string;
  rating: number;
  title: string;
  comment: string;
  travel_type?: string;
  stayed_date?: string;
  helpful_count: number;
  photos?: string[];
  created_at: string;
  ratings?: {
    cleanliness?: number;
    service?: number;
    location?: number;
    amenities?: number;
    value_for_money?: number;
  };
}

interface ReviewSectionProps {
  propertyId: number;
  propertySlug: string;
  propertyName: string;
  overallRating: number;
  reviewCount: number;
  ratingBreakdown?: {
    cleanliness: string;
    service: string;
    location: string;
    amenities: string;
    value_for_money: string;
    total_reviews: number;
  };
}

function RatingBar({ label, value, max = 5 }: { label: string; value: number; max?: number }) {
  const pct = (value / max) * 100;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-neutral-500 w-28 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: pct >= 80 ? '#22c55e' : pct >= 60 ? '#eab308' : '#ef4444',
          }}
        />
      </div>
      <span className="text-xs font-bold text-neutral-700 w-8 text-right">{value.toFixed(1)}</span>
    </div>
  );
}

function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hover, setHover] = useState(0);

  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          type="button"
          onClick={() => onChange(i)}
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(0)}
          className="p-0.5 transition-transform hover:scale-110"
        >
          <Star
            size={24}
            fill={(hover || value) >= i ? '#f59e0b' : 'none'}
            stroke={(hover || value) >= i ? '#f59e0b' : '#d1d5db'}
            strokeWidth={1.5}
          />
        </button>
      ))}
      {value > 0 && (
        <span className="text-sm font-semibold text-neutral-600 ml-2">
          {value === 5 ? 'Excellent' : value === 4 ? 'Very Good' : value === 3 ? 'Good' : value === 2 ? 'Fair' : 'Poor'}
        </span>
      )}
    </div>
  );
}

function ReviewCard({ review }: { review: Review }) {
  const [helpful, setHelpful] = useState(false);

  return (
    <div className="bg-white/80 rounded-xl border border-neutral-100 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
            <User size={18} className="text-primary-600" />
          </div>
          <div>
            <p className="font-semibold text-neutral-800 text-sm">{review.user_name}</p>
            <div className="flex items-center gap-2 text-xs text-neutral-400">
              {review.travel_type && <span>{review.travel_type}</span>}
              {review.stayed_date && (
                <span>Stayed {format(parseISO(review.stayed_date), 'MMM yyyy')}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 bg-green-600 text-white px-2 py-1 rounded-lg">
          <Star size={11} fill="white" stroke="none" />
          <span className="text-xs font-bold">{review.rating.toFixed(1)}</span>
        </div>
      </div>

      {review.title && (
        <h4 className="font-semibold text-neutral-800 text-sm mb-1">{review.title}</h4>
      )}
      <p className="text-sm text-neutral-600 leading-relaxed mb-3">{review.comment}</p>

      {review.ratings && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 mb-3">
          {Object.entries(review.ratings).map(([key, val]) => (
            <div key={key} className="flex items-center gap-1.5 text-xs">
              <span className="text-neutral-400 capitalize">{key.replace(/_/g, ' ')}</span>
              <span className="font-semibold text-neutral-700">{val}/5</span>
            </div>
          ))}
        </div>
      )}

      {review.photos && review.photos.length > 0 && (
        <div className="flex gap-2 mb-3 overflow-x-auto">
          {review.photos.map((url, i) => (
            <img key={i} src={url} alt="Review photo" className="w-20 h-20 rounded-lg object-cover" />
          ))}
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-neutral-50">
        <span className="text-xs text-neutral-400">
          {format(parseISO(review.created_at), 'd MMM yyyy')}
        </span>
        <button
          onClick={() => setHelpful(!helpful)}
          className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg transition-colors ${
            helpful ? 'bg-blue-50 text-blue-600' : 'text-neutral-400 hover:bg-page'
          }`}
        >
          <ThumbsUp size={12} /> Helpful ({review.helpful_count + (helpful ? 1 : 0)})
        </button>
      </div>
    </div>
  );
}

export default function ReviewSection({
  propertyId,
  propertySlug,
  propertyName,
  overallRating,
  reviewCount,
  ratingBreakdown,
}: ReviewSectionProps) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [formRating, setFormRating] = useState(0);
  const [formTitle, setFormTitle] = useState('');
  const [formComment, setFormComment] = useState('');
  const [formTravelType, setFormTravelType] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Sub-ratings
  const [subRatings, setSubRatings] = useState({
    cleanliness: 0, service: 0, location: 0, amenities: 0, value_for_money: 0,
  });

  const loadReviews = async () => {
    if (loaded) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/properties/${propertySlug}/reviews/`);
      setReviews(data.results || data || []);
      setLoaded(true);
    } catch {
      toast.error('Could not load reviews');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formRating === 0) {
      toast.error('Please select a rating');
      return;
    }
    if (!formComment.trim()) {
      toast.error('Please write a review');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/properties/${propertyId}/reviews/`, {
        rating: formRating,
        title: formTitle,
        comment: formComment,
        travel_type: formTravelType || undefined,
        ratings: Object.values(subRatings).some(v => v > 0) ? subRatings : undefined,
      });
      toast.success('Review submitted! It will appear after moderation.');
      setShowForm(false);
      setFormRating(0);
      setFormTitle('');
      setFormComment('');
      setFormTravelType('');
      setSubRatings({ cleanliness: 0, service: 0, location: 0, amenities: 0, value_for_money: 0 });
      setLoaded(false); // Reload
    } catch {
      toast.error('Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div id="guest-reviews" className="bg-white/80 rounded-2xl shadow-card p-6">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-bold text-neutral-900 font-heading">Guest Reviews</h3>
        <div className="flex items-center gap-2">
          <ReviewShareButton
            propertyName={propertyName}
            slug={propertySlug}
            rating={overallRating}
          />
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-1.5 text-xs font-semibold text-primary-600 bg-primary-50 hover:bg-primary-100 px-3 py-2 rounded-lg border border-primary-200 transition-colors"
          >
            <Star size={12} /> Write a Review
          </button>
        </div>
      </div>

      {/* Overall rating + breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-6 mb-6 pb-6 border-b border-neutral-100">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-green-600 text-white mb-2">
            <span className="text-3xl font-black">{overallRating.toFixed(1)}</span>
          </div>
          <p className="text-sm font-semibold text-neutral-700">
            {overallRating >= 4.5 ? 'Exceptional' : overallRating >= 4 ? 'Excellent' : overallRating >= 3.5 ? 'Very Good' : overallRating >= 3 ? 'Good' : 'Average'}
          </p>
          <p className="text-xs text-neutral-400">{reviewCount} reviews</p>
        </div>

        {ratingBreakdown && (
          <div className="space-y-2.5">
            <RatingBar label="Cleanliness" value={parseFloat(ratingBreakdown.cleanliness)} />
            <RatingBar label="Service" value={parseFloat(ratingBreakdown.service)} />
            <RatingBar label="Location" value={parseFloat(ratingBreakdown.location)} />
            <RatingBar label="Amenities" value={parseFloat(ratingBreakdown.amenities)} />
            <RatingBar label="Value for Money" value={parseFloat(ratingBreakdown.value_for_money)} />
          </div>
        )}
      </div>

      {/* Write review form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-page rounded-xl p-5 mb-6 border border-neutral-200">
          <h4 className="font-semibold text-neutral-800 text-sm mb-4">Share your experience</h4>

          <div className="mb-4">
            <label className="text-xs font-semibold text-neutral-500 block mb-1.5">Overall Rating *</label>
            <StarInput value={formRating} onChange={setFormRating} />
          </div>

          {/* Sub-ratings */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            {(['cleanliness', 'service', 'location', 'amenities', 'value_for_money'] as const).map((key) => (
              <div key={key}>
                <label className="text-xs text-neutral-500 capitalize block mb-1">{key.replace(/_/g, ' ')}</label>
                <div className="flex gap-0.5">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setSubRatings(prev => ({ ...prev, [key]: i }))}
                      className="p-0.5"
                    >
                      <Star
                        size={14}
                        fill={subRatings[key] >= i ? '#f59e0b' : 'none'}
                        stroke={subRatings[key] >= i ? '#f59e0b' : '#d1d5db'}
                      />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mb-3">
            <label className="text-xs font-semibold text-neutral-500 block mb-1">Travel Type</label>
            <div className="flex gap-2 flex-wrap">
              {['Business', 'Couple', 'Family', 'Friends', 'Solo'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setFormTravelType(formTravelType === t ? '' : t)}
                  className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-all ${
                    formTravelType === t
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white/80 text-neutral-600 border-neutral-200 hover:border-primary-300'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-3">
            <label className="text-xs font-semibold text-neutral-500 block mb-1">Review Title</label>
            <input
              type="text"
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              placeholder="Summarize your stay in a few words"
              className="w-full px-3 py-2.5 rounded-lg border border-neutral-200 text-sm focus:outline-none focus:border-primary-400"
              maxLength={100}
            />
          </div>

          <div className="mb-4">
            <label className="text-xs font-semibold text-neutral-500 block mb-1">Your Review *</label>
            <textarea
              value={formComment}
              onChange={(e) => setFormComment(e.target.value)}
              placeholder="What did you like? What could be improved?"
              className="w-full px-3 py-2.5 rounded-lg border border-neutral-200 text-sm focus:outline-none focus:border-primary-400 min-h-[100px] resize-y"
              maxLength={2000}
            />
            <p className="text-xs text-neutral-400 mt-1 text-right">{formComment.length}/2000</p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2"
            >
              {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              {submitting ? 'Submitting...' : 'Submit Review'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="text-sm text-neutral-500 hover:text-neutral-700"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Reviews list */}
      {!loaded && !loading && (
        <button
          onClick={loadReviews}
          className="w-full py-3 text-sm font-semibold text-primary-600 bg-primary-50 hover:bg-primary-100 rounded-xl transition-colors"
        >
          Load {reviewCount} Reviews
        </button>
      )}

      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={24} className="animate-spin text-neutral-400" />
        </div>
      )}

      {loaded && reviews.length > 0 && (
        <div className="space-y-4">
          {reviews.map((review) => (
            <ReviewCard key={review.id} review={review} />
          ))}
        </div>
      )}

      {loaded && reviews.length === 0 && (
        <p className="text-center text-neutral-400 text-sm py-6">
          No reviews yet. Be the first to share your experience!
        </p>
      )}
    </div>
  );
}
