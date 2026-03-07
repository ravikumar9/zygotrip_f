setInterval(() => {
  const el = document.getElementById("timer");
  if (!el || !el.dataset.exp) {
    return;
  }
  const diff = new Date(el.dataset.exp) - new Date();
  if (diff <= 0) {
    location.reload();
    return;
  }
  el.innerText = Math.floor(diff / 1000) + "s";
}, 1000);
