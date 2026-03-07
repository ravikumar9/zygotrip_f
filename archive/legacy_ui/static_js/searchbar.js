(function () {
  const form = document.querySelector('[data-search-form]');
  if (!form) {
    return;
  }

  const locationInput = form.querySelector('#search-location');
  const locationHidden = form.querySelector('input[name="location"]');
  const suggestions = form.querySelector('[data-search-suggestions]');
  const checkinInput = form.querySelector('#search-checkin');
  const checkoutInput = form.querySelector('#search-checkout');
  const autoSubmit = form.hasAttribute('data-search-autosubmit');

  const debounce = (fn, wait) => {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), wait);
    };
  };

  const setMinDates = () => {
    if (!checkinInput && !checkoutInput) {
      return;
    }

    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    const minDate = `${year}-${month}-${day}`;

    if (checkinInput) {
      checkinInput.setAttribute('min', minDate);
    }

    if (checkoutInput) {
      checkoutInput.setAttribute('min', minDate);
    }
  };

  const updateCheckoutMin = () => {
    if (!checkinInput || !checkoutInput || !checkinInput.value) {
      return;
    }

    const checkinDate = new Date(checkinInput.value);
    const nextDay = new Date(checkinDate);
    nextDay.setDate(nextDay.getDate() + 1);

    const year = nextDay.getFullYear();
    const month = String(nextDay.getMonth() + 1).padStart(2, '0');
    const day = String(nextDay.getDate()).padStart(2, '0');
    const minCheckoutDate = `${year}-${month}-${day}`;

    checkoutInput.setAttribute('min', minCheckoutDate);
  };

  const validateDates = () => {
    if (!checkinInput || !checkoutInput) {
      return true;
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (checkinInput.value) {
      const checkin = new Date(checkinInput.value);
      if (checkin < today) {
        window.alert('Check-in date cannot be in the past');
        return false;
      }
    }

    if (checkinInput.value && checkoutInput.value) {
      const checkin = new Date(checkinInput.value);
      const checkout = new Date(checkoutInput.value);
      if (checkout <= checkin) {
        window.alert('Check-out date must be after check-in date');
        return false;
      }
    }

    return true;
  };

  const clearSuggestions = () => {
    if (!suggestions) {
      return;
    }
    suggestions.innerHTML = '';
    suggestions.hidden = true;
  };

  const renderGroup = (title, items) => {
    if (!items.length) {
      return '';
    }
    const listItems = items
      .map((item) => {
        const label = item.label || '';
        const value = item.value || label;
        const meta = item.meta || '';
        const count = typeof item.properties_count === 'number' ? item.properties_count : '';
        const countMarkup = count !== '' ? `<span class="search-suggestion-count">${count}</span>` : '';
        const metaMarkup = meta ? `<div class="search-suggestion-meta">${meta}</div>` : '';
        return `
          <li class="search-suggestion" data-value="${value}">
            <div class="search-suggestion-main">
              <div class="search-suggestion-label">${label}</div>
              ${metaMarkup}
            </div>
            ${countMarkup}
          </li>
        `;
      })
      .join('');

    return `
      <div class="search-suggestion-group">
        <div class="search-suggestion-title">${title}</div>
        <ul>${listItems}</ul>
      </div>
    `;
  };

  const renderSuggestions = (data) => {
    if (!suggestions) {
      return;
    }

    const isArrayResponse = Array.isArray(data);
    const cities = isArrayResponse
      ? data.map((item) => ({
          label: item.name || '',
          value: item.name || '',
          meta: item.state || '',
        }))
      : Array.isArray(data.cities)
      ? data.cities
      : [];
    const areas = isArrayResponse ? [] : Array.isArray(data.areas) ? data.areas : [];
    const hotels = isArrayResponse ? [] : Array.isArray(data.hotels) ? data.hotels : [];

    const markup = [
      renderGroup('Cities', cities),
      renderGroup('Areas', areas),
      renderGroup('Hotels', hotels),
    ].join('');

    suggestions.innerHTML = markup;
    suggestions.hidden = !markup;
  };

  const fetchLocations = async (query) => {
    if (!query || query.length < 2) {
      clearSuggestions();
      return;
    }

    try {
      const response = await fetch(`/api/cities/?q=${encodeURIComponent(query)}`);
      if (!response.ok) {
        clearSuggestions();
        return;
      }

      const data = await response.json();
      if (data && typeof data === 'object') {
        renderSuggestions(data);
      } else {
        clearSuggestions();
      }
    } catch (error) {
      clearSuggestions();
    }
  };

  if (locationInput) {
    const debouncedFetch = debounce((event) => fetchLocations(event.target.value), 300);
    locationInput.addEventListener('input', debouncedFetch);
    locationInput.addEventListener('input', () => {
      if (locationHidden) {
        locationHidden.value = locationInput.value;
      }
    });

    locationInput.addEventListener('focus', () => {
      if (locationInput.value.trim().length >= 2) {
        fetchLocations(locationInput.value.trim());
      }
    });

    locationInput.addEventListener('blur', () => {
      window.setTimeout(() => clearSuggestions(), 150);
    });

    if (suggestions) {
      suggestions.addEventListener('click', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }
        const item = target.closest('.search-suggestion');
        if (!item) {
          return;
        }
        const value = item.getAttribute('data-value');
        if (!value) {
          return;
        }
        locationInput.value = value;
        if (locationHidden) {
          locationHidden.value = value;
        }
        clearSuggestions();
        if (autoSubmit) {
          form.requestSubmit();
        }
      });
    }

    if (autoSubmit) {
      const debouncedSubmit = debounce(() => {
        if (locationInput.value.trim().length < 2) {
          return;
        }
        form.requestSubmit();
      }, 350);
      locationInput.addEventListener('input', debouncedSubmit);
    }
  }

  if (checkinInput) {
    checkinInput.addEventListener('change', updateCheckoutMin);
  }

  form.addEventListener('submit', (event) => {
    if (!validateDates()) {
      event.preventDefault();
    }
  });

  setMinDates();
})();
