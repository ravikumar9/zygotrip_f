(function () {
  const checkIn = document.querySelector('input[name="check_in"]');
  const checkOut = document.querySelector('input[name="check_out"]');
  const roomSelect = document.querySelector('select[name="room_type"]');
  const mealSelect = document.querySelector('select[name="meal_plan"]');
  const qtyInput = document.querySelector('input[name="quantity"]');
  const nightsEl = document.getElementById('price-preview-nights');
  const totalEl = document.getElementById('price-preview-total');
  const roomPricesEl = document.getElementById('room-prices-data');
  const mealPricesEl = document.getElementById('meal-prices-data');

  if (!checkIn || !checkOut || !roomSelect || !qtyInput || !nightsEl || !totalEl) {
    return;
  }

  const roomPrices = roomPricesEl ? JSON.parse(roomPricesEl.textContent || '{}') : {};
  const mealPrices = mealPricesEl ? JSON.parse(mealPricesEl.textContent || '{}') : {};

  const today = new Date();
  const toIso = (date) => date.toISOString().slice(0, 10);
  const addDays = (date, days) => {
    const copy = new Date(date);
    copy.setDate(copy.getDate() + days);
    return copy;
  };

  const minCheckIn = toIso(today);
  checkIn.min = minCheckIn;
  if (!checkIn.value) {
    checkIn.value = minCheckIn;
  }

  const updateCheckoutMin = () => {
    const checkInDate = new Date(checkIn.value);
    const minOut = toIso(addDays(checkInDate, 1));
    checkOut.min = minOut;
    if (!checkOut.value || checkOut.value < minOut) {
      checkOut.value = minOut;
    }
  };

  const updatePreview = () => {
    const checkInDate = new Date(checkIn.value);
    const checkOutDate = new Date(checkOut.value);
    const nights = Math.max(0, (checkOutDate - checkInDate) / (1000 * 60 * 60 * 24));
    const qty = parseInt(qtyInput.value || '1', 10);
    const roomRate = parseFloat(roomPrices[roomSelect.value] || '0');
    const mealRate = mealSelect && mealSelect.value ? parseFloat(mealPrices[mealSelect.value] || '0') : 0;
    const total = Math.round((roomRate + mealRate) * qty * nights);

    nightsEl.textContent = String(nights);
    totalEl.textContent = `₹${total}`;
  };

  updateCheckoutMin();
  updatePreview();

  checkIn.addEventListener('change', () => {
    updateCheckoutMin();
    updatePreview();
  });
  checkOut.addEventListener('change', updatePreview);
  roomSelect.addEventListener('change', updatePreview);
  if (mealSelect) {
    mealSelect.addEventListener('change', updatePreview);
  }
  qtyInput.addEventListener('input', updatePreview);
})();
