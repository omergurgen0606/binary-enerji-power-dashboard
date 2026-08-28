// Binary Enerji — push bildirimi service worker'ı.
//
// Sunucu şifreli bir yük gönderiyor; burada açılıp sistem bildirimi olarak
// gösteriliyor. Yük çözülemezse bildirim yine de gösteriliyor: alarmın
// hiç görünmemesindense genel bir uyarı görünmesi daha iyi.

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }

  const title = data.title || 'Binary Enerji';
  const options = {
    body: data.body || 'Cihazınızda bir alarm durumu var.',
    icon: '/logo.png',
    badge: '/logo.png',
    // Aynı cihazın art arda gelen alarmları bildirim yığmasın diye.
    tag: data.tag || 'binaryenerji',
    renotify: true,
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  // Pano zaten açıksa yeni sekme açmak yerine ona odaklan.
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.startsWith(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
