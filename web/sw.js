// Offline podpora: aplikace a poslední stažená data jsou k dispozici i u vody bez signálu.
const CACHE = 'reviry-v1';
const SHELL = [
  './', 'index.html', 'css/app.css', 'manifest.webmanifest', 'icons/icon.svg',
  'js/main.js', 'js/data.js', 'js/rules.js', 'js/weather.js', 'js/water.js', 'js/recommend.js',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Síť má přednost (čerstvá data, počasí), při výpadku se použije cache.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  const cacheable = url.origin === location.origin || url.hostname === 'unpkg.com' || url.hostname === 'api.open-meteo.com';
  if (!cacheable) return;
  e.respondWith(
    fetch(e.request)
      .then(res => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request).then(m => m ?? Response.error())),
  );
});
