// GuardNest Service Worker — Web Push
const CACHE_NAME = 'guardnest-v1';

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

// Handle incoming push notifications
self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || 'GuardNest';
  const options = {
    body: data.body || 'You have items that need attention.',
    icon: data.icon || '/icon-192.png',
    badge: '/icon-192.png',
    tag: data.tag || 'guardnest-default',
    renotify: true,
    data: { url: data.url || 'https://guardnest.app' }
  };
  e.waitUntil(self.registration.showNotification(title, options));
});

// Handle notification click — open the app
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data?.url || 'https://guardnest.app';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const client of list) {
        if (client.url.includes('guardnest.app') && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
