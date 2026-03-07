(function () {
  const dropdowns = document.querySelectorAll('.navbar-dropdown');

  const closeAll = () => {
    dropdowns.forEach((dropdown) => {
      dropdown.classList.remove('is-open');
      const toggle = dropdown.querySelector('.dropdown-toggle');
      if (toggle) {
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  };

  dropdowns.forEach((dropdown) => {
    const toggle = dropdown.querySelector('.dropdown-toggle');
    if (!toggle) {
      return;
    }

    toggle.addEventListener('click', (event) => {
      event.preventDefault();
      const isOpen = dropdown.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  });

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (!target.closest('.navbar-dropdown')) {
      closeAll();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeAll();
    }
  });
})();
