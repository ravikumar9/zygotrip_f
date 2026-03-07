const detailRoot = document.querySelector('[data-page="hotel-detail"]');

if (detailRoot) {
  const tabLinks = Array.from(document.querySelectorAll('[data-tab-target]'));
  const tabContents = Array.from(document.querySelectorAll('[data-tab-content]'));
  const tabIndicator = document.querySelector('[data-tab-indicator]');

  const setActiveTab = (targetId) => {
    tabLinks.forEach((link) => {
      const isActive = link.dataset.tabTarget === targetId;
      link.classList.toggle('is-active', isActive);
      link.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    tabContents.forEach((section) => {
      section.classList.toggle('is-active', section.id === targetId);
    });

    const activeLink = tabLinks.find((link) => link.dataset.tabTarget === targetId);
    if (activeLink && tabIndicator) {
      const rect = activeLink.getBoundingClientRect();
      const containerRect = activeLink.parentElement.getBoundingClientRect();
      tabIndicator.style.width = `${rect.width}px`;
      tabIndicator.style.transform = `translateX(${rect.left - containerRect.left}px)`;
    }
  };

  const initialHash = window.location.hash.replace('#', '');
  if (initialHash && document.getElementById(initialHash)) {
    setActiveTab(initialHash);
  } else if (tabLinks.length) {
    setActiveTab(tabLinks[0].dataset.tabTarget);
  }

  tabLinks.forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const targetId = link.dataset.tabTarget;
      setActiveTab(targetId);
      history.replaceState(null, '', `#${targetId}`);
      const section = document.getElementById(targetId);
      if (section) {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  const galleryModal = document.getElementById('gallery-modal');
  const galleryImage = galleryModal ? galleryModal.querySelector('.gallery-modal__image') : null;
  const galleryCaption = galleryModal ? galleryModal.querySelector('[data-gallery-caption]') : null;
  const galleryButtons = Array.from(document.querySelectorAll('.js-gallery-open'));
  const gallerySources = Array.from(document.querySelectorAll('[data-gallery-item] img'));
  let activeIndex = 0;

  const galleryItems = gallerySources.map((img) => {
    return {
      src: img ? img.getAttribute('src') : '',
      alt: img ? img.getAttribute('alt') : '',
    };
  });

  const updateGallery = (index) => {
    const item = galleryItems[index];
    if (!item || !galleryImage) {
      return;
    }
    galleryImage.src = item.src;
    galleryImage.alt = item.alt;
    if (galleryCaption) {
      galleryCaption.textContent = item.alt;
    }
  };

  const openGallery = (index) => {
    activeIndex = index;
    updateGallery(activeIndex);
    if (galleryModal) {
      galleryModal.classList.add('is-open');
      galleryModal.setAttribute('aria-hidden', 'false');
    }
  };

  const closeGallery = () => {
    if (galleryModal) {
      galleryModal.classList.remove('is-open');
      galleryModal.setAttribute('aria-hidden', 'true');
    }
  };

  galleryButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const indexValue = Number(button.dataset.index || 0);
      openGallery(indexValue);
    });
  });

  if (galleryModal) {
    galleryModal.querySelectorAll('[data-gallery-close]').forEach((button) => {
      button.addEventListener('click', closeGallery);
    });

    const prevButton = galleryModal.querySelector('[data-gallery-prev]');
    const nextButton = galleryModal.querySelector('[data-gallery-next]');

    if (prevButton) {
      prevButton.addEventListener('click', () => {
        activeIndex = (activeIndex - 1 + galleryItems.length) % galleryItems.length;
        updateGallery(activeIndex);
      });
    }

    if (nextButton) {
      nextButton.addEventListener('click', () => {
        activeIndex = (activeIndex + 1) % galleryItems.length;
        updateGallery(activeIndex);
      });
    }

    document.addEventListener('keydown', (event) => {
      if (!galleryModal.classList.contains('is-open')) {
        return;
      }
      if (event.key === 'Escape') {
        closeGallery();
      }
      if (event.key === 'ArrowLeft') {
        activeIndex = (activeIndex - 1 + galleryItems.length) % galleryItems.length;
        updateGallery(activeIndex);
      }
      if (event.key === 'ArrowRight') {
        activeIndex = (activeIndex + 1) % galleryItems.length;
        updateGallery(activeIndex);
      }
    });
  }

  const bookingCard = document.querySelector('[data-booking-card]');
  const bookingToggle = document.querySelector('[data-booking-toggle]');
  const mobileBar = document.querySelector('[data-mobile-bar]');
  const gallerySection = document.querySelector('.hotel-gallery');
  const roomSelectButtons = Array.from(document.querySelectorAll('[data-room-select]'));
  const roomTypeSelect = document.querySelector('#id_room_type');

  if (bookingToggle && bookingCard) {
    bookingToggle.addEventListener('click', () => {
      bookingCard.classList.toggle('is-open');
    });
  }

  roomSelectButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const card = button.closest('[data-room-card]');
      const roomId = card?.dataset.roomId;
      if (roomTypeSelect && roomId) {
        roomTypeSelect.value = roomId;
        roomTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
      bookingCard?.classList.add('is-open');
      bookingCard?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  if (gallerySection && mobileBar) {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          mobileBar.classList.remove('is-visible');
        } else {
          mobileBar.classList.add('is-visible');
        }
      },
      { threshold: 0.2 }
    );
    observer.observe(gallerySection);
  }

  const dateInputs = document.querySelectorAll('input[name="check_in"], input[name="check_out"]');
  const quantityInput = document.querySelector('input[name="quantity"]');
  const mobileDates = document.querySelector('[data-mobile-dates]');
  const mobileGuests = document.querySelector('[data-mobile-guests]');

  const updateMobileSummary = () => {
    const checkIn = document.querySelector('input[name="check_in"]')?.value || '';
    const checkOut = document.querySelector('input[name="check_out"]')?.value || '';
    if (mobileDates) {
      mobileDates.textContent = checkIn && checkOut ? `${checkIn} - ${checkOut}` : 'Select dates';
    }
    if (mobileGuests && quantityInput) {
      const rooms = quantityInput.value || '1';
      mobileGuests.textContent = `${rooms} room${rooms === '1' ? '' : 's'}`;
    }
  };

  dateInputs.forEach((input) => input.addEventListener('change', updateMobileSummary));
  if (quantityInput) {
    quantityInput.addEventListener('change', updateMobileSummary);
  }
  updateMobileSummary();

  const filterPanel = document.querySelector('[data-filter-panel]');
  const filterToggle = document.querySelector('[data-filter-toggle]');
  const filterCloseButtons = document.querySelectorAll('[data-filter-close]');

  if (filterToggle && filterPanel) {
    filterToggle.addEventListener('click', () => {
      filterPanel.classList.add('is-open');
    });
  }

  filterCloseButtons.forEach((button) => {
    button.addEventListener('click', () => {
      filterPanel?.classList.remove('is-open');
    });
  });

  const filterForm = document.querySelector('[data-filter-form]');
  const instantToggle = document.querySelector('[data-filter-instant]');
  const applyButton = document.querySelector('[data-filter-apply]');
  const clearButton = document.querySelector('[data-filter-clear]');
  const roomCards = Array.from(document.querySelectorAll('[data-room-card]'));
  const ratingChips = Array.from(document.querySelectorAll('[data-filter-chip]'));
  const typePills = Array.from(document.querySelectorAll('[data-filter-pill]'));
  const propertyRating = Number(detailRoot.dataset.propertyRating || 0);
  const propertyType = detailRoot.dataset.propertyType || '';
  let activeRating = '';
  let activeType = '';
  const priceInput = filterForm?.querySelector('[data-filter-input="price"]');
  const priceMinLabel = filterForm?.querySelector('[data-filter-min]');
  const priceMaxLabel = filterForm?.querySelector('[data-filter-max]');

  const applyFilters = () => {
    if (!filterForm) {
      return;
    }
    const priceValue = Number(priceInput?.value || 0);
    const selectedAmenities = Array.from(filterForm.querySelectorAll('[data-filter-input="amenity"]:checked')).map(
      (input) => input.value
    );
    const matchesRating = activeRating ? propertyRating >= Number(activeRating) : true;
    const matchesType = activeType ? propertyType === activeType : true;

    roomCards.forEach((card) => {
      const price = Number(card.dataset.price || 0);
      const amenities = (card.dataset.amenities || '').split(',').filter(Boolean);
      const matchesPrice = price <= priceValue || priceValue === 0;
      const matchesAmenities = selectedAmenities.length === 0 || selectedAmenities.every((amenity) => amenities.includes(amenity));
      card.style.display = matchesPrice && matchesAmenities && matchesRating && matchesType ? '' : 'none';
    });

    const params = new URLSearchParams(window.location.search);
    if (priceValue) {
      params.set('price', String(priceValue));
    } else {
      params.delete('price');
    }
    if (activeRating) {
      params.set('rating', String(activeRating));
    } else {
      params.delete('rating');
    }
    if (activeType) {
      params.set('type', activeType);
    } else {
      params.delete('type');
    }
    if (selectedAmenities.length) {
      params.set('amenities', selectedAmenities.join(','));
    } else {
      params.delete('amenities');
    }
    history.replaceState(null, '', `${window.location.pathname}?${params.toString()}${window.location.hash}`);
  };

  const syncPriceLabel = () => {
    if (!priceInput) {
      return;
    }
    const value = priceInput.value || '0';
    if (priceMaxLabel) {
      priceMaxLabel.textContent = `₹${value}`;
    }
  };

  const applyParamsToFilters = () => {
    const params = new URLSearchParams(window.location.search);
    const priceValue = params.get('price');
    const ratingValue = params.get('rating');
    const typeValue = params.get('type');
    const amenitiesValue = params.get('amenities');

    if (priceInput && priceValue) {
      priceInput.value = priceValue;
    }

    if (ratingValue) {
      activeRating = ratingValue;
      ratingChips.forEach((chip) => {
        chip.classList.toggle('is-active', chip.dataset.filterChip === ratingValue);
      });
    }

    if (typeValue) {
      activeType = typeValue;
      typePills.forEach((pill) => {
        pill.classList.toggle('is-active', pill.dataset.filterPill === typeValue);
      });
    }

    if (amenitiesValue) {
      const selected = amenitiesValue.split(',');
      filterForm?.querySelectorAll('[data-filter-input="amenity"]').forEach((input) => {
        input.checked = selected.includes(input.value);
      });
    }
    syncPriceLabel();
    applyFilters();
  };

  if (filterForm) {
    filterForm.addEventListener('change', () => {
      if (instantToggle?.checked) {
        applyFilters();
      }
    });
  }

  priceInput?.addEventListener('input', syncPriceLabel);

  ratingChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      const isActive = chip.classList.contains('is-active');
      ratingChips.forEach((item) => item.classList.remove('is-active'));
      activeRating = isActive ? '' : chip.dataset.filterChip;
      if (!isActive) {
        chip.classList.add('is-active');
      }
      if (instantToggle?.checked) {
        applyFilters();
      }
    });
  });

  typePills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const isActive = pill.classList.contains('is-active');
      typePills.forEach((item) => item.classList.remove('is-active'));
      activeType = isActive ? '' : pill.dataset.filterPill;
      if (!isActive) {
        pill.classList.add('is-active');
      }
      if (instantToggle?.checked) {
        applyFilters();
      }
    });
  });

  if (applyButton) {
    applyButton.addEventListener('click', applyFilters);
  }

  if (clearButton && filterForm) {
    clearButton.addEventListener('click', () => {
      filterForm.reset();
      ratingChips.forEach((item) => item.classList.remove('is-active'));
      typePills.forEach((item) => item.classList.remove('is-active'));
      activeRating = '';
      activeType = '';
      syncPriceLabel();
      applyFilters();
    });
  }

  applyParamsToFilters();

  const accordionTriggers = document.querySelectorAll('[data-accordion-trigger]');
  accordionTriggers.forEach((trigger) => {
    trigger.addEventListener('click', () => {
      const item = trigger.closest('.hotel-accordion__item');
      item?.classList.toggle('is-open');
    });
  });

  const revealItems = document.querySelectorAll('.reveal-on-scroll');
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
        }
      });
    },
    { threshold: 0.2 }
  );
  revealItems.forEach((item) => revealObserver.observe(item));
}
