(function () {
  const forms = document.querySelectorAll('[data-auto-submit]');
  forms.forEach((form) => {
    form.addEventListener('change', (event) => {
      const target = event.target;
      if (target && (target.matches('input') || target.matches('select'))) {
        form.submit();
      }
    });
  });
})();
