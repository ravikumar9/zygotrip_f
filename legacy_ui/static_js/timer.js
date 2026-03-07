(function() {
  function updateTimer() {
    const el = document.getElementById("timer");
    if (!el) return;
    
    let seconds = parseInt(el.dataset.time);
    if (isNaN(seconds) || seconds <= 0) {
      el.innerText = "Expired";
      location.reload();
      return;
    }
    
    seconds--;
    el.dataset.time = seconds;
    
    // Format as MM:SS
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    el.innerText = `${minutes}:${secs.toString().padStart(2, '0')}`;
  }
  
  // Update immediately
  updateTimer();
  
  // Then update every second
  setInterval(updateTimer, 1000);
})();
