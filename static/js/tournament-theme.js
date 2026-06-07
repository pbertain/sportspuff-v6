(function () {
  const STORAGE_KEY = 'sportspuff:tournament-theme';
  const THEMES = new Set(['atp', 'wta', 'wimbledon', 'roland-garros', 'us-open', 'australian-open']);

  function cleanTheme(theme) {
    return THEMES.has(theme) ? theme : '';
  }

  function applyTheme(theme) {
    const clean = cleanTheme(theme);
    if (clean) {
      document.body.dataset.tournamentTheme = clean;
      try {
        localStorage.setItem(STORAGE_KEY, clean);
      } catch (e) {}
    } else {
      delete document.body.dataset.tournamentTheme;
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (e) {}
    }
    return clean;
  }

  function savedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) || '';
    } catch (e) {
      return '';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const select = document.getElementById('tournament-theme-select');
    const activeTheme = applyTheme(savedTheme());

    if (!select) return;
    select.value = activeTheme;
    select.addEventListener('change', function () {
      applyTheme(select.value);
    });
  });
})();
