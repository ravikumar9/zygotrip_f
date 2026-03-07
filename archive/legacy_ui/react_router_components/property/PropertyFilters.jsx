import { useState } from 'react'
import styles from './PropertyFilters.module.css'

const SORT_OPTIONS = [
  { value: 'popular', label: 'Most Popular' },
  { value: 'price_asc', label: 'Price: Low to High' },
  { value: 'price_desc', label: 'Price: High to Low' },
  { value: 'rating', label: 'Top Rated' },
  { value: 'newest', label: 'Newest First' },
]

const PROPERTY_TYPES = ['Hotel', 'Hostel', 'Villa', 'Resort', 'Apartment', 'Guesthouse']

const AMENITY_OPTIONS = [
  'WiFi', 'Pool', 'Parking', 'AC', 'Gym', 'Restaurant',
  'Bar', 'Spa', 'Pet Friendly', 'Room Service',
]

export default function PropertyFilters({ filters, onChange }) {
  const [localFilters, setLocalFilters] = useState({
    min_price: filters.min_price || '',
    max_price: filters.max_price || '',
    free_cancellation: filters.free_cancellation || false,
    sort: filters.sort || 'popular',
    property_type: filters.property_type || [],
    amenity: filters.amenity || [],
  })

  function update(key, value) {
    const updated = { ...localFilters, [key]: value }
    setLocalFilters(updated)
    onChange(updated)
  }

  function toggleArray(key, value) {
    const arr = localFilters[key] || []
    const updated = arr.includes(value)
      ? arr.filter((v) => v !== value)
      : [...arr, value]
    update(key, updated)
  }

  function clearAll() {
    const reset = {
      min_price: '', max_price: '', free_cancellation: false,
      sort: 'popular', property_type: [], amenity: [],
    }
    setLocalFilters(reset)
    onChange(reset)
  }

  const activeCount = [
    localFilters.min_price,
    localFilters.max_price,
    localFilters.free_cancellation,
    ...(localFilters.property_type || []),
    ...(localFilters.amenity || []),
  ].filter(Boolean).length

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <h3 className={styles.title}>Filters</h3>
        {activeCount > 0 && (
          <button className={styles.clearBtn} onClick={clearAll}>
            Clear all ({activeCount})
          </button>
        )}
      </div>

      {/* Sort */}
      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>Sort By</h4>
        <div className={styles.radioGroup}>
          {SORT_OPTIONS.map((opt) => (
            <label key={opt.value} className={styles.radioLabel}>
              <input
                type="radio"
                name="sort"
                value={opt.value}
                checked={localFilters.sort === opt.value}
                onChange={() => update('sort', opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </section>

      {/* Price range */}
      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>Price per Night (₹)</h4>
        <div className={styles.priceRow}>
          <input
            type="number"
            placeholder="Min"
            className={styles.priceInput}
            value={localFilters.min_price}
            min={0}
            onChange={(e) => update('min_price', e.target.value)}
          />
          <span className={styles.priceSep}>–</span>
          <input
            type="number"
            placeholder="Max"
            className={styles.priceInput}
            value={localFilters.max_price}
            min={0}
            onChange={(e) => update('max_price', e.target.value)}
          />
        </div>
      </section>

      {/* Free Cancellation */}
      <section className={styles.section}>
        <label className={styles.checkLabel}>
          <input
            type="checkbox"
            checked={localFilters.free_cancellation}
            onChange={(e) => update('free_cancellation', e.target.checked)}
          />
          Free Cancellation
        </label>
      </section>

      {/* Property Type */}
      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>Property Type</h4>
        {PROPERTY_TYPES.map((pt) => (
          <label key={pt} className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={(localFilters.property_type || []).includes(pt)}
              onChange={() => toggleArray('property_type', pt)}
            />
            {pt}
          </label>
        ))}
      </section>

      {/* Amenities */}
      <section className={styles.section}>
        <h4 className={styles.sectionTitle}>Amenities</h4>
        {AMENITY_OPTIONS.map((amenity) => (
          <label key={amenity} className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={(localFilters.amenity || []).includes(amenity)}
              onChange={() => toggleArray('amenity', amenity)}
            />
            {amenity}
          </label>
        ))}
      </section>
    </aside>
  )
}
