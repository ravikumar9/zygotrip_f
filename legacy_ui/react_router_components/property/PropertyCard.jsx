import { Link } from 'react-router-dom'
import styles from './PropertyCard.module.css'

const RATING_LABELS = {
  excellent: { label: 'Excellent', color: '#27ae60' },
  good: { label: 'Good', color: '#2ecc71' },
  average: { label: 'Average', color: '#f39c12' },
  below_average: { label: 'Fair', color: '#e74c3c' },
}

export default function PropertyCard({ property }) {
  const {
    id, slug, name, city_name, area, rating, review_count,
    star_category, min_price, primary_image, amenity_names,
    rating_tier, has_free_cancellation, is_trending, bookings_today,
  } = property

  const tier = RATING_LABELS[rating_tier] || RATING_LABELS.average
  const href = `/hotels/${slug || id}`

  return (
    <Link to={href} className={styles.card}>
      {/* Image */}
      <div className={styles.imageWrap}>
        {primary_image ? (
          <img src={primary_image} alt={name} className={styles.image} loading="lazy" />
        ) : (
          <div className={styles.imagePlaceholder}>
            <span>No Image</span>
          </div>
        )}
        {is_trending && <span className={styles.trendingBadge}>🔥 Trending</span>}
        {has_free_cancellation && (
          <span className={styles.cancelBadge}>Free Cancellation</span>
        )}
      </div>

      {/* Body */}
      <div className={styles.body}>
        <div className={styles.headerRow}>
          <h3 className={styles.name}>{name}</h3>
          <div className={styles.ratingBox} style={{ background: tier.color }}>
            {rating.toFixed(1)}
          </div>
        </div>

        <p className={styles.location}>
          {area ? `${area}, ` : ''}{city_name}
        </p>

        {/* Star category */}
        <p className={styles.stars}>
          {'★'.repeat(star_category)}{'☆'.repeat(5 - star_category)}
        </p>

        {/* Amenities (top 4) */}
        {amenity_names && amenity_names.length > 0 && (
          <ul className={styles.amenities}>
            {amenity_names.slice(0, 4).map((a) => (
              <li key={a} className={styles.amenityTag}>{a}</li>
            ))}
          </ul>
        )}

        {/* Reviews + signals */}
        <div className={styles.metaRow}>
          <span className={styles.tierLabel} style={{ color: tier.color }}>
            {tier.label}
          </span>
          {review_count > 0 && (
            <span className={styles.reviewCount}>{review_count.toLocaleString()} reviews</span>
          )}
          {bookings_today > 0 && (
            <span className={styles.bookingSignal}>
              {bookings_today} booked today
            </span>
          )}
        </div>

        {/* Price */}
        <div className={styles.priceRow}>
          <span className={styles.priceLabel}>From</span>
          <span className={styles.price}>
            ₹{min_price ? min_price.toLocaleString() : '—'}
          </span>
          <span className={styles.perNight}>/night</span>
        </div>
      </div>
    </Link>
  )
}
