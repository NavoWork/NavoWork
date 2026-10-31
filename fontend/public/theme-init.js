/* Run before styles/React so the stored preference applies to the first paint. */
(function () {
  const key = 'navowork:theme';
  const valid = (value) => ['light', 'dark', 'system'].includes(value);
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const listeners = new Set();
  let preference = 'system';
  let storageAvailable = true;
  let snapshot;

  try {
    const stored = localStorage.getItem(key);
    if (valid(stored)) preference = stored;
  } catch {
    storageAvailable = false;
  }

  function apply() {
    const resolved = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.style.colorScheme = resolved;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', resolved === 'dark' ? '#111111' : '#F7F8FA');
    document
      .getElementById('app-favicon')
      ?.setAttribute('href', `/brand/navowork-favicon-${resolved}.svg`);
    if (
      snapshot?.preference === preference &&
      snapshot?.resolved === resolved &&
      snapshot?.storageAvailable === storageAvailable
    )
      return;
    snapshot = Object.freeze({ preference, resolved, storageAvailable });
    listeners.forEach((listener) => listener());
  }

  window.navoworkTheme = {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    setPreference(value) {
      if (!valid(value)) return;
      preference = value;
      try {
        localStorage.setItem(key, value);
        storageAvailable = true;
      } catch {
        storageAvailable = false;
      }
      apply();
    },
  };
  media.addEventListener('change', apply);
  window.addEventListener('storage', (event) => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : 'system';
    apply();
  });
  apply();
})();
