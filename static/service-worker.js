// service-worker.js
self.addEventListener('push', function(event) {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'MEF Portal Notification';
  const options = {
    body: data.body || 'You have a new notification.',
    icon: '/static/mef_logo.png',
    badge: '/static/mef_logo.png',
    data: data.url || '/status'
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data)
  );
});
