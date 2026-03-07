import { useState } from 'react'
import styles from './PropertyGallery.module.css'

export default function PropertyGallery({ images = [], propertyName = '' }) {
  const [active, setActive] = useState(0)
  const [lightboxOpen, setLightboxOpen] = useState(false)

  if (!images.length) {
    return <div className={styles.placeholder}>No photos available</div>
  }

  const currentImage = images[active]

  const prev = () => setActive((i) => (i === 0 ? images.length - 1 : i - 1))
  const next = () => setActive((i) => (i === images.length - 1 ? 0 : i + 1))

  return (
    <div className={styles.gallery}>
      {/* Main image */}
      <div className={styles.mainWrap}>
        <img
          src={currentImage.url}
          alt={currentImage.caption || propertyName}
          className={styles.mainImage}
          onClick={() => setLightboxOpen(true)}
        />
        <button className={`${styles.navBtn} ${styles.navLeft}`} onClick={prev} aria-label="Previous">
          ‹
        </button>
        <button className={`${styles.navBtn} ${styles.navRight}`} onClick={next} aria-label="Next">
          ›
        </button>
        <span className={styles.counter}>{active + 1} / {images.length}</span>
      </div>

      {/* Thumbnail strip */}
      {images.length > 1 && (
        <div className={styles.thumbs}>
          {images.map((img, i) => (
            <button
              key={img.id ?? i}
              className={`${styles.thumb} ${i === active ? styles.thumbActive : ''}`}
              onClick={() => setActive(i)}
              aria-label={`Photo ${i + 1}`}
            >
              <img src={img.url} alt={img.caption || `Photo ${i + 1}`} />
            </button>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {lightboxOpen && (
        <div className={styles.lightboxOverlay} onClick={() => setLightboxOpen(false)}>
          <button
            className={styles.lightboxClose}
            onClick={() => setLightboxOpen(false)}
            aria-label="Close"
          >
            ×
          </button>
          <img
            src={currentImage.url}
            alt={currentImage.caption || propertyName}
            className={styles.lightboxImage}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  )
}
