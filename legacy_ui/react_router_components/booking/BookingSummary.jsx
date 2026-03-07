import { Link } from 'react-router-dom'
import PriceBreakdown from './PriceBreakdown'
import styles from './BookingSummary.module.css'

const STATUS_CONFIG = {
  hold: { label: 'Hold', color: '#f39c12' },
  payment_pending: { label: 'Payment Pending', color: '#e67e22' },
  confirmed: { label: 'Confirmed', color: '#27ae60' },
  cancelled: { label: 'Cancelled', color: '#e74c3c' },
  refund_pending: { label: 'Refund Pending', color: '#8e44ad' },
  refunded: { label: 'Refunded', color: '#16a085' },
  checked_in: { label: 'Checked In', color: '#2980b9' },
  checked_out: { label: 'Checked Out', color: '#7f8c8d' },
  settled: { label: 'Settled', color: '#27ae60' },
}

function fmt(amount) {
  if (!amount) return '₹0'
  return `₹${Number(amount).toLocaleString('en-IN')}`
}

/**
 * BookingSummary – full booking detail card as returned by the API.
 *
 * Props:
 *   booking: BookingSerializer output from /api/v1/bookings/<uuid>/
 */
export default function BookingSummary({ booking }) {
  if (!booking) return null

  const {
    public_booking_id, property_name, property_city, check_in, check_out,
    nights, status, status_display, total_amount, guest_name, guest_email,
    guest_phone, rooms, guests, price_breakdown, hold_expires_at,
    timer_seconds_remaining, promo_code,
  } = booking

  const statusCfg = STATUS_CONFIG[status] || { label: status_display || status, color: '#7f8c8d' }

  return (
    <div className={styles.wrapper}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <p className={styles.bookingId}>{public_booking_id}</p>
          <h2 className={styles.propertyName}>{property_name}</h2>
          <p className={styles.city}>{property_city}</p>
        </div>
        <span className={styles.statusBadge} style={{ background: statusCfg.color }}>
          {statusCfg.label}
        </span>
      </div>

      {/* Dates */}
      <div className={styles.datesRow}>
        <div className={styles.dateBlock}>
          <span className={styles.dateLabel}>Check-in</span>
          <span className={styles.dateValue}>{check_in}</span>
        </div>
        <div className={styles.nights}>{nights} night{nights !== 1 ? 's' : ''}</div>
        <div className={styles.dateBlock}>
          <span className={styles.dateLabel}>Check-out</span>
          <span className={styles.dateValue}>{check_out}</span>
        </div>
      </div>

      {/* Hold timer */}
      {status === 'hold' && timer_seconds_remaining > 0 && (
        <div className={styles.timerBox}>
          Complete payment within{' '}
          <strong>{Math.floor(timer_seconds_remaining / 60)}m {timer_seconds_remaining % 60}s</strong>{' '}
          or the booking will expire.
        </div>
      )}

      {/* Guest */}
      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>Guest Details</h4>
        <p className={styles.infoRow}><span>Name</span><strong>{guest_name}</strong></p>
        {guest_email && <p className={styles.infoRow}><span>Email</span><strong>{guest_email}</strong></p>}
        {guest_phone && <p className={styles.infoRow}><span>Phone</span><strong>{guest_phone}</strong></p>}
      </section>

      {/* Rooms */}
      {rooms && rooms.length > 0 && (
        <section className={styles.section}>
          <h4 className={styles.sectionTitle}>Rooms</h4>
          {rooms.map((r) => (
            <p key={r.id} className={styles.infoRow}>
              <span>{r.room_type_name}</span>
              <strong>{r.quantity} × {r.bed_type}{r.meal_plan ? ` (${r.meal_plan})` : ''}</strong>
            </p>
          ))}
        </section>
      )}

      {/* Promo */}
      {promo_code && (
        <section className={styles.section}>
          <p className={styles.promoTag}>Promo applied: <strong>{promo_code}</strong></p>
        </section>
      )}

      {/* Price breakdown */}
      {price_breakdown && (
        <PriceBreakdown
          breakdown={price_breakdown}
          nights={nights}
          rooms={rooms?.reduce((s, r) => s + (r.quantity || 1), 0) || 1}
        />
      )}

      {/* Total fallback */}
      {!price_breakdown && (
        <div className={styles.totalRow}>
          <span>Total</span>
          <strong className={styles.totalAmount}>{fmt(total_amount)}</strong>
        </div>
      )}
    </div>
  )
}
