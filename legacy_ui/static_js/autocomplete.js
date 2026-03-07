(function () {
  const AUTOCOMPLETE_ENDPOINT = '/api/search/?q=';
  const INPUT_SELECTOR = '[data-autocomplete="search"]';

  const debounce = (fn, wait) => {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), wait);
    };
  };

  const highlightMatch = (label, query) => {
    if (!query) {
      return label;
    }
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'ig');
    return label.replace(regex, '<mark>$1</mark>');
  };

  const groupResults = (items) => {
    const groups = { city: [], area: [], property: [] };
    items.forEach((item) => {
      if (groups[item.type]) {
        groups[item.type].push(item);
      }
    });
    return groups;
  };

  const ensureList = (input) => {
    const wrapper = input.closest('.search-form-field') || input.parentElement;
    let list = wrapper ? wrapper.querySelector('[data-autocomplete-list]') : null;
    if (!list && wrapper) {
      list = document.createElement('div');
      list.className = 'search-suggestions';
      list.setAttribute('data-autocomplete-list', '');
      list.hidden = true;
      wrapper.appendChild(list);
    }
    return list;
  };

  const closeList = (list, input) => {
    if (!list) {
      return;
    }
    list.innerHTML = '';
    list.hidden = true;
    if (input) {
      input.setAttribute('aria-expanded', 'false');
    }
  };

  const renderGroup = (title, items, query) => {
    if (!items.length) {
      return '';
    }
    const markup = items
      .map((item) => {
        const name = item.name || '';
        const count = item.property_count;
        const countMarkup = typeof count === 'number' ? `<span class="search-suggestion-count">${count}</span>` : '';
        const labelMarkup = highlightMatch(name, query);
        return `
          <li class="search-suggestion" data-autocomplete-value="${name}" data-type="${item.type}" data-slug="${item.slug}">
            <div class="search-suggestion-main">
              <div class="search-suggestion-label">${labelMarkup}</div>
            </div>
            ${countMarkup}
          </li>
        `;
      })
      .join('');

    return `
      <div class="search-suggestion-group">
        <div class="search-suggestion-title">${title}</div>
        <ul>${markup}</ul>
      </div>
    `;
  };

  const renderList = (list, input, items, query) => {
    if (!list) {
      return;
    }
    if (!items.length) {
      closeList(list, input);
      return;
    }

    const groups = groupResults(items);
    const markup = [
      renderGroup('Cities', groups.city, query),
      renderGroup('Areas', groups.area, query),
      renderGroup('Properties', groups.property, query),
    ].join('');

    list.innerHTML = markup;
    list.hidden = !markup;
    if (input) {
      input.setAttribute('aria-expanded', 'true');
    }
  };

  const fetchResults = async (query) => {
    const response = await fetch(`${AUTOCOMPLETE_ENDPOINT}${encodeURIComponent(query)}`);
    if (!response.ok) {
      return [];
    }
    const data = await response.json();
    // Normalize response: handle flat array or grouped {groups: [...]} format
    let items = Array.isArray(data) ? data : [];
    if (!items.length && data && Array.isArray(data.groups)) {
      // Flatten grouped response from /search/autocomplete/ endpoint
      data.groups.forEach((group) => {
        (group.items || []).forEach((item) => {
          items.push({ ...item, name: item.label || item.name, property_count: item.count || null });
        });
      });
    }
    // Normalize 'locality' type → 'area' so JS groupResults() recognises it
    return items.map((item) => ({
      ...item,
      type: item.type === 'locality' ? 'area' : item.type,
    }));
  };

  const moveActive = (list, direction) => {
    if (!list) {
      return null;
    }
    const items = Array.from(list.querySelectorAll('.search-suggestion'));
    if (!items.length) {
      return null;
    }
    const currentIndex = items.findIndex((item) => item.classList.contains('is-active'));
    const nextIndex = currentIndex === -1 ? 0 : (currentIndex + direction + items.length) % items.length;
    if (currentIndex >= 0) {
      items[currentIndex].classList.remove('is-active');
    }
    items[nextIndex].classList.add('is-active');
    return items[nextIndex];
  };

  const applySelection = (input, list, item) => {
    if (!item) {
      return;
    }
    const value = item.getAttribute('data-autocomplete-value') || '';
    const type = item.getAttribute('data-type') || '';
    const slug = item.getAttribute('data-slug') || '';
    const form = input.closest('form');
    const hiddenLocation = form ? form.querySelector('input[name="location"]') : null;
    const cityField = form ? form.querySelector('input[name="city"]') : null;
    const areaField = form ? form.querySelector('input[name="area"]') : null;

    if (type === 'property' && slug) {
      window.location.href = `/hotels/${slug}/`;
      return;
    }

    input.value = value;
    if (hiddenLocation) {
      hiddenLocation.value = value;
    }
    if (cityField && type === 'city') {
      cityField.value = value;
    }
    if (areaField && type === 'area') {
      areaField.value = value;
    }
    if (cityField && type !== 'city') {
      cityField.value = '';
    }
    if (areaField && type !== 'area') {
      areaField.value = '';
    }
    closeList(list, input);

    if (form && form.hasAttribute('data-autocomplete-submit')) {
      form.requestSubmit();
    }
  };

  const initAutocomplete = (input) => {
    const list = ensureList(input);
    let lastResults = [];

    const handleInput = debounce(async () => {
      const query = input.value.trim();
      if (query.length < 2) {
        closeList(list, input);
        return;
      }

      try {
        lastResults = await fetchResults(query);
        renderList(list, input, lastResults, query);
      } catch (error) {
        closeList(list, input);
      }
    }, 300);

    input.addEventListener('input', handleInput);

    input.addEventListener('focus', () => {
      if (input.value.trim().length >= 2) {
        handleInput();
      }
    });

    input.addEventListener('keydown', (event) => {
      if (!list || list.hidden) {
        return;
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        moveActive(list, 1);
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        moveActive(list, -1);
      }
      if (event.key === 'Enter') {
        const active = list.querySelector('.search-suggestion.is-active');
        if (active) {
          event.preventDefault();
          applySelection(input, list, active);
        }
      }
      if (event.key === 'Escape') {
        closeList(list, input);
      }
    });

    input.addEventListener('blur', () => {
      window.setTimeout(() => closeList(list, input), 150);
    });

    if (list) {
      list.addEventListener('click', (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }
        const item = target.closest('.search-suggestion');
        if (!item) {
          return;
        }
        applySelection(input, list, item);
      });
    }

    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      if (!target.closest('.search-form-field')) {
        closeList(list, input);
      }
    });
  };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll(INPUT_SELECTOR).forEach((input) => {
      if (input instanceof HTMLInputElement) {
        initAutocomplete(input);
      }
    });
  });
})();
