(function () {
  const form = document.querySelector('[data-filter-form]');
  const results = document.querySelector('[data-results]');
  const skeleton = document.getElementById('results-skeleton');
  const count = document.getElementById('results-count');
  const ratingInput = document.getElementById('rating-filter');
  const presetButtons = document.querySelectorAll('[data-preset]');
  const ratingChips = document.querySelectorAll('.chip-toggle[data-rating]');
  const resetEmpty = document.querySelector('[data-reset-empty]');
  const histogram = document.querySelector('[data-price-histogram]');
  const mobileFilter = document.querySelector('[data-mobile-filter]');
  const mobileSort = document.querySelector('[data-mobile-sort]');

  if (!form || !results) {
    return;
  }

  const debounce = (fn, wait) => {
    let timeoutId;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => fn(...args), wait);
    };
  };

  const setRating = (value) => {
    if (ratingInput) {
      ratingInput.value = value;
    }
    ratingChips.forEach((chip) => {
      const isActive = chip.dataset.rating === String(value);
      chip.classList.toggle('active', isActive);
    });
  };

  const urlParams = new URLSearchParams(window.location.search);
  const initialRating = urlParams.get('rating');
  if (initialRating) {
    setRating(initialRating);
  }

  const applyPreset = (preset) => {
    const maxPrice = document.getElementById('max-price');
    const minPrice = document.getElementById('min-price');
    const priceRange = document.getElementById('price-range');
    const amenityInputs = document.querySelectorAll('input[name="amenities"]');

    amenityInputs.forEach((input) => {
      input.checked = false;
    });

    if (preset === 'budget') {
      if (minPrice) minPrice.value = '0';
      if (maxPrice) maxPrice.value = '2500';
      if (priceRange) priceRange.value = '2500';
      setRating('3');
    } else if (preset === 'family') {
      if (maxPrice) maxPrice.value = '6000';
      if (priceRange) priceRange.value = '6000';
      setRating('4');
      amenityInputs.forEach((input) => {
        const value = input.value.toLowerCase();
        if (value.includes('breakfast') || value.includes('pool')) {
          input.checked = true;
        }
      });
    } else if (preset === 'luxury') {
      if (minPrice) minPrice.value = '7000';
      if (maxPrice) maxPrice.value = '20000';
      if (priceRange) priceRange.value = '20000';
      setRating('4.5');
    } else if (preset === 'business') {
      if (maxPrice) maxPrice.value = '8000';
      if (priceRange) priceRange.value = '8000';
      setRating('4');
      amenityInputs.forEach((input) => {
        const value = input.value.toLowerCase();
        if (value.includes('wifi')) {
          input.checked = true;
        }
      });
    } else if (preset === 'weekend') {
      if (maxPrice) maxPrice.value = '5000';
      if (priceRange) priceRange.value = '5000';
      setRating('4');
    }
  };

  const buildBadge = (badge) => {
    const label = badge && badge.label ? badge.label : '';
    if (!label) {
      return '';
    }
    return `<span class="hotel-card-badge hotel-card-badge--primary">${label}</span>`;
  };

  const buildCard = (hotel) => {
    const image = hotel.images && hotel.images.featured ? hotel.images.featured : '/static/img/placeholder-hotel.jpg';
    const rating = hotel.rating ? hotel.rating.value : null;
    const ratingCount = hotel.rating ? hotel.rating.count : 0;
    const price = hotel.price ? hotel.price.base : null;
    const discount = hotel.discount ? hotel.discount.percentage : null;
    const badges = Array.isArray(hotel.badges) ? hotel.badges : [];
    const trustBadges = badges.slice(0, 3).map(buildBadge).join('');

    const bookingSignals = hotel.booking_signals || {};
    const bookedToday = bookingSignals.bookings_today || 0;
    const popularityText = bookedToday >= 5 ? `Booked ${bookedToday} times today` : '';

    const cancellation = hotel.cancellation || {};
    const cancellationText = cancellation.has_free_cancellation ? `Free cancellation up to ${cancellation.cancellation_hours}h` : 'Non-refundable';

    const recommended = hotel.relevance_score && Number(hotel.relevance_score) >= 0.75;

    return `
      <article class="hotel-card-premium">
        <a href="${hotel.cta ? hotel.cta.url : '#'}" class="hotel-card-link">
          <div class="hotel-card-image-wrapper">
            <img src="${image}" alt="${hotel.name}" class="hotel-image" loading="lazy">
            <span class="hotel-card-quickview">Quick view</span>
          </div>
          <div class="hotel-card-info">
            <div class="hotel-card-header">
              <h3 class="hotel-card-title">${hotel.name}</h3>
              ${rating ? `<div class="hotel-card-rating">${rating.toFixed(1)} ★</div>` : ''}
            </div>
            <div class="hotel-card-location">
              <span>${hotel.location ? hotel.location.city : ''}</span>
            </div>
            <div class="hotel-card-trust">
              ${recommended ? '<span class="hotel-card-badge hotel-card-badge--primary">Recommended</span>' : ''}
              ${trustBadges}
            </div>
            <div class="hotel-card-badges">
              ${popularityText ? `<span class="hotel-card-badge">${popularityText}</span>` : ''}
              <span class="hotel-card-badge">${cancellationText}</span>
              ${ratingCount ? `<span class="hotel-card-badge">${ratingCount} reviews</span>` : ''}
            </div>
          </div>
          <div class="hotel-card-price-section">
            <div>
              ${discount ? `<div class="hotel-card-price-original">₹${Math.round(price / (1 - discount / 100))}</div>` : ''}
              <div class="hotel-card-price-current">₹${price ? Math.round(price) : 0}</div>
              <div class="hotel-card-price-label">per night</div>
            </div>
            <button class="hotel-card-cta" type="button">View Details</button>
          </div>
        </a>
      </article>
    `;
  };

  const updateHistogram = (resultsData) => {
    if (!histogram) {
      return;
    }
    histogram.innerHTML = '';
    const prices = resultsData.map((item) => item.price && item.price.base).filter(Boolean);
    if (!prices.length) {
      histogram.innerHTML = '<div class="price-histogram-empty">No price data</div>';
      return;
    }

    const bins = 8;
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const step = (max - min) / bins || 1;
    const counts = new Array(bins).fill(0);

    prices.forEach((price) => {
      const idx = Math.min(bins - 1, Math.floor((price - min) / step));
      counts[idx] += 1;
    });

    const maxCount = Math.max(...counts) || 1;
    counts.forEach((countValue) => {
      const level = Math.max(1, Math.ceil((countValue / maxCount) * 5));
      const bar = document.createElement('span');
      bar.className = `price-bar level-${level}`;
      histogram.appendChild(bar);
    });
  };

  const getParams = () => {
    const params = new URLSearchParams();
    const inputs = form.querySelectorAll('[data-filter-input]');

    inputs.forEach((input) => {
      if (input.type === 'checkbox') {
        if (input.checked) {
          params.append(input.name, input.value);
        }
        return;
      }

      if (input.type === 'radio') {
        if (input.checked) {
          params.append(input.name, input.value);
        }
        return;
      }

      if (input.value) {
        params.append(input.name, input.value);
      }
    });

    const urlParams = new URLSearchParams(window.location.search);
    const q = urlParams.get('q');
    if (q) {
      params.append('q', q);
    }

    ['checkin', 'checkout', 'guests', 'rooms', 'location'].forEach((key) => {
      const value = urlParams.get(key);
      if (value) {
        params.append(key, value);
      }
    });

    return params;
  };

  const loadResults = () => {
    const params = getParams();
    if (skeleton) {
      skeleton.style.display = 'grid';
    }
    results.style.opacity = '0.4';

    fetch(`/api/v1/search/?${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        const list = Array.isArray(data.results) ? data.results : [];
        results.innerHTML = list.length
          ? list.map(buildCard).join('')
          : `
            <div class="empty-state">
              <div class="empty-state-icon">🏨</div>
              <h3 class="empty-state-title">No hotels found</h3>
              <p class="empty-state-description">Try adjusting your filters or search query.</p>
              <div class="empty-state-action">
                <button class="btn btn-primary" data-reset-empty>Reset Filters</button>
                <a href="/hotels/" class="btn btn-outline">Browse All</a>
              </div>
            </div>
          `;

        if (count) {
          count.textContent = data.pagination ? data.pagination.total_results : list.length;
        }

        updateHistogram(list);
      })
      .catch(() => {
        results.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <h3 class="empty-state-title">Unable to load hotels</h3>
            <p class="empty-state-description">Please try again in a moment.</p>
            <div class="empty-state-action">
              <button class="btn btn-primary" data-filter-apply>Retry</button>
            </div>
          </div>
        `;
      })
      .finally(() => {
        if (skeleton) {
          skeleton.style.display = 'none';
        }
        results.style.opacity = '1';
      });
  };

  const debouncedLoad = debounce(loadResults, 300);

  form.addEventListener('input', debouncedLoad);
  form.addEventListener('change', debouncedLoad);

  ratingChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      setRating(chip.dataset.rating || '');
      debouncedLoad();
    });
  });

  presetButtons.forEach((button) => {
    button.addEventListener('click', () => {
      presetButtons.forEach((btn) => btn.classList.remove('active'));
      button.classList.add('active');
      applyPreset(button.dataset.preset);
      debouncedLoad();
    });
  });

  const applyBtn = document.querySelector('[data-filter-apply]');
  if (applyBtn) {
    applyBtn.addEventListener('click', loadResults);
  }

  const resetBtn = document.querySelector('[data-filter-reset]');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      form.reset();
      setRating('');
      presetButtons.forEach((btn) => btn.classList.remove('active'));
      loadResults();
    });
  }

  document.addEventListener('click', (event) => {
    if (event.target && event.target.matches('[data-reset-empty]')) {
      if (resetBtn) {
        resetBtn.click();
      }
    }
  });

  if (mobileFilter) {
    mobileFilter.addEventListener('click', () => {
      form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  if (mobileSort) {
    const sortSelect = form.querySelector('[data-filter-input="sort"]');
    mobileSort.addEventListener('click', () => {
      if (sortSelect) {
        sortSelect.focus();
      }
    });
  }

  setRating(ratingInput ? ratingInput.value : '');
  loadResults();
})();
