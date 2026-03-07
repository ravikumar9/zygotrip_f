(function () {
  const toggle = document.querySelector('[data-toggle="price-breakdown"]');
  const panel = document.getElementById('price-breakdown-panel');

  if (!toggle || !panel) {
    return;
  }

  toggle.addEventListener('click', function () {
    const isOpen = panel.classList.toggle('is-open');
    panel.setAttribute('aria-hidden', String(!isOpen));
    toggle.setAttribute('aria-expanded', String(isOpen));
  });
})();
