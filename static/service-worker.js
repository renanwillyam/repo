self.addEventListener('install', event => {
  event.waitUntil(
    caches.open('financeiro-cache').then(cache => {
      return cache.addAll([
        '/',
        '/static/manifest.json',
        '/static/icon-192.png',
        '/static/icon-512.png'
      ]);
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});