import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import PropertyGallery from '../components/property/PropertyGallery'
import { getPropertyDetails } from '../services/api'
import styles from './DetailsPage.module.css'

const RATING_TIER_LABEL = {
  excellent: 'Excellent',
  good: 'Good',
  average: 'Average',
  below_average: 'Fair',
}

export default function DetailsPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [property, setProperty] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Booking params (passed to BookingPage via URL)
  const [checkin, setCheckin] = useState('')
  const [checkout, setCheckout] = useState('')
  const [adults, setAdults] = useState(2)
  const [selectedRoom, setSelectedRoom] = useState(null)

  useEffect(() => {
    setLoading(true)
    getPropertyDetails(id)
      .then((data) => {
        setProperty(data)
        if (data.room_types?.length) setSelectedRoom(data.room_types[0])
      })
      .catch((err) => setError(err.message || 'Failed to load property.'))
      .finally(() => setLoading(false))
  }, [id])

  function handleBookNow(e) {
    e.preventDefault()
    if (!selectedRoom) return
    const params = new URLSearchParams({
      room_type_id: selectedRoom.id,
      checkin,
      checkout,
      adults,
    })
    navigate(`/hotels/${id}/book?${params.toString()}`)
  }

  if (loading) return <div className={styles.loading}>Loading property…</div>
  if (error) return <div className={styles.error}>{error} <Link to="/">← Back</Link></div>
  if (!property) return null

  const {
    name, city_name, locality_name, area, landmark, address,
    rating, review_count, star_category, rating_tier,
    has_free_cancellation, cancellation_hours,
    is_trending, bookings_today,
    description, images, amenities, room_types,
  } = property

  const tierLabel = RATING_TIER_LABEL[rating_tier] || 'Good'

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <nav className={styles.breadcrumb}>
        <Link to="/">Hotels</Link>
        <span>›</span>
        <span>{city_name}</span>
        <span>›</span>
        <span>{name}</span>
      </nav>

      <div className={styles.layout}>
        {/* Left column */}
        <div className={styles.leftCol}>
          {/* Gallery */}
          <PropertyGallery images={images} propertyName={name} />

          {/* Header */}
          <div className={styles.propertyHeader}>
            <div>
              <h1 className={styles.propertyName}>{name}</h1>
              <p className={styles.location}>
                {area && `${area}, `}
                {locality_name && `${locality_name}, `}
                {city_name}
              </p>
              {landmark && <p className={styles.landmark}>{landmark}</p>}
              <p className={styles.address}>{address}</p>
              <p className={styles.stars}>
                {'★'.repeat(star_category)}{'☆'.repeat(5 - star_category)}
                <span className={styles.starLabel}> {star_category}-Star</span>
              </p>
            </div>
            <div className={styles.ratingBlock}>
              <span className={styles.ratingScore}>{Number(rating).toFixed(1)}</span>
              <span className={styles.ratingLabel}>{tierLabel}</span>
              {review_count > 0 && (
                <span className={styles.reviewCount}>{review_count.toLocaleString()} reviews</span>
              )}
            </div>
          </div>

          {/* Trust signals */}
          <div className={styles.signalsRow}>
            {has_free_cancellation && (
              <span className={styles.signal}>✓ Free Cancellation (within {cancellation_hours}h)</span>
            )}
            {is_trending && <span className={styles.signal}>🔥 Trending</span>}
            {bookings_today > 0 && (
              <span className={styles.signal}>{bookings_today} bookings today</span>
            )}
          </div>

          {/* Amenities */}
          {amenities?.length > 0 && (
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>Amenities</h2>
              <ul className={styles.amenityList}>
                {amenities.map((a) => (
                  <li key={a.name} className={styles.amenityItem}>
                    {a.icon && <span className={styles.amenityIcon}>{a.icon}</span>}
                    {a.name}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Description */}
          {description && (
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>About the Property</h2>
              <p className={styles.description}>{description}</p>
            </section>
          )}

          {/* Room Types */}
          {room_types?.length > 0 && (
            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>Available Rooms</h2>
              <div className={styles.roomList}>
                {room_types.map((room) => (
                  <div
                    key={room.id}
                    className={`${styles.roomCard} ${selectedRoom?.id === room.id ? styles.roomSelected : ''}`}
                    onClick={() => setSelectedRoom(room)}
                  >
                    <div className={styles.roomInfo}>
                      <h3 className={styles.roomName}>{room.name}</h3>
                      <p className={styles.roomMeta}>
                        {room.bed_type && `${room.bed_type} · `}
                        Sleeps {room.capacity}
                        {room.meal_plan ? ` · ${room.meal_plan}` : ''}
                      </p>
                      {room.description && (
                        <p className={styles.roomDesc}>{room.description}</p>
                      )}
                    </div>
                    <div className={styles.roomPriceBlock}>
                      <span className={styles.roomPrice}>
                        ₹{Number(room.base_price).toLocaleString()}
                      </span>
                      <span className={styles.roomPerNight}>/night</span>
                      {selectedRoom?.id === room.id && (
                        <span className={styles.selectedLabel}>Selected</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right column: booking widget */}
        <aside className={styles.bookingWidget}>
          <div className={styles.widgetCard}>
            <h3 className={styles.widgetTitle}>Book This Property</h3>

            {selectedRoom && (
              <div className={styles.widgetRoom}>
                <span>{selectedRoom.name}</span>
                <strong>₹{Number(selectedRoom.base_price).toLocaleString()}/night</strong>
              </div>
            )}

            <form className={styles.widgetForm} onSubmit={handleBookNow}>
              <label className={styles.fieldLabel}>
                Check-in
                <input
                  type="date"
                  required
                  value={checkin}
                  min={new Date().toISOString().split('T')[0]}
                  onChange={(e) => setCheckin(e.target.value)}
                  className={styles.fieldInput}
                />
              </label>

              <label className={styles.fieldLabel}>
                Check-out
                <input
                  type="date"
                  required
                  value={checkout}
                  min={checkin || new Date().toISOString().split('T')[0]}
                  onChange={(e) => setCheckout(e.target.value)}
                  className={styles.fieldInput}
                />
              </label>

              <label className={styles.fieldLabel}>
                Adults
                <select
                  value={adults}
                  onChange={(e) => setAdults(Number(e.target.value))}
                  className={styles.fieldInput}
                >
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>{n} Adult{n > 1 ? 's' : ''}</option>
                  ))}
                </select>
              </label>

              <button
                type="submit"
                className={styles.bookBtn}
                disabled={!selectedRoom}
              >
                Book Now
              </button>
            </form>

            {has_free_cancellation && (
              <p className={styles.widgetCancelNote}>
                ✓ Free cancellation available
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
