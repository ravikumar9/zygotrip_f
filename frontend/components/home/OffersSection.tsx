'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import CopyBtn from '@/components/ui/CopyBtn';
import { fetchFeaturedOffers, type FeaturedOffer } from '@/services/offers';

interface DisplayOffer {
  title: string;
  subtitle: string;
  code: string;
  gradient: string;
  emoji: string;
  tag: string;
}

const GRADIENTS = [
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
];

const EMOJI_MAP: Record<string, string> = {
  percentage: '🏷️',
  flat: '💰',
  bogo: '🎁',
  bundle: '📦',
};

/** Fallback offers when backend is unreachable */
const FALLBACK: DisplayOffer[] = [
  { title: 'Save on Your Next Stay', subtitle: 'Valid on prepaid bookings', code: 'ZYGO20', gradient: GRADIENTS[0], emoji: '🏨', tag: 'Hotels' },
  { title: 'Wallet Cashback', subtitle: 'Use ZygoWallet on checkout', code: 'WALLET500', gradient: GRADIENTS[1], emoji: '💳', tag: 'Cashback' },
  { title: 'Weekend Getaway', subtitle: 'Weekend specials available', code: 'WEEKEND15', gradient: GRADIENTS[2], emoji: '🌴', tag: 'Weekends' },
  { title: 'First Booking Bonus', subtitle: 'Flat ₹300 off for new users', code: 'FIRST300', gradient: GRADIENTS[3], emoji: '🎉', tag: 'New User' },
];

function mapApiOffer(offer: FeaturedOffer, idx: number): DisplayOffer {
  return {
    title: offer.title,
    subtitle: offer.description || `Use code ${offer.coupon_code}`,
    code: offer.coupon_code,
    gradient: GRADIENTS[idx % GRADIENTS.length],
    emoji: EMOJI_MAP[offer.offer_type] || '🏨',
    tag: offer.offer_type === 'percentage'
      ? `${parseFloat(offer.discount_percentage)}% Off`
      : offer.offer_type === 'flat'
        ? `₹${parseFloat(offer.discount_flat)} Off`
        : 'Deal',
  };
}

export default function OffersSection() {
  const [offers, setOffers] = useState<DisplayOffer[]>(FALLBACK);

  useEffect(() => {
    fetchFeaturedOffers().then(apiOffers => {
      if (apiOffers.length > 0) {
        setOffers(apiOffers.slice(0, 4).map(mapApiOffer));
      }
    });
  }, []);

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex items-end justify-between mb-5">
        <div>
          <h2 className="text-xl font-black text-neutral-900 font-heading">
            Top Offers for You
          </h2>
          <p className="text-xs text-neutral-400 mt-0.5">
            Personalised deals · Updated daily
          </p>
        </div>
        <Link
          href="/hotels"
          className="text-xs font-bold hover:underline"
          style={{ color: 'var(--primary)' }}
        >
          View all →
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {offers.map((offer) => (
          <div
            key={offer.code}
            className="bg-white/80 rounded-2xl border border-neutral-100 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all overflow-hidden"
          >
            {/* Gradient banner */}
            <div
              className="h-24 flex items-center justify-center text-5xl"
              style={{ background: offer.gradient }}
            >
              {offer.emoji}
            </div>

            <div className="p-4">
              <span className="offer-tag mb-2 inline-block">{offer.tag}</span>
              <h3 className="font-black text-neutral-900 text-sm leading-tight mb-1">
                {offer.title}
              </h3>
              <p className="text-xs text-neutral-400 mb-3">{offer.subtitle}</p>

              <div className="flex items-center justify-between">
                <CopyBtn code={offer.code} />
                <span className="text-xs text-neutral-300">tap to copy</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
