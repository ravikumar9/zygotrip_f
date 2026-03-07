import styles from './PriceBreakdown.module.css'

function Row({ label, value, highlight, discount }) {
  return (
    <div className={`${styles.row} ${highlight ? styles.highlight : ''} ${discount ? styles.discount : ''}`}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </div>
  )
}

function fmt(amount) {
  if (amount === undefined || amount === null) return '₹0'
  return `₹${Number(amount).toLocaleString('en-IN')}`
}

/**
 * PriceBreakdown – renders a full Goibibo-style price breakdown card.
 *
 * Props:
 *   breakdown: { base_amount, gst, service_fee, promo_discount, total_amount, meal_amount? }
 *   nights:    integer
 *   rooms:     integer
 */
export default function PriceBreakdown({ breakdown, nights = 1, rooms = 1 }) {
  if (!breakdown) return null

  const {
    base_amount,
    meal_amount,
    service_fee,
    gst,
    promo_discount,
    total_amount,
  } = breakdown

  const hasDiscount = Number(promo_discount) > 0
  const hasMeal = Number(meal_amount) > 0

  return (
    <div className={styles.card}>
      <h3 className={styles.title}>Price Breakdown</h3>

      <Row
        label={`Room charges (${nights} night${nights !== 1 ? 's' : ''} × ${rooms} room${rooms !== 1 ? 's' : ''})`}
        value={fmt(base_amount)}
      />

      {hasMeal && (
        <Row label="Meal charges" value={fmt(meal_amount)} />
      )}

      {Number(service_fee) > 0 && (
        <Row label="Service fee" value={fmt(service_fee)} />
      )}

      {Number(gst) > 0 && (
        <Row label="Taxes & GST (18%)" value={fmt(gst)} />
      )}

      {hasDiscount && (
        <Row
          label="Promo discount"
          value={`−${fmt(promo_discount)}`}
          discount
        />
      )}

      <div className={styles.divider} />

      <Row
        label="Total Amount"
        value={fmt(total_amount)}
        highlight
      />

      <p className={styles.note}>* Inclusive of all taxes</p>
    </div>
  )
}
