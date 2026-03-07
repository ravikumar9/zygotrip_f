import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import PropertyCard from '../components/property/PropertyCard'
import PropertyFilters from '../components/property/PropertyFilters'
import { getProperties, searchProperties } from '../services/api'
import styles from './ListingPage.module.css'

const PAGE_SIZE = 20

export default function ListingPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Derive initial state from URL params
  const initialQuery = searchParams.get('q') || searchParams.get('location') || ''
  const initialCheckin = searchParams.get('checkin') || ''
  const initialCheckout = searchParams.get('checkout') || ''

  const [query, setQuery] = useState(initialQuery)
  const [checkin, setCheckin] = useState(initialCheckin)
  const [checkout, setCheckout] = useState(initialCheckout)
  const [filters, setFilters] = useState({
    sort: searchParams.get('sort') || 'popular',
    min_price: searchParams.get('min_price') || '',
    max_price: searchParams.get('max_price') || '',
    free_cancellation: searchParams.get('free_cancellation') === 'true',
    property_type: searchParams.getAll('property_type'),
    amenity: searchParams.getAll('amenity'),
  })

  const [results, setResults] = useState([])
  const [pagination, setPagination] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1)

  const fetchProperties = useCallback(async (pageNum = 1) => {
    setLoading(true)
    setError(null)
    try {
      const params = {
        ...filters,
        page: pageNum,
        page_size: PAGE_SIZE,
      }
      if (query) params.location = query
      if (checkin) params.checkin = checkin
      if (checkout) params.checkout = checkout

      const data = query
        ? await searchProperties({ ...params, q: query })
        : await getProperties(params)

      setResults(data.results || [])
      setPagination(data.pagination || null)
    } catch (err) {
      setError(err.message || 'Failed to load properties.')
    } finally {
      setLoading(false)
    }
  }, [filters, query, checkin, checkout])

  useEffect(() => {
    fetchProperties(page)
  }, [fetchProperties, page])

  function handleSearch(e) {
    e.preventDefault()
    setPage(1)
    fetchProperties(1)
  }

  function handleFiltersChange(newFilters) {
    setFilters(newFilters)
    setPage(1)
  }

  return (
    <div className={styles.page}>
      {/* Search bar */}
      <header className={styles.searchHeader}>
        <div className={styles.searchContainer}>
          <h1 className={styles.brand}>ZygoTrip</h1>
          <form className={styles.searchForm} onSubmit={handleSearch}>
            <input
              type="text"
              placeholder="Search by city, area or hotel name"
              className={styles.searchInput}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <input
              type="date"
              className={styles.dateInput}
              value={checkin}
              onChange={(e) => setCheckin(e.target.value)}
              placeholder="Check-in"
            />
            <input
              type="date"
              className={styles.dateInput}
              value={checkout}
              onChange={(e) => setCheckout(e.target.value)}
              placeholder="Check-out"
            />
            <button type="submit" className={styles.searchBtn}>
              Search
            </button>
          </form>
        </div>
      </header>

      <div className={styles.layout}>
        {/* Filters sidebar */}
        <PropertyFilters filters={filters} onChange={handleFiltersChange} />

        {/* Results */}
        <main className={styles.main}>
          {/* Results count */}
          <div className={styles.resultsHeader}>
            {!loading && pagination && (
              <p className={styles.resultsCount}>
                {pagination.count.toLocaleString()} properties found
                {query ? ` for "${query}"` : ''}
              </p>
            )}
          </div>

          {/* Loading */}
          {loading && (
            <div className={styles.loadingGrid}>
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className={styles.skeleton} />
              ))}
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div className={styles.errorBox}>
              <p>{error}</p>
              <button onClick={() => fetchProperties(page)} className={styles.retryBtn}>
                Retry
              </button>
            </div>
          )}

          {/* Empty */}
          {!loading && !error && results.length === 0 && (
            <div className={styles.emptyBox}>
              <p>No properties found. Try a different location or adjust filters.</p>
            </div>
          )}

          {/* Grid */}
          {!loading && results.length > 0 && (
            <div className={styles.grid}>
              {results.map((property) => (
                <PropertyCard key={property.id} property={property} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loading && pagination && pagination.total_pages > 1 && (
            <div className={styles.pagination}>
              <button
                className={styles.pageBtn}
                disabled={!pagination.previous}
                onClick={() => setPage((p) => p - 1)}
              >
                ← Previous
              </button>
              <span className={styles.pageInfo}>
                Page {pagination.current_page} of {pagination.total_pages}
              </span>
              <button
                className={styles.pageBtn}
                disabled={!pagination.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
