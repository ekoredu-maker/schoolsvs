// One-time cleanup service worker to remove stale cached versions.
// After activation it deletes old caches, unregisters itself, and refreshes open pages.

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
    } catch (e) {}

    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });

    await self.registration.unregister();

    for (const client of clients) {
      try {
        client.navigate(client.url);
      } catch (e) {}
    }
  })());
});
