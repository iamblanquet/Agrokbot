const CACHE = 'campo-shell-v26';
const SHELL = ['/', '/index.html', '/style.css', '/app.js', '/auth.js', '/storage.js', '/sync.js', '/admin.js', '/monitor.js', '/api-client.js', '/manifest.webmanifest', '/icon.svg', '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png', '/agrokool-mark.png', '/agrokool-mark-white.png', '/agrokool-logo.png', '/agrokool-logo-white.png', '/isologo-agk.png', '/agrokool-verde.png', '/agrokool-gold.png', '/agrokool-horizontal.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(Promise.all([
    caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('campo-shell-') && k !== CACHE).map(k => caches.delete(k)))),
    self.clients.claim()
  ]));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (!SHELL.includes(url.pathname) && event.request.mode !== 'navigate') return;
  // Prefer the current app while online; preserve the shell for offline capture.
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(url.pathname, copy)));
      return response;
    }
    return caches.match(event.request, {ignoreSearch:true}).then(cached => cached || response);
  }).catch(async () => (await caches.match(event.request, {ignoreSearch:true})) || (event.request.mode === 'navigate' ? await caches.match('/') : Response.error())));
});
