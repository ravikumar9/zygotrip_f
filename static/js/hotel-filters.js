(function () {
  const filterInputs = Array.from(document.querySelectorAll('.filter-input'));
  const cards = Array.from(document.querySelectorAll('.card[data-city]'));
  const priceInputs = filterInputs.filter((input) => input.dataset.filterGroup === 'price');

  if (!filterInputs.length || !cards.length) {
    return;
  }

  const getSelectedValues = (group) => {
    return filterInputs
      .filter((input) => input.dataset.filterGroup === group && input.type === 'checkbox' && input.checked)
      .map((input) => input.value);
  };

  const getSearchQuery = () => {
    const input = filterInputs.find((item) => item.dataset.filterGroup === 'search');
    return input ? input.value.trim().toLowerCase() : '';
  };

  const getPriceMax = () => {
    const slider = priceInputs[0];
    return slider ? Number(slider.value || slider.max || 0) : 0;
  };

  const applyFilters = () => {
    const selectedLocations = getSelectedValues('location');
    const selectedRatings = getSelectedValues('rating').map(Number);
    const selectedAmenities = getSelectedValues('amenities');
    const selectedTypes = getSelectedValues('type');
    const selectedMeals = getSelectedValues('meal');
    const selectedCancel = getSelectedValues('cancel');
    const selectedInstant = getSelectedValues('instant');
    const searchQuery = getSearchQuery();
    const maxPrice = getPriceMax();

    cards.forEach((card) => {
      const city = (card.dataset.city || '').toLowerCase();
      const rating = Number(card.dataset.rating || 0);
      const price = Number(card.dataset.price || 0);
      const type = (card.dataset.type || '').toLowerCase();
      const meal = (card.dataset.meal || '').toLowerCase();
      const cancelPolicy = (card.dataset.cancel || '').toLowerCase();
      const instant = (card.dataset.instant || '').toLowerCase();
      const amenities = (card.dataset.amenities || '').split(',').map((value) => value.trim()).filter(Boolean);
      const title = (card.querySelector('.card-title')?.textContent || '').toLowerCase();

      const matchesSearch = !searchQuery || title.includes(searchQuery);
      const matchesLocation = !selectedLocations.length || selectedLocations.includes(city);
      const matchesRating = !selectedRatings.length || selectedRatings.some((value) => rating >= value);
      const matchesPrice = !maxPrice || price <= maxPrice || price === 0;
      const matchesType = !selectedTypes.length || selectedTypes.includes(type);
      const matchesMeal = !selectedMeals.length || selectedMeals.includes(meal);
      const matchesCancel = !selectedCancel.length || selectedCancel.includes(cancelPolicy);
      const matchesInstant = !selectedInstant.length || selectedInstant.includes(instant);
      const matchesAmenities = !selectedAmenities.length || selectedAmenities.every((value) => amenities.includes(value));

      const isVisible = [
        matchesSearch,
        matchesLocation,
        matchesRating,
        matchesPrice,
        matchesType,
        matchesMeal,
        matchesCancel,
        matchesInstant,
        matchesAmenities,
      ].every(Boolean);

      card.style.display = isVisible ? '' : 'none';
    });
  };

  filterInputs.forEach((input) => {
    input.addEventListener('input', applyFilters);
    input.addEventListener('change', applyFilters);
  });

  applyFilters();
})();
