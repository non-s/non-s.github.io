// GlobalBR News — Service Worker v3
// Stale-while-revalidate for article pages, cache-first for assets,
// offline fallback with cached articles list.

const CACHE_NAME     = 'globalbr-v3';
const ARTICLE_CACHE  = 'globalbr-articles-v3';
const OFFLINE        = '/offline.html';
const MAX_ARTICLE_CACHE = 20;

const STATIC_ASSETS = [
  '/',
  OFFLINE,
  '/assets/css/style.css',
  '/manifest.json',
];

// ── Install: pre-cache static shell ──────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(c => c.addAll(STATIC_ASSETS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean up old caches ────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME && k !== ARTICLE_CACHE)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Only handle same-origin GET requests
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/assets/') || url.pathname === '/manifest.json') {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
        if (resp.ok) {
          caches.open(CACHE_NAME).then(c => c.put(e.request, resp.clone()));
        }
        return resp;
      }))
    );
    return;
  }

  // Article pages: stale-while-revalidate
  if (url.pathname.match(/\/\w[\w-]*\/\d{4}\/\d{2}\/\d{2}\//)) {
    e.respondWith(
      caches.open(ARTICLE_CACHE).then(async cache => {
        const cached = await cache.match(e.request);
        const fetchPromise = fetch(e.request).then(resp => {
          if (resp.ok) {
            cache.put(e.request, resp.clone());
            // Trim cache to MAX_ARTICLE_CACHE entries
            cache.keys().then(keys => {
              if (keys.length > MAX_ARTICLE_CACHE) {
                cache.delete(keys[0]);
              }
            });
          }
          return resp;
        }).catch(() => cached || caches.match(OFFLINE));
        // Serve cached version immediately; update in background
        return cached || fetchPromise;
      })
    );
    return;
  }

  // Default: network-first with offline fallback
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp.ok) {
          caches.open(CACHE_NAME).then(c => c.put(e.request, resp.clone()));
        }
        return resp;
      })
      .catch(() => caches.match(e.request).then(r => r || caches.match(OFFLINE)))
  );
});

// ── Push notifications ────────────────────────────────────────
self.addEventListener('push', e => {
  if (!e.data) return;
  const data = e.data.json().catch(() => ({ title: 'GlobalBR News', body: e.data.text() }));
  e.waitUntil(
    data.then(d =>
      self.registration.showNotification(d.title || 'GlobalBR News', {
        body:    d.body  || 'New article published',
        icon:    '/assets/images/logo.png',
        badge:   '/assets/images/logo.png',
        tag:     'globalbr-news',
        data:    { url: d.url || '/' },
        actions: [{ action: 'open', title: 'Read now' }],
      })
    )
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const target = e.notification.data?.url || '/';
  e.waitUntil(clients.openWindow(target));
});
