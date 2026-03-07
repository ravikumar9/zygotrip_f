(function () {
  const STORAGE_KEY = 'zygo:queryState';
  const STATE_KEYS = ['checkin', 'checkout', 'guests', 'location', 'rooms'];

  const readStateFromUrl = () => {
    const params = new URLSearchParams(window.location.search);
    const location = params.get('location') || params.get('q') || '';
    const rooms = params.get('rooms') || params.get('quantity') || '';
    return {
      checkin: params.get('checkin') || params.get('check_in') || '',
      checkout: params.get('checkout') || params.get('check_out') || '',
      guests: params.get('guests') || '',
      location,
      rooms,
    };
  };

  const readStateFromStorage = () => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  };

  const writeStateToStorage = (state) => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
      // Ignore storage errors.
    }
  };

  const mergeState = (primary, fallback) => {
    const merged = { ...fallback };
    STATE_KEYS.forEach((key) => {
      if (primary[key]) {
        merged[key] = primary[key];
      }
    });
    return merged;
  };

  const applyStateToUrl = (state) => {
    if (!state) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const hadChanges = STATE_KEYS.some((key) => {
      if (!state[key]) {
        return false;
      }
      const existing = params.get(key);
      if (existing) {
        return false;
      }
      params.set(key, state[key]);
      return true;
    });

    if (state.location && !params.get('q')) {
      params.set('q', state.location);
    }
    if (state.rooms && !params.get('quantity')) {
      params.set('quantity', state.rooms);
    }

    if (hadChanges) {
      const newUrl = `${window.location.pathname}?${params.toString()}${window.location.hash || ''}`;
      window.history.replaceState({}, '', newUrl);
    }
  };

  const syncInputs = (state) => {
    if (!state) {
      return;
    }

    const setValueIfEmpty = (selector, value) => {
      if (!value) {
        return;
      }
      document.querySelectorAll(selector).forEach((input) => {
        if (input && !input.value) {
          input.value = value;
        }
      });
    };

    setValueIfEmpty('input[name="checkin"], input[name="check_in"]', state.checkin);
    setValueIfEmpty('input[name="checkout"], input[name="check_out"]', state.checkout);
    setValueIfEmpty('select[name="guests"], input[name="guests"]', state.guests);
    setValueIfEmpty('input[name="location"], input[name="q"]', state.location);
    setValueIfEmpty('input[name="rooms"], input[name="quantity"]', state.rooms);
  };

  const appendStateToLinks = (state) => {
    if (!state) {
      return;
    }
    const pathsToPersist = ['/search', '/hotels', '/booking', '/payments', '/invoice'];
    const shouldPersist = (path) => pathsToPersist.some((prefix) => path.startsWith(prefix));

    document.querySelectorAll('a[href]').forEach((link) => {
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) {
        return;
      }

      const url = new URL(href, window.location.origin);
      if (url.origin !== window.location.origin) {
        return;
      }
      if (!shouldPersist(url.pathname)) {
        return;
      }

      STATE_KEYS.forEach((key) => {
        if (state[key] && !url.searchParams.get(key)) {
          url.searchParams.set(key, state[key]);
        }
      });
      if (state.location && !url.searchParams.get('q')) {
        url.searchParams.set('q', state.location);
      }
      if (state.rooms && !url.searchParams.get('quantity')) {
        url.searchParams.set('quantity', state.rooms);
      }
      link.setAttribute('href', url.pathname + '?' + url.searchParams.toString() + url.hash);
    });
  };

  const appendStateToForms = (state) => {
    if (!state) {
      return;
    }
    document.addEventListener('submit', (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) {
        return;
      }
      STATE_KEYS.forEach((key) => {
        if (!state[key]) {
          return;
        }
        if (form.querySelector(`[name="${key}"]`)) {
          return;
        }
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = state[key];
        form.appendChild(input);
      });
    });
  };

  const init = () => {
    const fromUrl = readStateFromUrl();
    const fromStorage = readStateFromStorage();
    const merged = mergeState(fromUrl, fromStorage);

    writeStateToStorage(merged);
    applyStateToUrl(merged);
    syncInputs(merged);
    appendStateToLinks(merged);
    appendStateToForms(merged);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
