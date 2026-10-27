// PWA Service Worker registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW registration failed:', err));
  });
}

// Force uppercase on free-text inputs (as per orientações)
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('input[style*="uppercase"], textarea[style*="uppercase"]').forEach(el => {
    el.addEventListener('input', function () {
      const start = this.selectionStart;
      const end = this.selectionEnd;
      this.value = this.value.toUpperCase();
      this.setSelectionRange(start, end);
    });
  });
});
